# Central de Atendimento com JEV

Demo do **JEV** (TypeSafe AI), um modelo "System One": em vez de gerar texto, ele recebe um estado e
perguntas tipadas e devolve **decisões estruturadas com confiança calibrada** — em ~100–500 ms e por
US$0,042 por milhão de tokens de entrada.

Cada mensagem de cliente passa por **uma única chamada** ao JEV com 7 perguntas em paralelo:

| Pergunta | Tipo | Para quê |
|---|---|---|
| injeção de prompt / conteúdo abusivo | Noul | **Guardrail** |
| time, urgência, sentimento, reembolso | Choice / Score / Noul | **Triagem** |
| complexidade (FAQ / simples / complexo) | Choice | **Roteamento de LLM** |

As regras finais são código Python (`app/pipeline.py`), com **gating por confiança**:
bloqueio → revisão humana (confiança < 0,6) → humano prioritário → resposta pronta / LLM pequeno / LLM grande.

**Apresentação:** https://fbadaro.github.io/hello-jev/ (fonte em `presentation/index.html`)

## Rodando

```bash
cp .env.example .env          # coloque sua TYPESAFE_API_KEY
uv sync
uv run python scripts/record.py   # opcional: valida exemplos e grava respostas p/ modo offline
uv run uvicorn app.main:app --reload
# abra http://127.0.0.1:8000
```

Sem key (ou com `JEV_MODE=recorded`) a demo roda no **modo gravado**, reproduzindo respostas reais
salvas em `app/recorded.json` — plano B para a apresentação.

Testes: `uv run pytest`

## Roteiro sugerido (≈10 min)

1. **O problema** — usar um LLM grande para decidir coisas simples (classificar, filtrar, rotear) é caro e lento.
2. **"Trocar senha"** — vira resposta pronta, sem LLM. Mostre latência e custo.
3. **"Integração caiu"** vs **"Upgrade de plano"** — o JEV manda um para o LLM grande e outro para o pequeno.
4. **"Tentativa de injeção"** — bloqueada antes de chegar a qualquer LLM.
5. **"Cobrado duas vezes"** / **"Cliente furioso"** — escalados para humano prioritário.
6. **"Mensagem ambígua"** — confiança baixa → revisão humana. *O JEV diz quando não tem certeza; o código decide o que fazer com isso.*
7. **Rodar lote** — leia os totais: custo com JEV vs mandar tudo para o LLM grande.
8. **Ver código** — uma chamada, 7 perguntas, regras em `if`.

## Limites honestos (vale mencionar)

- O JEV **não gera texto** — ele decide; a resposta ao cliente continua sendo de um template ou LLM.
- Funciona melhor em **inglês**; em português, as instruções ficam em inglês e a confiança serve de proteção.
- Pode ficar confiante escolhendo entre opções que não contêm a resposta certa — desenhe bem as opções e meça no seu próprio dado.
- Custos de LLM na tela são **valores de referência** (`app/config.py`), não chamadas reais.

Referências: `REFERENCES.md` · Docs: https://docs.typesafe.ai
