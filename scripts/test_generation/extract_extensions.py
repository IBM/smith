"""
Extract extension variable values from test case prompts using LLM.

Reads extension_variables.json (produced by the policy creation skill)
and for each test case, uses an LLM to extract the values of those extension
variables from the user's input prompt.

Only handles extensions — NOT system variables (already in test cases)
and NOT MCP tool arguments (handled by process_test_batch.py).
"""

import os
import json
import glob
from openai import OpenAI


def build_prompt(user_input: str, extension_vars: list, existing_subject: dict) -> str:
    """Build LLM prompt to extract extension values from user input."""
    var_descriptions = []
    for var in extension_vars:
        path = var["path"]
        field_name = path.split(".")[-1]
        if field_name in existing_subject:
            continue
        desc = f"- {path} ({var['type']})"
        if var.get("candidates"):
            desc += f" — possible values: {var['candidates']}"
        if var.get("reason"):
            desc += f" — {var['reason']}"
        var_descriptions.append(desc)

    if not var_descriptions:
        return None

    return f"""Given the user input below, extract values for the following extension variables.
These are contextual variables that can be inferred from what the user is asking.

User Input: "{user_input}"

Extension variables to extract:
{chr(10).join(var_descriptions)}

Instructions:
- Only extract values that can be clearly inferred from the user input.
- If a value cannot be determined, use null.
- For list types, return a JSON array.
- For string types, return the exact value.

Respond ONLY with a JSON object mapping the full path to the extracted value:
{{
    "<path>": <value_or_null>,
    ...
}}
"""


def extract_extensions_for_case(client, model: str, user_input: str, extension_vars: list, existing_subject: dict, temp: float, top_p: float) -> dict:
    """Use LLM to extract extension values for one test case."""
    prompt = build_prompt(user_input, extension_vars, existing_subject)
    if prompt is None:
        return {}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract contextual variable values from user prompts. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=temp,
            top_p=top_p,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        return json.loads(content)

    except Exception as e:
        print(f"  Warning: extraction failed for '{user_input[:50]}...': {e}")
        return {}


def apply_extensions_to_case(test_case: dict, extracted: dict) -> dict:
    """Apply extracted extension values into the test case's extensions."""
    for path, value in extracted.items():
        if value is None:
            continue
        parts = path.replace("input.", "").split(".")
        target = test_case["input"]["extensions"]
        for part in parts[:-1]:
            if part == "extensions":
                continue
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

    return test_case


def run_extract_extensions(api_key, openai_base_url, model, temp, top_p, test_path, extension_vars_file):
    """Main function to extract extensions for all test cases."""
    client = OpenAI(api_key=api_key, base_url=openai_base_url)

    if not os.path.exists(extension_vars_file):
        print(f"No extension_variables.json found at {extension_vars_file}, skipping extension extraction.")
        return

    with open(extension_vars_file, "r") as f:
        content = f.read().strip()
        if not content or content in ("{}", "[]"):
            print("extension_variables.json is empty, skipping extension extraction.")
            return
        data = json.loads(content)
    extension_vars = data.get("extension_variables", [])

    if not extension_vars:
        print("No extension variables to extract. Exiting.")
        return

    print(f"Extension variables to extract: {len(extension_vars)}")
    for var in extension_vars:
        print(f"  {var['path']} — {var.get('reason', '')}")

    labels = ["allow", "disallow"]
    total_processed = 0
    total_enriched = 0

    for label in labels:
        label_path = os.path.join(test_path, label, "*")
        files = sorted(glob.glob(label_path))
        print(f"\nProcessing {len(files)} {label} cases...")

        for file_path in files:
            with open(file_path, "r") as f:
                test_case = json.load(f)

            user_input = test_case["input"]["extensions"]["agent"]["input"]
            existing_subject = test_case["input"]["extensions"].get("subject", {})

            extracted = extract_extensions_for_case(client, model, user_input, extension_vars, existing_subject, temp, top_p)
            total_processed += 1

            if extracted and any(v is not None for v in extracted.values()):
                test_case = apply_extensions_to_case(test_case, extracted)
                total_enriched += 1
                with open(file_path, "w") as f:
                    json.dump(test_case, f, indent=4)

    print(f"\nDone. Processed: {total_processed}, Enriched with extensions: {total_enriched}")
