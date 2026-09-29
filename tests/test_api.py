import pytest
from fastapi.testclient import TestClient

from app import main
from app.jev_client import JevError, JevResult, RecordingNotFound


@pytest.fixture
def client():
    return TestClient(main.app)


def good_answers():
    return {
        "injection": {"type": "noul", "noul": 0.01},
        "abusive": {"type": "noul", "noul": 0.01},
        "team": {"type": "choice", "choice": "sales", "confidence": 0.9, "probabilities": {"sales": 0.95}},
        "urgency": {"type": "score", "score": 1.0, "confidence": 0.8, "legend": {}, "probabilities": {}},
        "sentiment": {"type": "score", "score": 0.0, "confidence": 0.9, "legend": {}, "probabilities": {}},
        "refund": {"type": "noul", "noul": 0.02},
        "complexity": {"type": "choice", "choice": "simple", "confidence": 0.85, "probabilities": {"simple": 0.9}},
    }


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Central de Atendimento com JEV" in r.text


def test_status(client, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert client.get("/api/status").json() == {"mode": "recorded", "model": "jev-latest"}


def test_examples(client):
    examples = client.get("/api/examples").json()
    assert len(examples) == 10
    assert {"id", "title", "message", "expected_route"} <= set(examples[0])


def test_analyze_success(client, monkeypatch):
    monkeypatch.setattr(
        main, "analyze",
        lambda message: JevResult(model="jev-1.13.0", answers=good_answers(), input_tokens=1000, latency_ms=150.0, mode="live"),
    )
    body = client.post("/api/analyze", json={"message": "Quero fazer upgrade"}).json()
    assert body["decision"]["route"] == "llm_small"
    assert body["costs"]["jev_usd"] == pytest.approx(0.000042)
    assert body["latency_ms"] == 150.0
    assert body["mode"] == "live"
    assert body["answers"]["team"]["choice"] == "sales"


@pytest.mark.parametrize("message", ["", "   \n  "])
def test_analyze_rejects_blank(client, message):
    assert client.post("/api/analyze", json={"message": message}).status_code == 422


def test_analyze_rejects_too_long(client):
    assert client.post("/api/analyze", json={"message": "a" * 4001}).status_code == 422


def test_analyze_recording_not_found(client, monkeypatch):
    def raise_nf(message):
        raise RecordingNotFound("O modo gravado só funciona com os exemplos prontos.")

    monkeypatch.setattr(main, "analyze", raise_nf)
    r = client.post("/api/analyze", json={"message": "livre"})
    assert r.status_code == 400
    assert "exemplos prontos" in r.json()["detail"]


def test_analyze_jev_failure(client, monkeypatch):
    def raise_err(message):
        raise JevError("Falha ao chamar o JEV: timeout")

    monkeypatch.setattr(main, "analyze", raise_err)
    r = client.post("/api/analyze", json={"message": "oi"})
    assert r.status_code == 502
    assert "Falha ao chamar o JEV" in r.json()["detail"]
