# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from smith.policy_agent.policy_analysis.duplication.update_duplication import (
    detect_redundant_rules,
)
from smith.policy_agent.policy_analysis.cycle_detection.update_cycle_detection import (
    cycle_detection,
)
from smith.policy_agent.policy_analysis.dead_rules.dead_rule_finder import (
    detect_dead_rules,
)


def update_policy_analysis_feedback(
    api_key, output_dir, openai_base_url, policy_path, model, temp, top_p
):
    """
    Run all policy analysis feedbacks (duplication, cycle detection, and dead rule detection)
    in sequence and save their results in the same feedback directory.
    """
    results = ""
    print("\n=== Starting Combined Policy Analysis Feedback ===\n")

    # Run duplication analysis
    print("Running duplication feedback...")
    results = (
        results
        + detect_redundant_rules(
            api_key, output_dir, openai_base_url, policy_path, model, temp, top_p
        ).to_markdown()
    )
    print("Duplication feedback complete.\n")

    # Run cycle detection
    print("Running cycle detection feedback...")
    results = (
        results
        + cycle_detection(
            api_key, output_dir, openai_base_url, policy_path, model, temp, top_p
        ).to_markdown()
    )
    print("Cycle detection feedback complete.\n")

    # Run dead rule detection
    print("Running dead rule detection feedback...")
    results = (
        results
        + detect_dead_rules(
            api_key, output_dir, openai_base_url, policy_path, model, temp, top_p
        ).to_markdown()
    )
    print("Dead rule detection feedback complete.\n")

    print("\n=== All Policy Analysis Completed ===\n")
    return results
