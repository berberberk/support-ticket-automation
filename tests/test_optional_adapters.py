from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from src.components import (
    GeneratorUnavailable,
    OpenRouterGenerator,
)
from src.config import AppConfig
from src.factory import build_generator, build_pipeline
from src.models import RetrievedEvidence, Ticket
from src.pipeline import SupportPipeline


class SpyExternalGenerator:
    backend = "openrouter"
    provider = "spy"
    model = "spy-model"
    status = "available"

    def __init__(self) -> None:
        self.calls: list[tuple[str, RetrievedEvidence]] = []

    def generate(self, sanitized_ticket: str, evidence: RetrievedEvidence) -> str:
        self.calls.append((sanitized_ticket, evidence))
        return "Ответ по утверждённой статье"


class StaticRetriever:
    backend = "qdrant"
    status = "available"

    def __init__(self, evidence: RetrievedEvidence | None) -> None:
        self.evidence = evidence

    def retrieve(self, text: str) -> RetrievedEvidence | None:
        return self.evidence


class OptionalAdaptersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temp_dir.name) / "audit.jsonl"
        self.kb_path = Path(__file__).parents[1] / "data" / "kb.json"
        self.evidence = RetrievedEvidence("kb-1", "Правила", 0.9, "Разрешённый текст статьи")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _pipeline(self, generator: object, retriever: object) -> SupportPipeline:
        return SupportPipeline(self.kb_path, self.audit_path, generator=generator, retriever=retriever)  # type: ignore[arg-type]

    def test_default_configuration_keeps_offline_components(self) -> None:
        pipeline = build_pipeline(AppConfig(), self.audit_path)
        self.assertEqual(pipeline.retriever.backend, "lexical")
        self.assertEqual(pipeline.generator.backend, "deterministic")

    def test_hard_risk_never_reaches_external_generator(self) -> None:
        generator = SpyExternalGenerator()
        result = self._pipeline(generator, StaticRetriever(self.evidence)).process(
            Ticket("Аккаунт взломали, замечен несанкционированный вход.")
        )
        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(generator.calls, [])

    def test_external_generator_receives_only_sanitized_ticket(self) -> None:
        generator = SpyExternalGenerator()
        raw = "Не могу войти: ivan@example.com, +7 912 345-67-89"
        self._pipeline(generator, StaticRetriever(self.evidence)).process(Ticket(raw))
        sent_text, _ = generator.calls[0]
        self.assertNotIn("ivan@example.com", sent_text)
        self.assertNotIn("+7 912 345-67-89", sent_text)
        self.assertIn("[EMAIL_REDACTED]", sent_text)

    def test_no_evidence_prevents_external_call(self) -> None:
        generator = SpyExternalGenerator()
        result = self._pipeline(generator, StaticRetriever(None)).process(
            Ticket("Не могу войти в аккаунт, как восстановить пароль?")
        )
        self.assertEqual(result["reason"], "insufficient_evidence")
        self.assertEqual(generator.calls, [])

    def test_openrouter_timeout_fails_closed(self) -> None:
        generator = OpenRouterGenerator(api_key="not-a-real-key", model="openrouter/free", timeout_seconds=1, max_tokens=30)
        with patch("src.components.httpx.post", side_effect=httpx.TimeoutException("timeout")):
            result = self._pipeline(generator, StaticRetriever(self.evidence)).process(
                Ticket("Не могу войти в аккаунт, как восстановить пароль?")
            )
        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["route"], "human_operator")
        self.assertNotIn("draft", result)

    def test_wiring_accepts_semantic_retriever_contract(self) -> None:
        generator = SpyExternalGenerator()
        result = self._pipeline(generator, StaticRetriever(self.evidence)).process(
            Ticket("Не могу войти в аккаунт, как восстановить пароль?")
        )
        self.assertEqual(result["decision"], "draft_ready")
        self.assertEqual(result["evidence"], ["kb-1"])


if __name__ == "__main__":
    unittest.main()
