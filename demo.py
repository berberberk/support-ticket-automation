#!/usr/bin/env python3

import json
from pathlib import Path

from src.models import Ticket
from src.components import DeterministicGenerator
from src.pipeline import SupportPipeline


ROOT = Path(__file__).parent
AUDIT_PATH = ROOT / "runtime" / "audit.jsonl"


def _print_happy(result: dict[str, object]) -> None:
    print("=== HAPPY PATH ===")
    print(f"request_id: {result['request_id']}")
    print(f"topic: {result['topic']}")
    print(f"risk: {result['risk']}")
    print(f"confidence: {result['confidence']} (illustrative PoC score)")
    print(f"evidence: {result['evidence']}")
    print(f"decision: {result['decision']}")
    print(f"draft: {result['draft']}")


def _print_risky(result: dict[str, object]) -> None:
    print("\n=== RISKY PATH ===")
    print(f"request_id: {result['request_id']}")
    print(f"risk: {result['risk']}")
    print(f"decision: {result['decision']}")
    print(f"route: {result['route']}")
    print(f"reason: {result['reason']}")
    print(f"generator_called: {'yes' if result['generator_called'] else 'no'}")


def _print_outage(result: dict[str, object]) -> None:
    print("\n=== GENERATOR OUTAGE ===")
    print(f"request_id: {result['request_id']}")
    print(f"risk: {result['risk']}")
    print(f"evidence: {result['evidence']}")
    print(f"generator: {result['generator_status']}")
    print(f"decision: {result['decision']}")
    print(f"route: {result['route']}")
    print(f"reason: {result['reason']}")


def main() -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("", encoding="utf-8")
    pipeline = SupportPipeline(ROOT / "data" / "kb.json", AUDIT_PATH)

    happy = pipeline.process(
        Ticket("Как восстановить пароль и снова войти в аккаунт?", ticket_id="demo-happy")
    )
    risky = pipeline.process(
        Ticket(
            "Кажется, мой аккаунт взломали: вижу несанкционированный вход.",
            ticket_id="demo-risky",
        )
    )
    outage_pipeline = SupportPipeline(
        ROOT / "data" / "kb.json",
        AUDIT_PATH,
        generator=DeterministicGenerator(available=False),
    )
    outage = outage_pipeline.process(
        Ticket("Как восстановить пароль и снова войти в аккаунт?", ticket_id="demo-outage")
    )

    _print_happy(happy)
    _print_risky(risky)
    _print_outage(outage)
    print(f"\naudit: {AUDIT_PATH}")
    print(f"audit_records: {len(AUDIT_PATH.read_text(encoding='utf-8').splitlines())}")

    records = [
        json.loads(line)
        for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(records) == 3
    assert all("Как восстановить пароль" not in json.dumps(record, ensure_ascii=False) for record in records)
    assert all("Кажется, мой аккаунт" not in json.dumps(record, ensure_ascii=False) for record in records)


if __name__ == "__main__":
    main()
