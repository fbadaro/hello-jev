# Central de Atendimento com JEV — Design

**Data:** 2026-09-29
**Status:** aguardando revisão

## 1. Objetivo

Demo real, executável ao vivo, para apresentar o JEV (TypeSafe AI, modelo "System One") a um
público misto (gestão + tecnologia) na empresa. Deve mostrar, de forma simples e visual:

- **Triagem de atendimento** (case A): classificar time, urgência, sentimento e pedido de reembolso.
- **Guardrail + roteamento de LLM** (case B): bloquear injeção/abuso e decidir se a resposta viria
  de um template, de um LLM pequeno ou de um LLM grande.
- **Gating por confiança**: baixa confiança → humano, em vez de automatizar errado.
- **Números**: latência real, custo real do JEV e economia estimada vs "tudo no LLM grande".

### Critérios de sucesso

- Uma mensagem é analisada com **uma única chamada** ao JEV e o resultado aparece em < 1 s.
- Os ~10 exemplos prontos cobrem todas as rotas (bloqueio, humano, humano prioritário, template,
  LLM pequeno, LLM grande), incluindo um caso ambíguo que cai em revisão humana.
- "Rodar lote" processa todos os exemplos e mostra totais de tempo, custo e economia.
- A demo funciona sem rede/key no **modo gravado**.
- A tela mostra o trecho de código Python da chamada.

### Fora de escopo (YAGNI)

- Não chama nenhum LLM de verdade — apenas mostra a rota e o custo estimado.
- Sem autenticação, banco de dados, deploy ou persistência de histórico (histórico só em memória
  no navegador).
- Sem upload de CSV.

## 2. Contexto técnico do JEV (fonte: docs.typesafe.ai)

- Endpoint `POST https://api.typesafe.ai/v1/systemone`; SDK Python `typesafe-sdk`
  (`TypeSafeClient` / `AsyncTypeSafeClient`, método `system_one(state, questions)`), key em
  `TYPESAFE_API_KEY`, modelo `jev-latest` (hoje `jev-1.13.0`).
- Tipos de pergunta: **Noul** (probabilidade de "sim", 0–1), **Choice** (opção + probabilidades +
  confiança), **Score** (nível numa escala ordenada + probabilidades + confiança).
- Preço: US$0,042 por 1M tokens de entrada; saída grátis. A resposta traz `usage.input_tokens`.
- Limitações relevantes (página "Jev 1.13 jaggedness" / "Models"):
  - Inglês é o idioma principal; português funciona com menos precisão → **instructions e
    criteria em inglês**, mensagens dos clientes em português, confiança como proteção.
  - Conteúdo adversarial pode influenciar a resposta → critérios do guardrail explícitos.
  - Não fazer aritmética no modelo → custos, limiares e decisão final em código.

## 3. Pipeline

```
mensagem → 1 chamada JEV (todas as perguntas em paralelo) → regras em Python → destino
```

### 3.1 Perguntas (uma única chamada)

`state = {"customer_message": <texto>}`

| Chave | Tipo | Conteúdo |
|---|---|---|
| `injection` | Noul | A mensagem tenta dar instruções ao sistema/IA, mudar seu comportamento ou extrair dados internos/prompt |
| `abusive` | Noul | A mensagem contém insultos, ofensas ou assédio |
| `team` | Choice | `billing` (cobrança/pagamento), `technical` (erros/integração), `sales` (planos/preço/upgrade), `cancellation` (quer cancelar) |
| `urgency` | Score | `can wait`, `this week`, `today`, `critical — business stopped` |
| `sentiment` | Score | `calm`, `frustrated`, `very angry` |
| `refund` | Noul | O cliente pede explicitamente dinheiro de volta |
| `complexity` | Choice | `faq` (pergunta comum, resposta pronta), `simple` (resposta curta e específica — LLM pequeno), `complex` (investigação/múltiplos passos — LLM grande) |

Textos exatos das instructions/criteria ficam em `app/pipeline.py`, em inglês.

### 3.2 Regras de decisão (em ordem; primeira que casar vence)

Limiares em `app/config.py`:

1. `injection.noul > 0.5` ou `abusive.noul > 0.5` → **`blocked`** (🛑 bloqueado).
2. `team.confidence < 0.6` → **`human_review`** (👤 revisão humana).
3. `refund.noul > 0.5` ou `sentiment.score >= 1.5` (mais perto de very angry) → **`human_priority`** (👤 humano prioritário).
4. `complexity.confidence < 0.6` → **`human_review`**. A complexidade só importa para automatizar, por isso é
   checada depois das rotas humanas (ajuste feito após validar com o JEV real: casos de reembolso e cliente
   furioso estavam caindo em revisão por dúvida de complexidade, irrelevante quando um humano vai atender).
