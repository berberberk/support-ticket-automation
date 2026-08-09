#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from src.config import load_config
from src.factory import build_pipeline
from src.models import Ticket


ROOT = Path(__file__).parent


def _print_result(label: str, result: dict[str, object]) -> None:
    print(f"=== {label} ===")
    print(f"topic: {result['topic']}")
    print(f"retriever: {result.get('retriever_backend')} ({result.get('retriever_status')})")
    print(f"evidence: {result.get('evidence', [])}")
    print(f"scores: {result.get('evidence_scores', {})}")
    print(f"generator: {result.get('generator_provider')} / {result.get('generator_model')}")
    print(f"decision: {result['decision']}")
    print(f"generator_called: {result['generator_called']}")
    print(f"draft: {result.get('draft')}")


def main() -> None:
    config = load_config()
    pipeline = build_pipeline(config, ROOT / "runtime" / "rag_audit.jsonl")
    print(f"retrieval_backend: {pipeline.retriever.backend}")
    print(f"generator_backend: {pipeline.generator.backend}")
    print("ticket text is sanitized before an external generator; API keys are never printed.")
    _print_result(
        "SAFE RAG",
        pipeline.process(
            Ticket(
                ticket_id="rag-safe",
                channel="demo",
                text="Я забыл пароль и не могу авторизоваться, как вернуть доступ?",
            )
        ),
    )
    _print_result(
        "HARD RISK",
        pipeline.process(
            Ticket(
                ticket_id="rag-risk",
                channel="demo",
                text="Аккаунт взломали, замечен несанкционированный вход.",
            )
        ),
    )


if __name__ == "__main__":
    main()
