# model_output_schema/schema.py
from pydantic import BaseModel
from typing import List, Optional, Literal


class PolicyIssue(BaseModel):
    """
    Represents a single policy issue:
    - cycle
    - redundant/subsumed
    - dead/unreferenced rule
    """

    category: Literal["cycle", "redundant", "dead"]
    cycle_id: Optional[int] = None
    rule_name: Optional[str] = None
    location: Optional[str] = None
    reason: Optional[str] = None
    recommendation: Optional[str] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    rules_involved: Optional[List[str]] = None
    cycle_path: Optional[str] = None
    note: Optional[str] = None


class PolicyAnalysisReport(BaseModel):
    issues: List[PolicyIssue] = []

    def to_markdown(self) -> str:
        """
        Convert the report to Markdown format including all fields.
        """
        md_lines = ["# Policy Analysis Report\n\n"]
        if not self.issues:
            md_lines.append("> No issues detected.\n")
        else:
            for idx, issue in enumerate(self.issues, 1):
                md_lines.append(f"### Issue {idx}\n")
                md_lines.append(f"- **Category:** {issue.category}\n")
                md_lines.append(f"- **Cycle ID:** {issue.cycle_id or '-'}\n")
                md_lines.append(f"- **Rule Name:** {issue.rule_name or '-'}\n")
                md_lines.append(f"- **Location:** {issue.location or '-'}\n")
                md_lines.append(f"- **Reason:** {issue.reason or '-'}\n")
                md_lines.append(
                    f"- **Recommendation:** {issue.recommendation or '-'}\n"
                )
                md_lines.append(f"- **Severity:** {issue.severity or '-'}\n")
                md_lines.append(
                    f"- **Rules Involved:** {', '.join(issue.rules_involved) if issue.rules_involved else '-'}\n"
                )
                md_lines.append(f"- **Cycle Path:** {issue.cycle_path or '-'}\n")
                md_lines.append(f"- **Note:** {issue.note or '-'}\n")
                md_lines.append("\n")  # blank line between issues
        return "".join(md_lines)
