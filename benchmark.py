#!/usr/bin/env python3
"""Локальный микрозамер детерминированного горячего пути; не нагрузочный тест production."""

from __future__ import annotations

import math
import time

from src.components import assess_risk, classify_topic, normalize_text


REQUESTS = 1_000
TICKET_TEXT = "Не могу войти в аккаунт, как восстановить пароль?"


def percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percent / 100) - 1)
    return ordered[index]


def main() -> None:
    samples_ms: list[float] = []
    started = time.perf_counter()
    for _ in range(REQUESTS):
        request_started = time.perf_counter()
        normalized = normalize_text(TICKET_TEXT)
        risk = assess_risk(normalized)
        classify_topic(risk.sanitized_text)
        samples_ms.append((time.perf_counter() - request_started) * 1000)
    elapsed = time.perf_counter() - started

    print("Local PoC microbenchmark; not a production load test.")
    print(f"requests: {REQUESTS}")
    print(f"elapsed_seconds: {elapsed:.6f}")
    print(f"throughput_requests_per_second: {REQUESTS / elapsed:.2f}")
    print(f"p50_ms: {percentile(samples_ms, 50):.4f}")
    print(f"p95_ms: {percentile(samples_ms, 95):.4f}")
    print(f"p99_ms: {percentile(samples_ms, 99):.4f}")


if __name__ == "__main__":
    main()
