import os
import json
import re
from pathlib import Path
import httpx
from openai import OpenAI
from dotenv import load_dotenv

# Add src folder to sys.path so imports work from test/
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from policy_agent.policy_analysis.model_output_schema.schema import (
    PolicyIssue,
    PolicyAnalysisReport,
)

load_dotenv()


def cycle_detection(
    api_key, output_dir, openai_base_url, policy_path, model, temp, top_p
):
    """
    Detect cyclic rule dependencies in an OPA Rego policy using the LLM.
    Saves structured JSON and Markdown reports.
    """

    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")
    with open(policy_path, "r", encoding="utf-8") as f:
        rego_policy = f.read()

    schema_json_str = json.dumps(PolicyIssue.model_json_schema(), indent=2)

    system_instruction = """
    You are a code linting assistant specialized in analyzing Open Policy Agent (OPA) Rego policies.
    I will give you a full Rego policy.

    Your task is to detect **cycles in rule references or dependencies** only.

    ---

    ### Acceptance Criteria

    **Cyclic Rule Dependencies**
    - Represent rule dependencies as a directed graph (rule -> dependent rules).
    - Detect direct and indirect cycles (loops).
    - For each cycle, provide:
    - All rules involved.
    - A clear trace/path of the cycle.
    - An optional note explaining why the cycle occurs.
    - Only report cycles. Do NOT include rules that are not part of any cycle.

    **General Requirements**
    - Focus only on semantic and logical rule dependencies.
    - Ignore formatting, style, or syntax issues.

    ---

    Output JSON must strictly follow the schema below (derived from the Pydantic PolicyIssue model):

    {schema_json_str}

    Wrap all detected cycles in a JSON array. Each element must follow the PolicyIssue schema.
    Output only JSON. Do NOT include explanations, Markdown, or extra text.
    """

    # Initialize OpenAI client
    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    print("Sending policy to model for cycle detection...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": rego_policy},
        ],
        temperature=temp,
        top_p=top_p,
    )

    llm_output = response.choices[0].message.content.strip()

    # Remove ```json code blocks if present
    match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
    if match:
        llm_output = match.group(1).strip()

    # Parse JSON into Pydantic models
    try:
        issues_list = json.loads(llm_output)
        cycles = [PolicyIssue(**i) for i in issues_list if i.get("category") == "cycle"]
        report = PolicyAnalysisReport(issues=cycles)
    except json.JSONDecodeError as e:
        print("Error parsing LLM output:", e)
        print("LLM output was:", llm_output)
        report = PolicyAnalysisReport(issues=[])

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save structured JSON (Pydantic v2)
    json_file = os.path.join(output_dir, "linting_feedback_cycle-detection.json")
    Path(json_file).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Structured JSON saved to {json_file}")

    # Save Markdown
    md_file = os.path.join(output_dir, "linting_feedback_cycle-detection.md")
    Path(md_file).write_text(report.to_markdown(), encoding="utf-8")
    print(f"Markdown report saved to {md_file}")

    return report


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("MODEL_SONNET")
    base_url = os.getenv("BASE_URL")
    copy_save_dir = os.getenv("DATA_DIR")
    policy_dir = base_url + os.getenv("POLICY_DIR")
    policy_path = policy_dir + os.getenv("POLICY_PATH")
    output_dir = os.path.join(base_url, copy_save_dir, "outputs")

    cycle_detection(api_key, output_dir, openai_base_url, policy_path, model)
