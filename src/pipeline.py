from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .components import (
    CLASSIFIER_VERSION,
    GENERATOR_VERSION,
    LOCAL_DECISION_BOUNDARY,
    MIN_RETRIEVAL_SCORE,
    RETRIEVAL_VERSION,
    RULES_VERSION,
    DeterministicGenerator,
    assess_risk,
    classify_topic,
    grounding_gate,
    load_kb,
    normalize_text,
    retrieve,
)
from .models import Classification, Ticket


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, object]) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


class SupportPipeline:
    def __init__(self, kb_path: Path, audit_path: Path) -> None:
        self.documents = load_kb(kb_path)
        self.audit = AuditLogger(audit_path)
        self.generator = DeterministicGenerator()

    @staticmethod
    def _request_id(ticket: Ticket) -> str:
        return ticket.ticket_id or f"req-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _versions() -> dict[str, str]:
        return {
            "rules": RULES_VERSION,
            "classifier": CLASSIFIER_VERSION,
            "retrieval": RETRIEVAL_VERSION,
            "generator": GENERATOR_VERSION,
        }

    def _write_audit(
        self,
        *,
        request_id: str,
        ticket: Ticket,
        topic: str,
        route: str,
        risk_status: str,
        risk_reason: str | None,
        confidence: float,
        evidence_ids: list[str],
        decision: str,
        escalation_reason: str | None,
    ) -> None:
        self.audit.write(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "channel": ticket.channel,
                "topic": topic,
                "route": route,
                "risk_status": risk_status,
                "risk_reason": risk_reason,
                "confidence": confidence,
                "evidence_ids": evidence_ids,
                "decision": decision,
                "escalation_reason": escalation_reason,
                "versions": self._versions(),
            }
        )

    def process(self, ticket: Ticket) -> dict[str, object]:
        request_id = self._request_id(ticket)
        normalized = normalize_text(ticket.text)
        risk = assess_risk(normalized)

        if risk.status == "hard_risk":
            self._write_audit(
                request_id=request_id,
                ticket=ticket,
                topic="security",
                route="human_operator",
                risk_status=risk.status,
                risk_reason=risk.reason,
                confidence=0.0,
                evidence_ids=[],
                decision="needs_review",
                escalation_reason=risk.reason,
            )
            return {
                "request_id": request_id,
                "topic": "security",
                "route": "human_operator",
                "risk": risk.status,
                "reason": risk.reason,
                "decision": "needs_review",
                "generator_called": False,
            }

        classification = classify_topic(risk.sanitized_text)
        if classification.confidence < LOCAL_DECISION_BOUNDARY:
            return self._review_result(
                request_id, ticket, classification, "low_confidence"
            )

        evidence = retrieve(risk.sanitized_text, self.documents)
        if evidence is None or evidence.score < MIN_RETRIEVAL_SCORE:
            return self._review_result(
                request_id, ticket, classification, "insufficient_evidence"
            )

        calls_before = self.generator.calls
        draft = self.generator.generate(evidence)
        generator_called = self.generator.calls > calls_before
        if not grounding_gate(draft, evidence, risk.status):
            return self._review_result(
                request_id,
                ticket,
                classification,
                "grounding_or_safety_gate_failed",
                generator_called=generator_called,
            )

        self._write_audit(
            request_id=request_id,
            ticket=ticket,
            topic=classification.topic,
            route=classification.route,
            risk_status=risk.status,
            risk_reason=None,
            confidence=classification.confidence,
            evidence_ids=[evidence.document_id],
            decision="draft_ready",
            escalation_reason=None,
        )
        return {
            "request_id": request_id,
            "topic": classification.topic,
            "route": classification.route,
            "risk": risk.status,
            "confidence": classification.confidence,
            "evidence": [evidence.document_id],
            "decision": "draft_ready",
            "draft": draft,
            "generator_called": generator_called,
        }

    def _review_result(
        self,
        request_id: str,
        ticket: Ticket,
        classification: Classification,
        reason: str,
        *,
        generator_called: bool = False,
    ) -> dict[str, object]:
        self._write_audit(
            request_id=request_id,
            ticket=ticket,
            topic=classification.topic,
            route="human_operator",
            risk_status="safe",
            risk_reason=None,
            confidence=classification.confidence,
            evidence_ids=[],
            decision="needs_review",
            escalation_reason=reason,
        )
        return {
            "request_id": request_id,
            "topic": classification.topic,
            "route": "human_operator",
            "risk": "safe",
            "confidence": classification.confidence,
            "decision": "needs_review",
            "reason": reason,
            "generator_called": generator_called,
        }
