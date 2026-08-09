from __future__ import annotations

from pathlib import Path

from .components import (
    DeterministicGenerator,
    Generator,
    LexicalRetriever,
    OpenRouterGenerator,
    QdrantRetriever,
    Retriever,
    load_kb,
)
from .config import AppConfig
from .metrics import MetricsCollector
from .pipeline import SupportPipeline


ROOT = Path(__file__).resolve().parents[1]


def build_retriever(config: AppConfig) -> Retriever:
    documents = load_kb(ROOT / "data" / "kb.json")
    lexical = LexicalRetriever(documents)
    if config.retrieval_backend != "qdrant":
        return lexical
    try:
        return QdrantRetriever(
            documents,
            embedding_model=config.embedding_model,
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
            fallback=lexical,
        )
    except Exception as exc:
        lexical.status = f"fallback:{type(exc).__name__}"
        return lexical


def build_generator(config: AppConfig) -> Generator:
    if config.generator_backend == "openrouter" and config.openrouter_api_key:
        return OpenRouterGenerator(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            timeout_seconds=config.openrouter_timeout_seconds,
            max_tokens=config.openrouter_max_tokens,
        )
    return DeterministicGenerator()


def build_pipeline(
    config: AppConfig,
    audit_path: Path | None = None,
    metrics: MetricsCollector | None = None,
) -> SupportPipeline:
    return SupportPipeline(
        ROOT / "data" / "kb.json",
        audit_path or ROOT / "runtime" / "api_audit.jsonl",
        retriever=build_retriever(config),
        generator=build_generator(config),
        metrics=metrics,
    )
