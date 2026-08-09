import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from src.components import DeterministicGenerator


class ApiContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temp_dir.name) / "api_audit.jsonl"
        self.client = TestClient(create_app(audit_path=self.audit_path))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_safe_ticket_returns_grounded_draft(self) -> None:
        response = self.client.post(
            "/tickets",
            json={
                "request_id": "api-safe",
                "channel": "web",
                "text": "Не могу войти в аккаунт, как восстановить пароль?",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "draft_ready")
        self.assertEqual(body["topic"], "account_access")
        self.assertIn("kb-password-reset", body["evidence_ids"])
        self.assertIsNotNone(body["draft"])

    def test_risky_ticket_returns_review_not_http_error(self) -> None:
        response = self.client.post(
            "/tickets",
            json={
                "request_id": "api-risky",
                "channel": "web",
                "text": "Мой аккаунт взломали, был несанкционированный вход.",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "needs_review")
        self.assertEqual(body["route"], "human_operator")
        self.assertIsNone(body["draft"])

    def test_malformed_request_returns_validation_error(self) -> None:
        response = self.client.post(
            "/tickets",
            json={"request_id": "api-invalid", "channel": "web"},
        )

        self.assertEqual(response.status_code, 422)

    def test_unavailable_generator_fails_closed(self) -> None:
        client = TestClient(
            create_app(
                generator=DeterministicGenerator(available=False),
                audit_path=self.audit_path,
            )
        )
        response = client.post(
            "/tickets",
            json={
                "request_id": "api-outage",
                "channel": "web",
                "text": "Не могу войти в аккаунт, как восстановить пароль?",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "needs_review")
        self.assertEqual(body["route"], "human_operator")
        self.assertEqual(body["reason"], "generator_unavailable")
        self.assertIsNone(body["draft"])


if __name__ == "__main__":
    unittest.main()
