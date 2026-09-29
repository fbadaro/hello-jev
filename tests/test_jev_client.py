import json
from types import SimpleNamespace

import pytest

from app import jev_client
from app.jev_client import JevError, RecordingNotFound, analyze, get_mode, normalize_response


def fake_response():
    return SimpleNamespace(
        model="jev-1.13.0",
        usage=SimpleNamespace(input_tokens=392, output_tokens=65),
        nouls={"refund": SimpleNamespace(noul=0.97)},
        choices={"team": SimpleNamespace(choice="billing", confidence=0.78, probabilities={"billing": 0.85, "sales": 0.15})},
        scores={
            "sentiment": SimpleNamespace(
                score=1.0, confidence=1.0, legend={0: "calm", 1: "frustrated"}, probabilities={0: 0.0, 1: 1.0}
            )
        },
    )


def test_normalize_response():
    model, answers, tokens = normalize_response(fake_response())
    assert model == "jev-1.13.0"
    assert tokens == 392
    assert answers["refund"] == {"type": "noul", "noul": 0.97}
    assert answers["team"] == {
        "type": "choice",
        "choice": "billing",
        "confidence": 0.78,
        "probabilities": {"billing": 0.85, "sales": 0.15},
    }
    assert answers["sentiment"]["legend"] == {"0": "calm", "1": "frustrated"}
    assert answers["sentiment"]["probabilities"] == {"0": 0.0, "1": 1.0}


def test_normalize_handles_missing_usage():
    r = fake_response()
    r.usage = None
    assert normalize_response(r)[2] == 0


def test_mode_live_with_key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.delenv("JEV_MODE", raising=False)
    assert get_mode() == "live"


def test_mode_recorded_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert get_mode() == "recorded"


def test_mode_forced_recorded(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setenv("JEV_MODE", "recorded")
    assert get_mode() == "recorded"


@pytest.fixture
def recorded_file(tmp_path):
    path = tmp_path / "recorded.json"
    path.write_text(
        json.dumps(
            {
                "ex1": {
                    "message": "Fui cobrado duas vezes",
                    "model": "jev-1.13.0",
                    "answers": {"refund": {"type": "noul", "noul": 0.9}},
                    "input_tokens": 400,
                    "latency_ms": 180.0,
                }
            }
        )
    )
    return path


def test_recorded_lookup_by_message(recorded_file):
    r = analyze("  Fui cobrado duas vezes ", mode="recorded", recorded_path=recorded_file)
    assert r.mode == "recorded"
    assert r.input_tokens == 400
    assert r.latency_ms == 180.0
    assert r.answers["refund"]["noul"] == 0.9


def test_recorded_unknown_message(recorded_file):
    with pytest.raises(RecordingNotFound):
        analyze("outra mensagem", mode="recorded", recorded_path=recorded_file)


def test_recorded_missing_file(tmp_path):
    with pytest.raises(RecordingNotFound):
        analyze("x", mode="recorded", recorded_path=tmp_path / "nope.json")


def test_live_wraps_sdk_errors(monkeypatch):
    from typesafe_sdk import TypeSafeError

    def boom(message):
        raise TypeSafeError("rate limited")

    monkeypatch.setattr(jev_client, "_call_live", boom)
    with pytest.raises(JevError, match="Falha ao chamar o JEV"):
        analyze("oi", mode="live")


def test_live_measures_latency(monkeypatch):
    monkeypatch.setattr(jev_client, "_call_live", lambda message: fake_response())
    r = analyze("oi", mode="live")
    assert r.mode == "live"
    assert r.model == "jev-1.13.0"
    assert r.latency_ms >= 0
