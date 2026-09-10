# Safety-First Support Ticket Automation

[![CI](https://github.com/berberberk/itmo-aith-project-2/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/berberberk/itmo-aith-project-2/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue)

A local, safety-first proof of concept for routing customer-support tickets and preparing grounded response drafts. It automates only low-risk, well-supported cases; ambiguous or sensitive requests are routed to a human operator.

> **Portfolio context.** This repository was created as a time-boxed Machine Learning System Design (MLSD) case for the 2026 admission process to ITMO AI Talent Hub. It is published as a portfolio artifact after the selection process. The goal was to demonstrate a small, runnable system with explicit safety boundaries, failure behavior, and an honest production design—not to claim production readiness.

## Why the design looks like this

The key engineering trade-off is intentional: support automation should be judged not only by how often it produces a draft, but also by when it declines to automate.

The pipeline assigns a request ID, masks email addresses and phone numbers, applies hard risk rules, routes recognised low-risk tickets, retrieves an approved knowledge-base article, and creates an evidence-bound draft. It records an audit event without storing the raw ticket text. Every risky, ambiguous, unsupported, or failed case returns `needs_review` with no automatic draft. The default setup runs fully locally, without network access or API keys.

| Area | Implemented in this PoC | Production direction |
| --- | --- | --- |
| Risk policy and routing | Deterministic rules and keyword classification | Rules remain a hard safety layer; a calibrated classifier can improve routing |
| Knowledge retrieval | Local lexical search over four articles | Versioned approved corpus; optional semantic retrieval |
| Draft generation | Deterministic, evidence-bound template | Optional LLM only after retrieval and policy checks |
| Human escalation | Explicit `needs_review` response and reason | Operator queue, UI, review SLA, and feedback loop |
| Auditability | Local JSONL log with masked inputs | Durable audit store, access controls, and retention policy |
| Reliability | Synchronous pipeline; provider failure escalates | Queue, workers, bounded retries, idempotency, and persistent state |

Hard rules protect account-security incidents, disputed payments, and verification codes. Retrieval provides evidence before drafting. LLM generation is optional and never part of the fast-path safety decision.

## Run locally

The project uses [uv](https://docs.astral.sh/uv/) and supports Python 3.11+. The primary scenario was verified on Python 3.12.

```bash
uv sync
uv run python demo.py
uv run python evaluate.py
uv run python -m unittest discover -s tests -v
```

Start the HTTP API:

```bash
uv run uvicorn app:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
```

### Happy path

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"api-demo-1","channel":"web","text":"I cannot log in to my account. How do I reset my password?"}'
```

The response has `status: "draft_ready"` and includes the matched knowledge-base article.

### Safety / human-review path

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"api-risk-1","channel":"web","text":"My account was compromised and there was an unauthorized login."}'
```

The response has `status: "needs_review"`, routes to `human_operator`, and returns `draft: null`.

## Optional adapters

Optional Qdrant/FastEmbed and OpenRouter adapters are included but disabled by default. Real FastEmbed loading and live OpenRouter calls were intentionally not used during the MLSD case. An external generator receives only masked ticket text and one approved article; any failure falls back to human review.

```bash
cp .env.example .env
```

```bash
# semantic retrieval
RETRIEVAL_BACKEND=qdrant

# external draft generator
GENERATOR_BACKEND=openrouter
OPENROUTER_API_KEY=...
```

Without an API key or a configured Qdrant instance, the component factory keeps the safe local deterministic components. Use `uv run python demo_rag.py` to exercise the selected adapters.

## Limitations and evaluation

`uv run python evaluate.py` runs a small fixture-based sanity evaluation of deterministic PoC behaviour. It is not a production ML benchmark and its thresholds are demonstrative rather than calibrated.

- Risk and topic decisions use deterministic rules rather than trained production models.
- The default corpus has four local articles; retrieval evaluation is small and synthetic.
- There is no queue, retry mechanism, durable ticket-state store, or operator interface.
- Demo thresholds are not calibrated production thresholds.

In production, thresholds would be calibrated on held-out labelled tickets against error cost and available review capacity. Rules would protect hard safety constraints; a classical classifier would be the first ML baseline; retrieval would ground any generative step.

## Further reading

- [Original Russian case README](README-RU.md)
- [Architecture](docs/architecture.md) *(Russian)*
- [ML approach and evaluation](docs/ml.md) *(Russian)*
- [Monitoring](docs/monitoring.md) *(Russian)*
- [Risks and operations](docs/risks-and-ops.md) *(Russian)*
- [AI usage and verification log](AI_USAGE.md) *(Russian)*
