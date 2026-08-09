from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app import create_app
from src.components import DeterministicGenerator, OpenRouterGenerator
from src.metrics import MetricsCollector
from src.models import RetrievedEvidence, Ticket
from src.pipeline import SupportPipeline


class StaticRetriever:
    backend = "lexical"
    status = "available"

    def __init__(self, evidence: RetrievedEvidence | None) -> None:
        self.evidence = evidence

    def retrieve(self, text: str) -> RetrievedEvidence | None:
        return self.evidence


class FailingAuditSink:
    def write(self, record: dict[str, object]) -> None:
        raise OSError("audit_failed")


class MetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temp_dir.name) / "audit.jsonl"
        self.kb_path = Path(__file__).parents[1] / "data" / "kb.json"
        self.evidence = RetrievedEvidence(
            "kb-password-reset", "Пароль", 0.9, "Восстановите пароль через форму входа."
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def pipeline(
        self,
        generator: object | None = None,
        retriever: object | None = None,
        metrics: MetricsCollector | None = None,
    ) -> SupportPipeline:
        return SupportPipeline(
            self.kb_path,
            self.audit_path,
            generator=generator,  # type: ignore[arg-type]
            retriever=retriever,  # type: ignore[arg-type]
            metrics=metrics,
        )

    def test_safe_request_counts_request_decision_retrieval_and_generator(self) -> None:
        metrics = MetricsCollector()
        result = self.pipeline(metrics=metrics).process(
            Ticket("Не могу войти в аккаунт, как восстановить пароль?")
        )
        snapshot = metrics.snapshot()
        self.assertEqual(result["decision"], "draft_ready")
        self.assertEqual(snapshot["requests_total"], 1)
        self.assertEqual(snapshot["draft_ready_total"], 1)
        self.assertEqual(snapshot["retrieval_calls_total"], 1)
        self.assertEqual(snapshot["generator_calls_total"], 1)
        self.assertEqual(snapshot["generator_failures_total"], 0)
        self.assertEqual(snapshot["generator_latency_ms"]["count"], 1)  # type: ignore[index]

    def test_hard_risk_counts_review_without_retrieval_or_generator(self) -> None:
        metrics = MetricsCollector()
        result = self.pipeline(metrics=metrics).process(
            Ticket("Аккаунт взломали, замечен несанкционированный вход.")
        )
        snapshot = metrics.snapshot()
        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(snapshot["hard_risk_total"], 1)
        self.assertEqual(snapshot["needs_review_total"], 1)
        self.assertEqual(snapshot["retrieval_calls_total"], 0)
        self.assertEqual(snapshot["generator_calls_total"], 0)

    def test_provider_failure_counts_generator_failure(self) -> None:
        metrics = MetricsCollector()

        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        generator = OpenRouterGenerator(
            api_key="test-key",
            model="openrouter/test",
            timeout_seconds=1,
            max_tokens=30,
            http_client=httpx.Client(transport=httpx.MockTransport(timeout)),
        )
        result = self.pipeline(generator, StaticRetriever(self.evidence), metrics).process(
            Ticket("Не могу войти в аккаунт, как восстановить пароль?")
        )
        snapshot = metrics.snapshot()
        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(snapshot["generator_calls_total"], 1)
        self.assertEqual(snapshot["generator_failures_total"], 1)
        self.assertEqual(snapshot["needs_review_total"], 1)

    def test_audit_failure_counts_before_exception_propagates(self) -> None:
        metrics = MetricsCollector()
        pipeline = self.pipeline(metrics=metrics)
        pipeline.audit = FailingAuditSink()  # type: ignore[assignment]
        with self.assertRaisesRegex(OSError, "audit_failed"):
            pipeline.process(Ticket("Не могу войти в аккаунт, как восстановить пароль?"))
        self.assertEqual(metrics.snapshot()["audit_failures_total"], 1)

    def test_metrics_endpoint_never_returns_ticket_or_secret(self) -> None:
        metrics = MetricsCollector()
        app = create_app(audit_path=self.audit_path, metrics=metrics)
        client = TestClient(app)
        raw = "Не могу войти: ivan@example.com"
        client.post("/tickets", json={"request_id": "metrics-safe", "text": raw})
        body = client.get("/metrics").json()
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertEqual(body["requests_total"], 1)
        self.assertNotIn(raw, serialized)
        self.assertNotIn("ivan@example.com", serialized)
        self.assertNotIn("OPENROUTER", serialized)


if __name__ == "__main__":
    unittest.main()
