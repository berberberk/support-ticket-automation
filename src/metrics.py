from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsCollector:
    """Потокобезопасные in-process счётчики PoC без пользовательских данных."""

    _COUNTERS = (
        "requests_total",
        "draft_ready_total",
        "needs_review_total",
        "hard_risk_total",
        "retrieval_calls_total",
        "retrieval_fallback_total",
        "generator_calls_total",
        "generator_failures_total",
        "audit_failures_total",
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[str] = Counter()
        self._generator_latency_ms: list[float] = []

    def increment(self, name: str) -> None:
        if name not in self._COUNTERS:
            raise ValueError(f"Неизвестная метрика: {name}")
        with self._lock:
            self._counters[name] += 1

    def observe_generator_latency(self, milliseconds: float) -> None:
        with self._lock:
            self._generator_latency_ms.append(milliseconds)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            count = len(self._generator_latency_ms)
            average = round(sum(self._generator_latency_ms) / count, 3) if count else 0.0
            return {
                **{name: self._counters[name] for name in self._COUNTERS},
                "generator_latency_ms": {"count": count, "avg": average},
            }
