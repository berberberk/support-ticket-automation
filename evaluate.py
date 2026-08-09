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
    predicted_hard_risk = [
        (case, result) for case, result in results if result["risk"] == "hard_risk"
    ]
    true_positive = sum(
        case["expected_risk"] == "hard_risk" for case, _ in predicted_hard_risk
    )
    false_positive = sum(
        case["expected_risk"] != "hard_risk" for case, _ in predicted_hard_risk
    )
    false_negative = sum(
        case["expected_risk"] == "hard_risk" and result["risk"] != "hard_risk"
        for case, result in results
    )
    true_negative = sum(
        case["expected_risk"] != "hard_risk" and result["risk"] != "hard_risk"
        for case, result in results
    )

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
        "RISK: expected_hard_risk={} TP={} FP={} FN={} TN={} precision={} recall={}".format(
            len(hard_risk),
            true_positive,
            false_positive,
            false_negative,
            true_negative,
            _ratio(true_positive, true_positive + false_positive),
            _ratio(true_positive, true_positive + false_negative),
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

    mismatches = []
    for case, result in results:
        issues = []
        if case["expected_topic"] and result["topic"] != case["expected_topic"]:
            issues.append(
                "topic: expected={} actual={} stage=classification".format(
                    case["expected_topic"], result["topic"]
                )
            )
        if result["risk"] != case["expected_risk"]:
            issues.append(
                "risk: expected={} actual={} stage=risk_rules reason={}".format(
                    case["expected_risk"], result["risk"], result.get("reason")
                )
            )
        if result["decision"] != case["expected_decision"]:
            issues.append(
                "decision: expected={} actual={} stage=decision reason={}".format(
                    case["expected_decision"], result["decision"], result.get("reason")
                )
            )
        if case["expected_evidence_id"]:
            actual_evidence = result.get("evidence", [None])[0]
            if actual_evidence != case["expected_evidence_id"]:
                issues.append(
                    "evidence: expected={} actual={} stage=retrieval reason={}".format(
                        case["expected_evidence_id"], actual_evidence, result.get("reason")
                    )
                )
        if issues:
            mismatches.append((case["id"], issues))

    print("MISMATCHES:")
    if not mismatches:
        print("  none")
    for case_id, issues in mismatches:
        print(f"  {case_id}:")
        for issue in issues:
            print(f"    {issue}")


if __name__ == "__main__":
    main()
