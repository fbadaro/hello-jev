"""API da demo. Rode com: uv run uvicorn app.main:app --reload"""

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app import config
from app.jev_client import JevError, RecordingNotFound, analyze, get_mode
from app.pipeline import costs, decide

INDEX = Path(__file__).parent.parent / "static" / "index.html"

app = FastAPI(title="Central de Atendimento com JEV")


class AnalyzeRequest(BaseModel):
    message: str = Field(max_length=config.MAX_MESSAGE_CHARS)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a mensagem não pode ser vazia")
        return v.strip()


@app.get("/")
def index():
    return FileResponse(INDEX)


@app.get("/api/status")
def status():
    return {"mode": get_mode(), "model": config.MODEL}


@app.get("/api/examples")
def examples():
    return json.loads(config.EXAMPLES_PATH.read_text(encoding="utf-8"))


@app.post("/api/analyze")
def analyze_message(req: AnalyzeRequest):
    try:
        result = analyze(req.message)
    except RecordingNotFound as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except JevError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    decision = decide(result.answers)
    return {
        "model": result.model,
        "mode": result.mode,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "answers": result.answers,
        "decision": asdict(decision),
        "costs": asdict(costs(result.input_tokens, decision.route)),
    }
