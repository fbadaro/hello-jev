"""Chamada ao JEV: ao vivo via SDK, ou reprodução das respostas gravadas (plano B da apresentação)."""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import RetryPolicy, TypeSafeClient, TypeSafeError

from app import config
from app.pipeline import QUESTIONS


class JevError(Exception):
    """Erro com mensagem pronta para exibir na tela."""


class RecordingNotFound(JevError):
    pass


@dataclass
class JevResult:
    model: str
    answers: dict
    input_tokens: int
    latency_ms: float
    mode: str


def get_mode() -> str:
    if os.environ.get("JEV_MODE") == "recorded" or not os.environ.get("TYPESAFE_API_KEY"):
        return "recorded"
    return "live"


def normalize_response(response) -> tuple[str, dict, int]:
    """Converte a resposta do SDK em dicts simples (mesmo formato do JSON da API REST)."""
    answers: dict = {}
    for key, a in response.nouls.items():
        answers[key] = {"type": "noul", "noul": a.noul}
    for key, a in response.choices.items():
        answers[key] = {
            "type": "choice",
            "choice": a.choice,
            "confidence": a.confidence,
            "probabilities": {str(k): v for k, v in a.probabilities.items()},
        }
    for key, a in response.scores.items():
        answers[key] = {
            "type": "score",
            "score": a.score,
            "confidence": a.confidence,
            "legend": {str(k): v for k, v in a.legend.items()},
            "probabilities": {str(k): v for k, v in a.probabilities.items()},
        }
    tokens = (response.usage.input_tokens if response.usage else None) or 0
    return response.model, answers, tokens


_client = None


def _get_client():
    # Um cliente reaproveitado: a latência medida não inclui abrir conexão (TCP/TLS) a cada chamada.
    # Sem retries e com timeout curto: ao vivo, é melhor falhar rápido e trocar para o modo gravado.
    global _client
    if _client is None:
        _client = TypeSafeClient(model=config.MODEL, timeout=5, retry=RetryPolicy(max_retries=0))
    return _client


def _call_live(message: str):
    return _get_client().system_one(state={"customer_message": message}, questions=QUESTIONS)


def _analyze_live(message: str) -> JevResult:
    start = time.perf_counter()
    try:
        response = _call_live(message)
    except TypeSafeError as e:
        raise JevError(f"Falha ao chamar o JEV: {str(e).rstrip('.')}. Dica: use o modo gravado (JEV_MODE=recorded).") from e
    latency_ms = (time.perf_counter() - start) * 1000
    model, answers, tokens = normalize_response(response)
    return JevResult(model=model, answers=answers, input_tokens=tokens, latency_ms=latency_ms, mode="live")


def _analyze_recorded(message: str, path: Path) -> JevResult:
    if not path.exists():
        raise RecordingNotFound("Nenhuma resposta gravada. Rode scripts/record.py com a API key configurada.")
    recordings = json.loads(path.read_text(encoding="utf-8"))
    for rec in recordings.values():
        if rec["message"].strip() == message.strip():
            return JevResult(
                model=rec["model"],
                answers=rec["answers"],
                input_tokens=rec["input_tokens"],
                latency_ms=rec["latency_ms"],
                mode="recorded",
            )
    raise RecordingNotFound("O modo gravado só funciona com os exemplos prontos.")


def analyze(message: str, mode: str | None = None, recorded_path: Path | None = None) -> JevResult:
    mode = mode or get_mode()
    if mode == "live":
        return _analyze_live(message)
    return _analyze_recorded(message, recorded_path or config.RECORDED_PATH)
