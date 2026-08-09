import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.models import Ticket
from src.components import DeterministicGenerator, assess_risk
from src.pipeline import SupportPipeline


ROOT = Path(__file__).resolve().parents[1]


class SmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        audit_path = Path(self.temp_dir.name) / "audit.jsonl"
        self.pipeline = SupportPipeline(ROOT / "data" / "kb.json", audit_path)
        self.audit_path = audit_path

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_happy_path_uses_evidence_and_generator(self) -> None:
        result = self.pipeline.process(
            Ticket("Как восстановить пароль и снова войти в аккаунт?", ticket_id="happy")
        )

        self.assertEqual(result["decision"], "draft_ready")
        self.assertEqual(result["risk"], "safe")
        self.assertIn("kb-password-reset", result["evidence"])
        self.assertTrue(result["generator_called"])

    def test_risky_path_escalates_without_generator(self) -> None:
        result = self.pipeline.process(
            Ticket("Кажется, мой аккаунт взломали: есть несанкционированный вход.", ticket_id="risky")
        )

        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["route"], "human_operator")
        self.assertFalse(result["generator_called"])
        self.assertNotIn("draft", result)

    def test_unknown_low_confidence_escalates(self) -> None:
        result = self.pipeline.process(
            Ticket("Нужна помощь с необычным вопросом о профиле.", ticket_id="unknown")
        )

        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["reason"], "low_confidence")
        self.assertFalse(result["generator_called"])

    def test_audit_does_not_contain_raw_ticket_text(self) -> None:
        raw_text = "Как восстановить пароль, email audit-secret@example.com"
        self.pipeline.process(Ticket(raw_text, ticket_id="privacy"))

        audit_text = self.audit_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in audit_text.splitlines()]
        self.assertEqual(len(records), 1)
        self.assertNotIn(raw_text, audit_text)
        self.assertNotIn("audit-secret@example.com", audit_text)

    def test_pii_is_redacted_before_audit(self) -> None:
        raw_text = "Как восстановить пароль, email pii@example.com"
        assessment = assess_risk(raw_text)
        result = self.pipeline.process(Ticket(raw_text, ticket_id="pii"))

        self.assertNotIn("pii@example.com", assessment.sanitized_text)
        self.assertIn("[EMAIL_REDACTED]", assessment.sanitized_text)
        self.assertEqual(result["decision"], "draft_ready")
        self.assertNotIn("pii@example.com", self.audit_path.read_text(encoding="utf-8"))

    def test_insufficient_evidence_escalates_without_draft(self) -> None:
        result = self.pipeline.process(
            Ticket(
                "Как восстановить зелёный идентификатор пользователя из другого региона сегодня?",
                ticket_id="no-evidence",
            )
        )

        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["reason"], "insufficient_evidence")
        self.assertNotIn("draft", result)

    def test_empty_input_fails_closed(self) -> None:
        result = self.pipeline.process(Ticket("   ", ticket_id="empty"))

        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["route"], "human_operator")
        self.assertNotIn("draft", result)

    def test_ambiguous_topic_fails_closed(self) -> None:
        result = self.pipeline.process(
            Ticket("Подписка и платёж, нужна помощь.", ticket_id="ambiguous")
        )

        self.assertEqual(result["topic"], "unknown")
        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["reason"], "low_confidence")
        self.assertNotIn("draft", result)

    def test_generator_unavailable_fails_safe(self) -> None:
        pipeline = SupportPipeline(
            ROOT / "data" / "kb.json",
            self.audit_path,
            generator=DeterministicGenerator(available=False),
        )

        result = pipeline.process(
            Ticket("Как восстановить пароль и снова войти в аккаунт?", ticket_id="outage")
        )

        self.assertEqual(result["decision"], "needs_review")
        self.assertEqual(result["route"], "human_operator")
        self.assertEqual(result["reason"], "generator_unavailable")
        self.assertEqual(result["generator_status"], "unavailable")
        self.assertFalse(result["generator_called"])
        self.assertNotIn("draft", result)

    def test_evaluation_script_runs(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "evaluate.py")],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("=== PoC SANITY EVALUATION ===", completed.stdout)
        self.assertIn("SAFETY: hard-risk automatic drafts=0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
