import os
import json
import re
from pathlib import Path
import httpx
from openai import OpenAI
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from policy_agent.policy_analysis.model_output_schema.schema import PolicyIssue, PolicyAnalysisReport

load_dotenv()



def detect_redundant_rules(api_key, output_dir, openai_base_url, policy_path, model, temp, top_p):
    """
    Detect redundant or subsumed rules in an OPA Rego policy using the LLM.
    Saves structured JSON and Markdown reports.
    """

    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    with open(policy_path, "r", encoding="utf-8") as f:
        rego_policy = f.read()

    # Generate schema JSON dynamically from Pydantic model
    rule_issue_schema = PolicyIssue.model_json_schema()
    schema_json_str = json.dumps(rule_issue_schema, indent=2)

    system_instruction = f"""
You are a code linting assistant specialized in OPA Rego policies.
I will provide you with a complete Rego policy.

Your task is to detect rules that are **redundant or subsumed**, meaning they never introduce any new behavior or logic not already handled by earlier rules.

---

### Acceptance Criteria

**Redundant/Subsumed Rules**
- Analyze the logical order of rules in the policy (top-down evaluation).
- Identify rules whose effect is entirely covered by earlier rules.
- Detect partially redundant rules where some conditions overlap with earlier rules.
- For each redundant rule, provide:
  - Rule name and location (line numbers or section).
  - Reason for redundancy (what earlier rule(s) already cover this logic).
  - Clear recommendation (e.g., "Remove redundant rule", "Merge with Rule1").
  - Severity: low, medium, high, or critical based on impact on policy correctness.

**Special Case: Rule Chains**
- If rules form a dependency chain like Rule1 -> Rule2 -> Rule3:
  - Only flag a rule as redundant if all logic it can execute is already fully handled by preceding rules in the chain.
  - Explain which part of the rule is covered and why it is unnecessary.

**General Requirements**
- Focus only on semantic and logical redundancy.
- Ignore formatting, style, or syntactic issues.
- Ensure the evaluation respects OPA's rule evaluation order.

---

Output JSON must strictly follow the schema below (derived from the Pydantic PolicyIssue model):

{schema_json_str}

Wrap all detected redundant rules in a JSON array. Each element must follow the PolicyIssue schema.
Output only JSON. Do NOT include explanations, Markdown, or extra text.
"""

    # Initialize OpenAI client
    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    print("Sending policy to model for redundant rule detection...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": rego_policy}
        ],
        max_tokens=30000,
        temperature=temp,
        top_p=top_p
    )

    llm_output = response.choices[0].message.content.strip()

    # Extract JSON block if wrapped in ```json ... ```
    match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
    if match:
        llm_output = match.group(1).strip()

    # Parse JSON into Pydantic models
    try:
        issues_list = json.loads(llm_output)
        issues_list_with_category = []
        for i in issues_list:
            i["category"] = "redundant"
            issues_list_with_category.append(PolicyIssue(**i))
        report = PolicyAnalysisReport(issues=issues_list_with_category)
    except json.JSONDecodeError as e:
        print("Error parsing LLM output:", e)
        print("LLM output was:", llm_output)
        report = PolicyAnalysisReport(issues=[])

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save structured JSON
    json_file = os.path.join(output_dir, "linting_feedback_de-duplication.json")
    Path(json_file).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Structured JSON saved to {json_file}")

    # Save Markdown for readability (table-free)
    md_file = os.path.join(output_dir, "linting_feedback_de-duplication.md")
    Path(md_file).write_text(report.to_markdown(), encoding="utf-8")
    print(f"Markdown report saved to {md_file}")

    return report


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("MODEL")
    base_url = os.getenv("BASE_URL")
    copy_save_dir = os.getenv("DATA_DIR")
    policy_dir = base_url + os.getenv("POLICY_DIR")
    policy_path = policy_dir + os.getenv("POLICY_PATH")
    output_dir = os.path.join(base_url, copy_save_dir, "outputs")

    detect_redundant_rules(api_key, output_dir, openai_base_url, policy_path, model)
