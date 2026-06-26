# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from collections import defaultdict
from typing import List, Dict, Any


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = {}
    total = len(results)
    if total == 0:
        return {"overall": {"total": 0}}

    correct = sum(1 for r in results if r["verdict"] == "correct")
    incorrect = sum(1 for r in results if r["verdict"] == "incorrect")
    uncertain = sum(1 for r in results if r["verdict"] == "uncertain")

    metrics["overall"] = {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "uncertain": uncertain,
        "accuracy": correct / total,
        "error_rate": incorrect / total,
    }

    metrics["by_source"] = _group_accuracy(results, "source")
    metrics["by_label"] = _group_accuracy(results, "assigned_label")
    metrics["by_guidance"] = _group_accuracy(results, "guidance")
    metrics["confusion_matrix"] = _build_confusion_matrix(results)
    metrics["tier_distribution"] = _count_by(results, "evaluation_tier")

    llm_count = sum(1 for r in results if r["evaluation_tier"] == "llm")
    metrics["llm_escalation_rate"] = llm_count / total

    return metrics


def _group_accuracy(results: List[Dict], key: str) -> Dict[str, Dict]:
    groups = defaultdict(list)
    for r in results:
        groups[r.get(key, "unknown")].append(r)

    output = {}
    for group_name, group_results in groups.items():
        total = len(group_results)
        correct = sum(1 for r in group_results if r["verdict"] == "correct")
        incorrect = sum(1 for r in group_results if r["verdict"] == "incorrect")
        uncertain = sum(1 for r in group_results if r["verdict"] == "uncertain")
        output[group_name] = {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "uncertain": uncertain,
            "accuracy": correct / total if total > 0 else 0,
        }
    return output


def _build_confusion_matrix(results: List[Dict]) -> Dict[str, Dict[str, int]]:
    matrix = defaultdict(lambda: defaultdict(int))
    for r in results:
        assigned = r.get("assigned_label", "unknown")
        predicted = r.get("predicted_label", "unknown")
        matrix[assigned][predicted] += 1
    return {k: dict(v) for k, v in matrix.items()}


def _count_by(results: List[Dict], key: str) -> Dict[str, int]:
    counts = defaultdict(int)
    for r in results:
        counts[r.get(key, "unknown")] += 1
    return dict(counts)


def print_report(metrics: Dict[str, Any]):
    overall = metrics["overall"]
    print(f"\n{'='*60}")
    print("  LABEL VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"  Total cases:  {overall['total']}")
    print(f"  Correct:      {overall['correct']} ({overall['accuracy']:.1%})")
    print(f"  Incorrect:    {overall['incorrect']} ({overall['error_rate']:.1%})")
    print(
        f"  Uncertain:    {overall['uncertain']} ({overall['uncertain']/overall['total']:.1%})"
    )
    print(f"  LLM calls:    {metrics['llm_escalation_rate']:.1%} of cases")

    print("\n  By Source:")
    for src, stats in metrics["by_source"].items():
        print(f"    {src:12s}  accuracy={stats['accuracy']:.1%}  (n={stats['total']})")

    print("\n  By Label:")
    for lbl, stats in metrics["by_label"].items():
        print(f"    {lbl:12s}  accuracy={stats['accuracy']:.1%}  (n={stats['total']})")

    print("\n  Tier Distribution:")
    for tier, count in metrics["tier_distribution"].items():
        print(f"    {tier:12s}  {count} ({count/overall['total']:.1%})")

    print("\n  Confusion Matrix (assigned -> predicted):")
    for assigned, predicted_counts in metrics["confusion_matrix"].items():
        print(f"    {assigned:12s} -> {dict(predicted_counts)}")

    print(f"{'='*60}\n")
