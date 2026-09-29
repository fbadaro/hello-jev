"""Roda cada exemplo no JEV real, grava as respostas e aponta exemplos que caíram numa rota inesperada.

Uso: uv run python scripts/record.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config  # noqa: E402
from app.jev_client import analyze, get_mode  # noqa: E402
from app.pipeline import decide  # noqa: E402


def main() -> int:
    if get_mode() != "live":
        print("Defina TYPESAFE_API_KEY no .env (e não use JEV_MODE=recorded).")
        return 1

    examples = json.loads(config.EXAMPLES_PATH.read_text(encoding="utf-8"))
    recordings = {}
    mismatches = 0
    for ex in examples:
        result = analyze(ex["message"], mode="live")
        decision = decide(result.answers)
        ok = decision.route == ex["expected_route"]
        mismatches += not ok
        print(f"{'OK ' if ok else 'XX '} {ex['id']:<22} {decision.route:<15} {result.latency_ms:6.0f} ms  {decision.reason}")
        recordings[ex["id"]] = {
            "message": ex["message"],
            "model": result.model,
            "answers": result.answers,
            "input_tokens": result.input_tokens,
            "latency_ms": round(result.latency_ms, 1),
        }

    config.RECORDED_PATH.write_text(json.dumps(recordings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGravado em {config.RECORDED_PATH} — {mismatches} exemplo(s) fora da rota esperada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
