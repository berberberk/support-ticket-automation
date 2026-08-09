from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    generator_backend: str = "deterministic"
    retrieval_backend: str = "lexical"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"
    openrouter_timeout_seconds: float = 10.0
    openrouter_max_tokens: int = 300
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None


def load_config(env_path: Path | None = None) -> AppConfig:
    """Загрузить локальную конфигурацию; ключи не выводятся в логи и ответы API."""

    load_dotenv(env_path or ROOT / ".env")
    values = os.environ
    return AppConfig(
        generator_backend=values.get("GENERATOR_BACKEND", "deterministic").lower(),
        retrieval_backend=values.get("RETRIEVAL_BACKEND", "lexical").lower(),
        openrouter_api_key=values.get("OPENROUTER_API_KEY") or None,
        openrouter_model=values.get("OPENROUTER_MODEL", "openrouter/free"),
        openrouter_timeout_seconds=float(
            values.get("OPENROUTER_TIMEOUT_SECONDS", "10")
        ),
        openrouter_max_tokens=int(values.get("OPENROUTER_MAX_TOKENS", "300")),
        embedding_model=values.get(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        qdrant_url=values.get("QDRANT_URL") or None,
        qdrant_api_key=values.get("QDRANT_API_KEY") or None,
    )
