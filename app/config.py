"""Parâmetros da demo — ajuste aqui limiares e preços de referência."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = "jev-latest"

# Limiares das regras de decisão
GUARDRAIL_MIN = 0.5  # noul > isto em injection/abusive => bloqueia
GATING_CONFIDENCE_MIN = 0.6  # confiança < isto em team/complexity => revisão humana
REFUND_MIN = 0.5  # noul > isto em refund => humano prioritário
SENTIMENT_ANGRY_MIN = 1.5  # score (0=calm, 1=frustrated, 2=very angry) >= isto => humano prioritário

# Preço real do JEV
JEV_PRICE_PER_M_INPUT = 0.042  # US$ por 1M tokens de entrada; saída grátis

# Custo de LLM de REFERÊNCIA por mensagem (ilustrativo — ajuste para os preços que sua empresa usa).
# Premissa: ~1.500 tokens de entrada + ~500 de saída por resposta.
ROUTE_COST_USD = {
    "blocked": 0.0,
    "human_review": 0.0,
    "human_priority": 0.0,
    "template": 0.0,
    "llm_small": 0.004,
    "llm_large": 0.02,
}
BASELINE_ROUTE = "llm_large"  # cenário "sem JEV": tudo vai para o LLM grande

MAX_MESSAGE_CHARS = 4000

APP_DIR = Path(__file__).parent
EXAMPLES_PATH = APP_DIR / "examples.json"
RECORDED_PATH = APP_DIR / "recorded.json"
