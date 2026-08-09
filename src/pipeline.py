from __future__ import annotations

import json
import time
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
    Generator,
    GeneratorUnavailable,
    LexicalRetriever,
    Retriever,
    assess_risk,
    classify_topic,
    grounding_gate,
    load_kb,
    normalize_text,
)
from .models import Classification, RetrievedEvidence, Ticket
from .metrics import MetricsCollector


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, object]) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


class SupportPipeline:
    def __init__(
        self,
        kb_path: Path,
        audit_path: Path,
        generator: Generator | None = None,
        retriever: Retriever | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self.documents = load_kb(kb_path)
        self.audit = AuditLogger(audit_path)
        from .components import DeterministicGenerator

        self.generator = generator or DeterministicGenerator()
        self.retriever = retriever or LexicalRetriever(self.documents)
        self.metrics = metrics or MetricsCollector()

    @staticmethod
    def _request_id(ticket: Ticket) -> str:
        return ticket.ticket_id or f"req-{uuid.uuid4().hex[:12]}"

    def _versions(self) -> dict[str, str]:
        return {
            "rules": RULES_VERSION,
            "classifier": CLASSIFIER_VERSION,
            "retrieval": getattr(self.retriever, "backend", RETRIEVAL_VERSION),
            "generator": getattr(self.generator, "model", GENERATOR_VERSION),
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
        generator_status: str,
    ) -> None:
        record = {
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
                "generator_status": generator_status,
                "retriever_backend": self.retriever.backend,
                "retriever_status": self.retriever.status,
                "generator_backend": self.generator.backend,
                "generator_provider": self.generator.provider,
                "generator_model": self.generator.model,
                "versions": self._versions(),
        }
        try:
            self.audit.write(record)
        except Exception:
            self.metrics.increment("audit_failures_total")
            raise

    def process(self, ticket: Ticket) -> dict[str, object]:
        self.metrics.increment("requests_total")
        request_id = self._request_id(ticket)
        normalized = normalize_text(ticket.text)
        risk = assess_risk(normalized)

        if risk.status == "hard_risk":
            self.metrics.increment("hard_risk_total")
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
                generator_status="not_called",
            )
            result = {
                "request_id": request_id,
                "topic": "security",
                "route": "human_operator",
                "risk": risk.status,
                "reason": risk.reason,
                "decision": "needs_review",
                "generator_called": False,
                "generator_status": "not_called",
                "retriever_backend": self.retriever.backend,
                "retriever_status": self.retriever.status,
                "generator_provider": self.generator.provider,
                "generator_model": self.generator.model,
            }
            self.metrics.increment("needs_review_total")
            return result

        classification = classify_topic(risk.sanitized_text)
        if classification.confidence < LOCAL_DECISION_BOUNDARY:
            return self._review_result(
                request_id, ticket, classification, "low_confidence"
            )

        self.metrics.increment("retrieval_calls_total")
        evidence = self.retriever.retrieve(risk.sanitized_text)
        if self.retriever.status.startswith("fallback:"):
            self.metrics.increment("retrieval_fallback_total")
        if evidence is None or evidence.score < MIN_RETRIEVAL_SCORE:
            return self._review_result(
                request_id, ticket, classification, "insufficient_evidence"
            )

        try:
            # Внешний адаптер получает только PII-санитизированный текст и одну approved KB-статью.
            self.metrics.increment("generator_calls_total")
            started = time.monotonic()
            draft = self.generator.generate(risk.sanitized_text, evidence)
        except GeneratorUnavailable:
            self.metrics.increment("generator_failures_total")
            return self._review_result(
                request_id,
                ticket,
                classification,
                "generator_unavailable",
                evidence=evidence,
                generator_status="unavailable",
            )
        finally:
            if "started" in locals():
                self.metrics.observe_generator_latency((time.monotonic() - started) * 1000)
        generator_called = True
        deterministic_grounding = self.generator.backend == "deterministic"
        if not self._generation_gate(
            draft, evidence, risk.status, deterministic_grounding
        ):
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
            generator_status=self.generator.status,
        )
        result = {
            "request_id": request_id,
            "topic": classification.topic,
            "route": classification.route,
            "risk": risk.status,
            "confidence": classification.confidence,
            "evidence": [evidence.document_id],
            "evidence_scores": {evidence.document_id: evidence.score},
            "decision": "draft_ready",
            "draft": draft,
            "generator_called": generator_called,
            "retriever_backend": self.retriever.backend,
            "retriever_status": self.retriever.status,
            "generator_provider": self.generator.provider,
            "generator_model": self.generator.model,
        }
        self.metrics.increment("draft_ready_total")
        return result

    def _review_result(
        self,
        request_id: str,
        ticket: Ticket,
        classification: Classification,
        reason: str,
        *,
        evidence: RetrievedEvidence | None = None,
        generator_called: bool = False,
        generator_status: str = "not_called",
    ) -> dict[str, object]:
        self._write_audit(
            request_id=request_id,
            ticket=ticket,
            topic=classification.topic,
            route="human_operator",
            risk_status="safe",
            risk_reason=None,
            confidence=classification.confidence,
            evidence_ids=[evidence.document_id] if evidence else [],
            decision="needs_review",
            escalation_reason=reason,
            generator_status=generator_status,
        )
        result = {
            "request_id": request_id,
            "topic": classification.topic,
            "route": "human_operator",
            "risk": "safe",
            "confidence": classification.confidence,
            "decision": "needs_review",
            "reason": reason,
            "generator_called": generator_called,
            "generator_status": generator_status,
            "retriever_backend": self.retriever.backend,
            "retriever_status": self.retriever.status,
            "generator_provider": self.generator.provider,
            "generator_model": self.generator.model,
        }
        if evidence:
            result["evidence"] = [evidence.document_id]
            result["evidence_scores"] = {evidence.document_id: evidence.score}
        self.metrics.increment("needs_review_total")
        return result

    @staticmethod
    def _generation_gate(
        draft: str,
        evidence: RetrievedEvidence | None,
        risk_status: str,
        deterministic_grounding: bool,
    ) -> bool:
        if not (risk_status == "safe" and evidence and evidence.evidence and draft):
            return False
        if deterministic_grounding:
            return grounding_gate(draft, evidence, risk_status)
        # Для внешней LLM это только boundary PoC: evidence обязательно,
        # но семантическая обоснованность требует отдельной production-оценки.
        return True
