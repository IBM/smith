# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
import json
from typing import List, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

from smith.test_case_evaluation.tier1_rules import evaluate_tier1
from smith.test_case_evaluation.tier2_semantic import Tier2Evaluator
from smith.test_case_evaluation.tier3_llm_judge import LLMJudge
from smith.test_case_evaluation.metrics import compute_metrics, print_report

load_dotenv()


def normalize_label(label):
    """Normalize labels so malicious variants map to disallow."""
    if label in ("malicious_promptfoo", "malicious"):
        return "disallow"
    return label


@dataclass
class EvalCase:
    index: int
    source: str
    guidance: str
    action: str
    condition: str
    label: str
    user_input: str
    original_user_input: str = ""
    attack_type: str = ""


@dataclass
class ValidationResult:
    case_index: int
    source: str
    guidance: str
    assigned_label: str
    predicted_label: str
    verdict: str
    confidence: float
    evaluation_tier: str
    reason: str


def load_generated_cases(path: str) -> List[EvalCase]:
    with open(path, "r") as f:
        data = json.load(f)
    cases = []
    for i, item in enumerate(data):
        cases.append(
            EvalCase(
                index=i,
                source="generated",
                guidance=item.get("guidance", ""),
                action=item.get("action", ""),
                condition=item.get("condition", ""),
                label=item.get("label", ""),
                user_input=item.get("user_input", ""),
            )
        )
    return cases


def load_promptfoo_cases(classified_path: str) -> List[EvalCase]:
    with open(classified_path, "r") as f:
        data = json.load(f)
    cases = []
    skipped = 0
    for i, item in enumerate(data):
        guidance = item.get("guidance", "general_safety")
        action = item.get("action", "general_safety")
        if guidance == "general_safety" or action == "general_safety":
            skipped += 1
            continue
        cases.append(
            EvalCase(
                index=i,
                source="promptfoo",
                guidance=guidance,
                action=action,
                condition=item.get("llm_reason", ""),
                label=item.get("label", "disallow"),
                user_input=item.get("user_input", ""),
            )
        )
    if skipped:
        print(
            f"  (Skipped {skipped} promptfoo cases matched to 'general_safety' — no specific guidance to validate against)"
        )
    return cases


