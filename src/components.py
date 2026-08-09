from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Classification, RetrievedEvidence, RiskAssessment


RULES_VERSION = "rules-v1"
CLASSIFIER_VERSION = "keyword-router-v1"
RETRIEVAL_VERSION = "token-overlap-v1"
GENERATOR_VERSION = "deterministic-template-v1"
LOCAL_DECISION_BOUNDARY = 0.60
MIN_RETRIEVAL_SCORE = 0.20

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)[\s()-]*\d{3}[\s()-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)")
_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)

_RISK_MARKERS = {
    "account_compromise": (
        "аккаунт взломали",
        "взломали аккаунт",
        "аккаунт взломан",
        "несанкционированный вход",
        "сторонний доступ",
        "украли аккаунт",
        "account hacked",
        "unauthorized access",
    ),
}

_TOPIC_KEYWORDS = {
    "account_access": {"пароль", "восстановить", "войти", "аккаунт", "login", "password"},
    "payment_status": {"платеж", "платёж", "оплата", "оплатить", "карта", "payment"},
    "service_outage": {"сбой", "неработает", "недоступен", "ошибка", "outage"},
    "subscription": {"подписка", "отменить", "отмена", "продление", "subscription"},
}

_ROUTES = {
    "account_access": "self_service",
    "payment_status": "billing",
    "service_outage": "incident",
    "subscription": "retention",
}


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def sanitize_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return _PHONE_RE.sub("[PHONE_REDACTED]", text)


def assess_risk(text: str) -> RiskAssessment:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    for reason, markers in _RISK_MARKERS.items():
        if any(marker in lowered for marker in markers):
            return RiskAssessment("hard_risk", reason, sanitize_pii(normalized))
    return RiskAssessment("safe", None, sanitize_pii(normalized))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def classify_topic(text: str) -> Classification:
    tokens = _tokens(text)
    scores = {
        topic: len(tokens.intersection(keywords))
        for topic, keywords in _TOPIC_KEYWORDS.items()
    }
    topic, top_score = max(scores.items(), key=lambda item: item[1])
    ordered_scores = sorted(scores.values(), reverse=True)
    margin = ordered_scores[0] - ordered_scores[1]
    if top_score == 0 or margin == 0:
        return Classification("unknown", "human_operator", 0.20, CLASSIFIER_VERSION)

    # Это демонстрационный score для fixture, а не calibrated production probability.
    confidence = min(0.95, 0.55 + 0.12 * top_score + 0.04 * margin)
    return Classification(topic, _ROUTES[topic], round(confidence, 2), CLASSIFIER_VERSION)


def load_kb(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def retrieve(text: str, documents: list[dict[str, object]]) -> RetrievedEvidence | None:
    query_tokens = _tokens(text)
    if not query_tokens:
        return None

    candidates: list[RetrievedEvidence] = []
    for document in documents:
        searchable = " ".join(
            [
                str(document["title"]),
                " ".join(str(keyword) for keyword in document["keywords"]),
                str(document["evidence"]),
            ]
        )
        overlap = query_tokens.intersection(_tokens(searchable))
        score = round(len(overlap) / len(query_tokens), 3)
        candidates.append(
            RetrievedEvidence(
                str(document["id"]),
                str(document["title"]),
                score,
                str(document["evidence"]),
            )
        )

    return max(candidates, key=lambda candidate: candidate.score)


class DeterministicGenerator:
    """Локальная замена асинхронного LLM-адаптера для PoC."""

    version = GENERATOR_VERSION

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, evidence: RetrievedEvidence) -> str:
        self.calls += 1
        return (
            f"Черновик PoC по статье «{evidence.title}»: "
            f"{evidence.evidence}"
        )


def grounding_gate(
    draft: str,
    evidence: RetrievedEvidence | None,
    risk_status: str,
) -> bool:
    return bool(
        risk_status == "safe"
        and evidence
        and evidence.evidence
        and evidence.evidence in draft
    )
