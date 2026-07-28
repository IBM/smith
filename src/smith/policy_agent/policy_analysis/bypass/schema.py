# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel
from typing import List, Optional, Literal


class BypassVector(BaseModel):
    """A single divergence between the guidance (intent) and the policy.

    A bypass vector is an input shape where the policy's decision disagrees with
    what the guidance intends — either the policy wrongly permits a request the
    guidance forbids, or wrongly blocks one the guidance allows.
    """

    # The mechanism by which the policy diverges from the guidance.
    category: Literal[
        "omitted_field",
        "type_confusion",
        "malformed_value",
        "keyword_evasion",
    ]
    direction: Literal["guidance_deny_policy_allow", "guidance_allow_policy_deny"]
    guidance_rule: Optional[str] = None
    rules_involved: Optional[List[str]] = None
    field: Optional[str] = None
    reason: Optional[str] = None
    exploit_strategy: Optional[str] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None


class BypassReport(BaseModel):
    vectors: List[BypassVector] = []

    def to_markdown(self) -> str:
        md_lines = ["# Policy Bypass Analysis Report\n\n"]
        if not self.vectors:
            md_lines.append("> No bypass vectors detected.\n")
        else:
            for idx, v in enumerate(self.vectors, 1):
                md_lines.append(f"### Vector {idx}\n")
                md_lines.append(f"- **Category:** {v.category}\n")
                md_lines.append(f"- **Direction:** {v.direction}\n")
                md_lines.append(f"- **Guidance Rule:** {v.guidance_rule or '-'}\n")
                md_lines.append(
                    f"- **Policy Rules Involved:** "
                    f"{', '.join(v.rules_involved) if v.rules_involved else '-'}\n"
                )
                md_lines.append(f"- **Field:** {v.field or '-'}\n")
                md_lines.append(f"- **Reason:** {v.reason or '-'}\n")
                md_lines.append(
                    f"- **Exploit Strategy:** {v.exploit_strategy or '-'}\n"
                )
                md_lines.append(f"- **Severity:** {v.severity or '-'}\n")
                md_lines.append("\n")
        return "".join(md_lines)