def run_validation(
    test_cases_file: str,
    classified_promptfoo_file: str,
    output_file: str,
    tier2_high_threshold: float = 0.85,
    tier2_low_threshold: float = 0.60,
    max_llm_calls: Optional[int] = None,
    api_key: str = "",
    openai_base_url: str = "",
    model: str = "",
    temp: float = 0.2,
    top_p: float = 0.9,
):
    print("Loading cases...")
    generated_cases = load_generated_cases(test_cases_file)
    promptfoo_cases = load_promptfoo_cases(classified_promptfoo_file)
    all_cases = generated_cases + promptfoo_cases

    print(f"  Generated: {len(generated_cases)}")
    print(f"  Promptfoo: {len(promptfoo_cases)}")
    print(f"  Total:     {len(all_cases)}")

    results: List[ValidationResult] = []
    tier1_unresolved: List[EvalCase] = []

    # === Tier 1: Rule-based ===
    print("\nRunning Tier 1 (rule-based)...")
    for case in all_cases:
        t1 = evaluate_tier1(case.user_input)
        if t1 is not None:
            verdict = (
                "correct"
                if t1.predicted_label == normalize_label(case.label)
                else "incorrect"
            )
            results.append(
                ValidationResult(
                    case_index=case.index,
                    source=case.source,
                    guidance=case.guidance,
                    assigned_label=case.label,
                    predicted_label=t1.predicted_label,
                    verdict=verdict,
                    confidence=t1.confidence,
                    evaluation_tier="rule",
                    reason=t1.reason,
                )
            )
        else:
            tier1_unresolved.append(case)

    print(f"  Tier 1 resolved: {len(results)}")
    print(f"  Remaining for Tier 2: {len(tier1_unresolved)}")

    # === Tier 2: Embedding + NLI ===
    if tier1_unresolved:
        print("\nRunning Tier 2 (embedding + NLI)...")
        evaluator = Tier2Evaluator()

        # Split by source for different evaluation strategies
        generated_unresolved = [c for c in tier1_unresolved if c.source == "generated"]
        promptfoo_unresolved = [c for c in tier1_unresolved if c.source == "promptfoo"]

        tier2_escalate: List[tuple] = []

        # Evaluate generated cases (condition-based NLI)
        if generated_unresolved:
            print(f"  Evaluating {len(generated_unresolved)} generated cases...")
            gen_results = evaluator.evaluate_generated(
                [c.user_input for c in generated_unresolved],
                [c.condition for c in generated_unresolved],
                [c.guidance for c in generated_unresolved],
                [c.label for c in generated_unresolved],
            )
            for case, t2 in zip(generated_unresolved, gen_results):
                if (
                    t2.confidence >= tier2_high_threshold
                    and t2.predicted_label == normalize_label(case.label)
                ):
                    # High confidence, agrees — correct
                    results.append(
                        ValidationResult(
                            case_index=case.index,
                            source=case.source,
                            guidance=case.guidance,
                            assigned_label=case.label,
                            predicted_label=t2.predicted_label,
                            verdict="correct",
                            confidence=t2.confidence,
                            evaluation_tier="embedding",
                            reason=t2.reason,
                        )
                    )
                elif t2.predicted_label != normalize_label(case.label):
                    # Disagrees with label at any confidence — escalate to LLM for confirmation
                    tier2_escalate.append((case, t2))
                elif t2.confidence <= tier2_low_threshold:
                    tier2_escalate.append((case, t2))
                else:
                    # Low-to-moderate confidence but agrees with label — likely correct
                    results.append(
                        ValidationResult(
                            case_index=case.index,
                            source=case.source,
                            guidance=case.guidance,
                            assigned_label=case.label,
                            predicted_label=t2.predicted_label,
                            verdict="correct",
                            confidence=t2.confidence,
                            evaluation_tier="embedding",
                            reason=t2.reason,
                        )
                    )

        # Evaluate promptfoo cases (guidance-based NLI)
        if promptfoo_unresolved:
            print(f"  Evaluating {len(promptfoo_unresolved)} promptfoo cases...")
            pf_results = evaluator.evaluate_promptfoo(
                [c.user_input for c in promptfoo_unresolved],
                [c.guidance for c in promptfoo_unresolved],
                [c.label for c in promptfoo_unresolved],
            )
            for case, t2 in zip(promptfoo_unresolved, pf_results):
                if (
                    t2.confidence >= tier2_high_threshold
                    and t2.predicted_label == normalize_label(case.label)
                ):
                    # High confidence, agrees — correct
                    results.append(
                        ValidationResult(
                            case_index=case.index,
                            source=case.source,
                            guidance=case.guidance,
                            assigned_label=case.label,
                            predicted_label=t2.predicted_label,
                            verdict="correct",
                            confidence=t2.confidence,
                            evaluation_tier="embedding",
                            reason=t2.reason,
                        )
                    )
                elif t2.predicted_label != normalize_label(case.label):
                    # Disagrees with label at any confidence — escalate to LLM for confirmation
                    tier2_escalate.append((case, t2))
                elif t2.confidence <= tier2_low_threshold:
                    tier2_escalate.append((case, t2))
                else:
                    # Low-to-moderate confidence but agrees with label — likely correct
                    results.append(
                        ValidationResult(
                            case_index=case.index,
                            source=case.source,
                            guidance=case.guidance,
                            assigned_label=case.label,
                            predicted_label=t2.predicted_label,
                            verdict="correct",
                            confidence=t2.confidence,
                            evaluation_tier="embedding",
                            reason=t2.reason,
                        )
                    )

        tier2_resolved = len(tier1_unresolved) - len(tier2_escalate)
        print(f"  Tier 2 resolved: {tier2_resolved}")
        print(f"  Escalating to Tier 3: {len(tier2_escalate)}")
    else:
        tier2_escalate = []

    # === Tier 3: LLM Judge ===
    if tier2_escalate and api_key and openai_base_url and model:
        print(f"\nRunning Tier 3 (LLM judge) on {len(tier2_escalate)} cases...")
        judge = LLMJudge(api_key, openai_base_url, model, temp, top_p)

        for case, t2 in tier2_escalate:
            if max_llm_calls is not None and judge.call_count >= max_llm_calls:
                results.append(
                    ValidationResult(
                        case_index=case.index,
                        source=case.source,
                        guidance=case.guidance,
                        assigned_label=case.label,
                        predicted_label=t2.predicted_label,
                        verdict="uncertain",
                        confidence=t2.confidence,
                        evaluation_tier="embedding",
                        reason=f"LLM budget exhausted. Tier2: {t2.reason}",
                    )
                )
                continue

            try:
                t3 = judge.evaluate(
                    case.user_input, case.guidance, case.action, case.label
                )
                verdict = (
                    "correct"
                    if t3.predicted_label == normalize_label(case.label)
                    else "incorrect"
                )
                results.append(
                    ValidationResult(
                        case_index=case.index,
                        source=case.source,
                        guidance=case.guidance,
                        assigned_label=case.label,
                        predicted_label=t3.predicted_label,
                        verdict=verdict,
                        confidence=t3.confidence,
                        evaluation_tier="embedding & llm",
                        reason=f"Tier2: {t2.reason} | LLM: {t3.reason}",
                    )
                )
            except Exception as e:
                results.append(
                    ValidationResult(
                        case_index=case.index,
                        source=case.source,
                        guidance=case.guidance,
                        assigned_label=case.label,
                        predicted_label=t2.predicted_label,
                        verdict="uncertain",
                        confidence=t2.confidence,
                        evaluation_tier="embedding",
                        reason=f"LLM call failed: {str(e)[:100]}. Tier2: {t2.reason}",
                    )
                )
                print(f"  LLM call failed: {str(e)[:80]}. Falling back to Tier 2.")
                break

        print(f"  LLM calls made: {judge.call_count}")
    elif tier2_escalate:
        print(
            "\nSkipping Tier 3 (no LLM credentials configured). Marking as uncertain."
        )
        for case, t2 in tier2_escalate:
            results.append(
                ValidationResult(
                    case_index=case.index,
                    source=case.source,
                    guidance=case.guidance,
                    assigned_label=case.label,
                    predicted_label=t2.predicted_label,
                    verdict="uncertain",
                    confidence=t2.confidence,
                    evaluation_tier="embedding",
                    reason=f"No LLM configured. Tier2: {t2.reason}",
                )
            )

    # === Metrics & Output ===
    results_dicts = [asdict(r) for r in results]
    metrics = compute_metrics(results_dicts)
    print_report(metrics)

    output = {
        "results": results_dicts,
        "metrics": metrics,
        "config": {
            "tier2_high_threshold": tier2_high_threshold,
            "tier2_low_threshold": tier2_low_threshold,
            "max_llm_calls": max_llm_calls,
            "model": model,
        },
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results written to: {output_file}")

    return output


if __name__ == "__main__":
    base_url = os.getenv("BASE_URL", "")

    test_cases_file = base_url + os.getenv("CASE_FILE", "references/test_cases.json")
    classified_promptfoo_file = base_url + os.getenv(
        "CLASSIFIED_PROMPTFOO_FILE",
        "references/decomp_attack_file_promptfoo_classified.json",
    )
    output_file = base_url + "references/label_validation_results.json"

    api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("MODEL_SONNET", "")
    temp = float(os.getenv("TEMP", "0.2"))
    top_p = float(os.getenv("TOP_P", "0.9"))

    tier2_high = float(os.getenv("TIER2_HIGH_THRESHOLD", "0.70"))
    tier2_low = float(os.getenv("TIER2_LOW_THRESHOLD", "0.35"))
    max_llm = os.getenv("MAX_LLM_CALLS", None)
    max_llm_calls = int(max_llm) if max_llm else None

    run_validation(
        test_cases_file=test_cases_file,
        classified_promptfoo_file=classified_promptfoo_file,
        output_file=output_file,
        tier2_high_threshold=tier2_high,
        tier2_low_threshold=tier2_low,
        max_llm_calls=max_llm_calls,
        api_key=api_key,
        openai_base_url=openai_base_url,
        model=model,
        temp=temp,
        top_p=top_p,
    )