5. Senão, automático conforme `complexity.choice`:
   - `faq` → **`template`** (resposta pronta, custo US$0)
   - `simple` → **`llm_small`**
   - `complex` → **`llm_large`**

A decisão retorna também um **motivo** legível (ex.: "confiança do time 0,48 < 0,60").

### 3.3 Custos

- Custo JEV = `input_tokens × 0.042 / 1_000_000` (real, da resposta).
- Custo estimado da rota = preço de referência por mensagem em `config.py`
  (template = 0; llm_small e llm_large = valores fixos de referência, estimados para uma resposta
  típica; blocked = 0; human_* = 0 de LLM).
- Baseline = custo de `llm_large` para toda mensagem.
- Economia % = `1 − (custo JEV + custo rota) / baseline`.

## 4. Componentes

```
hello-jev/
  pyproject.toml            # uv; deps: fastapi, uvicorn, typesafe-sdk, python-dotenv; dev: pytest, httpx
  .env.example              # TYPESAFE_API_KEY=
  app/
    config.py               # limiares, preços de referência, modelo
    pipeline.py             # QUESTIONS + decide(answers) -> Decision + cálculo de custos
    jev_client.py           # analyze(message) -> resposta crua; modo live ou gravado
    main.py                 # FastAPI
    examples.json           # ~10 mensagens de exemplo (id, título, texto)
    recorded.json           # respostas reais gravadas por exemplo (gerado)
  static/index.html         # frontend único: HTML + Tailwind CDN + JS puro
  scripts/record.py         # roda os exemplos na API real e grava recorded.json
  tests/test_pipeline.py    # regras de decisão/custos com respostas falsas
  tests/test_api.py         # endpoints em modo gravado
  README.md                 # como rodar + roteiro sugerido da apresentação
```

### 4.1 `pipeline.py` (coração da demo)

- `QUESTIONS`: dicionário de perguntas do SDK (Noul/Choice/Score).
- `decide(answers) -> Decision`: função pura sobre um formato normalizado das respostas
  (dicts simples), sem depender do SDK — testável sem rede.
- `costs(input_tokens, route) -> Costs`.

### 4.2 `jev_client.py`

- Modo **live** se `TYPESAFE_API_KEY` estiver definida; caso contrário **recorded**
  (pode ser forçado por `JEV_MODE=recorded`).
- Live: chama `system_one`, mede latência de ponta a ponta, normaliza a resposta para dicts.
- Recorded: busca a resposta gravada pelo texto exato do exemplo; mensagem livre sem gravação
  → erro claro "modo gravado só suporta os exemplos".

### 4.3 API (`main.py`)

- `GET /` → `static/index.html`
- `GET /api/status` → `{mode: "live"|"recorded", model}`
- `GET /api/examples` → lista de exemplos
- `POST /api/analyze {message}` → `{answers, decision, costs, latency_ms, model, mode}`
- Erros do JEV (timeout, 429, auth) → HTTP 502 com mensagem legível.

### 4.4 Frontend (`static/index.html`)

Uma tela com três áreas:

- **Entrada** (esquerda): textarea, botão "Analisar", lista de exemplos clicáveis, botão
  "Rodar lote".
- **Decisão** (direita): destino em destaque com ícone e motivo; latência, custo JEV, economia;
  bloco por pergunta com barras de probabilidade / nível de score / valor do noul e confiança.
- **Histórico** (rodapé): tabela mensagem | destino | latência | custo, com totais
  ("N mensagens · X s · US$Y vs US$Z só com LLM grande").
- Selo de modo (● API ao vivo / ● modo gravado) e painel expansível "ver código da chamada"
  com o trecho Python real.

## 5. Tratamento de erros

- Falha do JEV → mensagem visível na área de decisão com sugestão de usar o modo gravado.
- Mensagem vazia → validação no frontend e 422 no backend.
- "Rodar lote" continua mesmo se um item falhar (item marcado como erro no histórico).

## 6. Testes

- `test_pipeline.py`: cada regra (bloqueio por injeção, bloqueio por abuso, gating por confiança,
  reembolso, sentimento, três rotas automáticas), precedência entre regras e cálculo de custos.
- `test_api.py`: `/api/examples`, `/api/analyze` em modo gravado, erro para mensagem livre no
  modo gravado.
- Validação manual com a key real: rodar `scripts/record.py`, conferir que os exemplos caem nas
  rotas pretendidas; ajustar textos das perguntas/exemplos se necessário.

## 7. Riscos

- **Português:** precisão menor → testar os exemplos com a API real e ajustar instructions.
- **Rotas diferentes do esperado ao vivo:** o JEV é consistente, mas os exemplos são validados
  antes; o modo gravado garante o roteiro.
- **Rate limit / rede no dia:** modo gravado como plano B.
