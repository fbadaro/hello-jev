import pytest

from app.pipeline import QUESTIONS, costs, decide


def noul(p):
    return {"type": "noul", "noul": p}


def choice(label, confidence):
    return {"type": "choice", "choice": label, "confidence": confidence, "probabilities": {label: confidence}}


def score(value, confidence=0.9):
    return {"type": "score", "score": value, "confidence": confidence, "legend": {}, "probabilities": {}}


def answers(**overrides):
    base = {
        "injection": noul(0.01),
        "abusive": noul(0.01),
        "team": choice("billing", 0.9),
        "urgency": score(1.0),
        "sentiment": score(0.0),
        "refund": noul(0.05),
        "complexity": choice("simple", 0.9),
    }
    base.update(overrides)
    return base


def test_questions_cover_all_keys():
    assert set(QUESTIONS) == {"injection", "abusive", "team", "urgency", "sentiment", "refund", "complexity"}


def test_injection_blocks():
    d = decide(answers(injection=noul(0.93)))
    assert d.route == "blocked"
    assert "injeção" in d.reason


def test_abusive_blocks():
    assert decide(answers(abusive=noul(0.8))).route == "blocked"


def test_block_wins_over_everything():
    d = decide(answers(injection=noul(0.9), team=choice("billing", 0.1), refund=noul(0.99)))
    assert d.route == "blocked"


def test_low_team_confidence_goes_to_human_review():
    d = decide(answers(team=choice("billing", 0.48)))
    assert d.route == "human_review"
    assert "0,48" in d.reason


def test_low_complexity_confidence_goes_to_human_review():
    assert decide(answers(complexity=choice("faq", 0.3))).route == "human_review"


def test_review_wins_over_priority():
    assert decide(answers(team=choice("billing", 0.2), refund=noul(0.99))).route == "human_review"


def test_refund_goes_to_priority():
    d = decide(answers(refund=noul(0.97)))
    assert d.route == "human_priority"
    assert "reembolso" in d.reason


def test_very_angry_goes_to_priority():
    assert decide(answers(sentiment=score(1.8))).route == "human_priority"


def test_frustrated_is_not_priority():
    assert decide(answers(sentiment=score(1.2))).route == "llm_small"


@pytest.mark.parametrize(
    "label,route", [("faq", "template"), ("simple", "llm_small"), ("complex", "llm_large")]
)
def test_automatic_routes(label, route):
    assert decide(answers(complexity=choice(label, 0.9))).route == route


def test_thresholds_are_strict():
    # confiança exatamente 0.6 não aciona revisão; noul exatamente 0.5 não bloqueia
    d = decide(answers(team=choice("billing", 0.6), injection=noul(0.5), refund=noul(0.5)))
    assert d.route == "llm_small"


def test_missing_answers_do_not_crash():
    a = answers()
    del a["complexity"]
    del a["injection"]
    assert decide(a).route == "human_review"


def test_missing_confidence_counts_as_zero():
    a = answers(team={"type": "choice", "choice": "billing"})
    assert decide(a).route == "human_review"


def test_costs_for_small_llm():
    c = costs(input_tokens=1000, route="llm_small")
    assert c.jev_usd == pytest.approx(0.000042)
    assert c.route_usd == pytest.approx(0.004)
    assert c.baseline_usd == pytest.approx(0.02)
    assert c.savings_pct == pytest.approx(100 * (1 - (0.000042 + 0.004) / 0.02))


def test_costs_for_template_are_almost_all_savings():
    c = costs(input_tokens=500, route="template")
    assert c.route_usd == 0
    assert c.savings_pct > 99


def test_priority_ignores_complexity_uncertainty():
    # complexidade só importa para automatizar; se vai para humano de qualquer forma, a dúvida é irrelevante
    assert decide(answers(refund=noul(0.98), complexity=choice("complex", 0.5))).route == "human_priority"
    assert decide(answers(sentiment=score(2.0), complexity=choice("complex", 0.56))).route == "human_priority"


def test_team_uncertainty_still_wins_over_priority():
    assert decide(answers(team=choice("billing", 0.4), refund=noul(0.98))).route == "human_review"
