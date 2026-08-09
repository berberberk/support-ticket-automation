from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ticket:
    text: str
    channel: str = "demo"
    ticket_id: str | None = None


@dataclass(frozen=True)
class RiskAssessment:
    status: str
    reason: str | None
    sanitized_text: str


@dataclass(frozen=True)
class Classification:
    topic: str
    route: str
    confidence: float
    component_version: str


@dataclass(frozen=True)
class RetrievedEvidence:
    document_id: str
    title: str
    score: float
    evidence: str
