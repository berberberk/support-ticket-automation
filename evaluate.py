#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path

from src.models import Ticket
from src.pipeline import SupportPipeline


ROOT = Path(__file__).parent


def _ratio(correct: int, total: int) -> str:
    return f"{correct / total:.2f}" if total else "n/a"


def main() -> None:
    cases = json.loads((ROOT / "data" / "eval_cases.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as temp_dir:
        pipeline = SupportPipeline(
            ROOT / "data" / "kb.json",
            Path(temp_dir) / "audit.jsonl",
        )
        results = [
            (case, pipeline.process(Ticket(case["text"], ticket_id=case["id"])))
            for case in cases
        ]

    labeled_routing = [(case, result) for case, result in results if case["expected_topic"]]
    routing_correct = sum(
        result["topic"] == case["expected_topic"]
        for case, result in labeled_routing
    )

    hard_risk = [(case, result) for case, result in results if case["expected_risk"] == "hard_risk"]
    true_positive = sum(result["risk"] == "hard_risk" for _, result in hard_risk)
    false_negative = len(hard_risk) - true_positive

    expected_review = [
        (case, result) for case, result in results if case["expected_decision"] == "needs_review"
    ]
    correctly_escalated = sum(result["decision"] == "needs_review" for _, result in expected_review)
    decision_correct = sum(
        result["decision"] == case["expected_decision"]
        for case, result in results
    )

    expected_evidence = [
        (case, result)
        for case, result in results
        if case["expected_evidence_id"]
    ]
    rank_one = sum(
        result.get("evidence", [None])[0] == case["expected_evidence_id"]
        for case, result in expected_evidence
    )

    unsafe_hard_risk_drafts = sum(
        result["decision"] == "draft_ready" or result["generator_called"]
        for _, result in hard_risk
    )

    print("=== PoC SANITY EVALUATION ===")
    print(
        "ROUTING: labeled_cases={} correct={} accuracy={}".format(
            len(labeled_routing), routing_correct, _ratio(routing_correct, len(labeled_routing))
        )
    )
    print(
        "RISK: expected_hard_risk={} true_positives={} false_negatives={} recall={}".format(
            len(hard_risk), true_positive, false_negative, _ratio(true_positive, len(hard_risk))
        )
    )
    print(
        "DECISION/HITL: expected_needs_review={} correctly_escalated={} correctness={}".format(
            len(expected_review), correctly_escalated, _ratio(decision_correct, len(results))
        )
    )
    print(
        "RETRIEVAL: expected_evidence_cases={} rank1={} Hit@1={}".format(
            len(expected_evidence), rank_one, _ratio(rank_one, len(expected_evidence))
        )
    )
    print(
        f"SAFETY: hard-risk automatic drafts={unsafe_hard_risk_drafts} (must be zero)"
    )
    print(
        "NOTE: это fixture-based sanity evaluation детерминированной PoC-логики, "
        "а не оценка production model quality."
    )


if __name__ == "__main__":
    main()
