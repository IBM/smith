# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
import json
import re
import httpx
from openai import OpenAI
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv()


def remove_empty_line(str_list):
    new_str_list = []
    for strr in str_list:
        if len(strr) != 0:
            new_str_list.append(strr)
    return new_str_list


def flatten_guidance(
    api_key,
    guidance_file,
    system_variables,
    openai_base_url,
    model,
    temp,
    top_p,
    output_file_flatten,
):
    guidances = ""
    with open(guidance_file, "r") as f:
        guidances = f.read()

    system_instruction = """
    You are a Guidance Flattening Agent.

    Your task is to rewrite heterogeneous guidance into a simple line-by-line natural-language format.

    The input guidance may be written as paragraphs, bullet lists, tables, headings with sub-items, mixed examples, or policy blocks.

    Your output should be a numbered list of guidance statements.

    Each output line must:
    1. Describe exactly one operation, tool action, or user action.
    2. Include the relevant actor, tool, resource, condition, and allow/deny meaning when available.
    3. Be self-contained, so downstream components can understand the line without reading surrounding context.
    4. Preserve the original meaning as much as possible.
    5. Avoid merging multiple operations into one line.
    6. Carry over contextual headers, such as "Allowed commands", "Disallowed commands", "Managers", "Employees", "Only for internal data", etc., into each relevant line.
    7. If a statement contains multiple operations, split it into multiple lines.
    8. Each line must relate to exactly one action/operation. If a guidance applies to multiple actions, split it into separate lines — one per action. Do not mix multiple actions in a single line.

    Do not generate test cases.
    Do not output JSON.
    Do not explain your reasoning.
    Only output the flattened guidance lines.
    """
    user_instruction = f"""
    Guidances: {guidances}
    """
    # Initialize OpenAI client
    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    print("Sending guidance for flatten...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
        temperature=temp,
        top_p=top_p,
    )

    llm_output = response.choices[0].message.content.strip()
    print("flatten results saved to " + output_file_flatten)
    with open(output_file_flatten, "w") as f:
        f.write(str(llm_output))
    return llm_output


def decompose_guidance(
    api_key,
    system_variables,
    guidance_file,
    openai_base_url,
    model,
    temp,
    top_p,
    output_file_decompose,
    output_file_flatten,
    flatten_flag=True,
    batch_processing=False,
    batch_size=10,
):
    guidances_str = ""
    if flatten_flag:
        guidances_str = flatten_guidance(
            api_key,
            guidance_file,
            system_variables,
            openai_base_url,
            model,
            temp,
            top_p,
            output_file_flatten,
        )
    else:
        with open(guidance_file, "r") as f:
            guidances_str = str(f.read())

    system_instruction = """
    You are a policy decision decomposition agent.

    Given one policy sentence and a global action list, produce:
    * action: choose exactly one action from the action list (no invented actions).
    * common_constraints: scope/preconditions for when this guidance applies (do NOT repeat the action here).
    * allow_conditions: abstract condition statements describing all allowed situations (can be multiple).
    * disallow_conditions: abstract condition statements describing all disallowed situations (can be multiple).

    Rules:
    * Conditions must be abstract (not concrete user utterances, no names, no specific individuals).
    * If the guidance has a threshold (e.g., $300), include boundary coverage in allow/disallow.
    * Keep common constraints separate from allow/disallow.
    * Output must be valid JSON following the schema exactly.
    * If a guidance is purely a deny/block rule (e.g. "No one can do X", "Block all Y"), leave allow_conditions as an empty list []. Do NOT infer allow conditions by negating the disallow condition.
    * If a guidance is purely an allow/permit rule (e.g. "Managers can do X", "Users are allowed to Y"), leave disallow_conditions as an empty list []. Do NOT infer disallow conditions by negating the allow condition.

    Output is a list of JSON, for each guidance, you need to output a JSON, the JSON schema for each JSON is:
    {
    'guidance': string, the original guidance,
    'action': string,
      'common_constraints': [string],
      'allow_conditions': [string],
      'disallow_conditions': [string]
    }

    You MUST provide JSON for each guidance, you cannot skip any guidance.

    Examples of input and output:

    Input example: Employees can only query their own salary data.

    Output example:
    [
    {
    "guidance": "Employees: Query your own salary data only",
    "action": salary_query,
      "common_constraints": [user is an employee],
      "allow_conditions": [employees query their own data],
      "disallow_conditions": [employees query others data]
    }
    ]
    """

    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    guidance_lines = remove_empty_line(guidances_str.split("\n"))

    if batch_processing and len(guidance_lines) > batch_size:
        all_results = []
        total_batches = (len(guidance_lines) + batch_size - 1) // batch_size
        for i in range(0, len(guidance_lines), batch_size):
            batch_lines = guidance_lines[i : i + batch_size]
            batch_num = i // batch_size + 1
            print(
                f"Sending batch {batch_num}/{total_batches} ({len(batch_lines)} items) for decomposition..."
            )

            batch_guidances = "\n".join(batch_lines)
            user_instruction = f"""
    Action list (choose from this list only): {system_variables['action_list']}
    Explaination for actions: {system_variables['action_description']}
    Guidances: {batch_guidances}
    """
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_instruction},
                ],
                temperature=temp,
                top_p=top_p,
            )

            llm_output = response.choices[0].message.content.strip()
            match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
            if match:
                llm_output = match.group(1).strip()
            try:
                batch_results = json.loads(llm_output)
                if not isinstance(batch_results, list):
                    batch_results = [batch_results]
                for j in range(len(batch_results)):
                    result = {}
                    result["guidance"] = (
                        batch_lines[j]
                        if j < len(batch_lines)
                        else batch_results[j].get("guidance", "")
                    )
                    result["action"] = batch_results[j]["action"]
                    result["common_constraints"] = batch_results[j][
                        "common_constraints"
                    ]
                    result["allow_conditions"] = batch_results[j]["allow_conditions"]
                    result["disallow_conditions"] = batch_results[j][
                        "disallow_conditions"
                    ]
                    all_results.append(result)
            except json.JSONDecodeError as e:
                print(f"Error parsing LLM output for batch {batch_num}:", e)
                print("Raw output will be skipped for this batch")

        with open(output_file_decompose, "w") as f:
            json.dump(all_results, f, indent=4)
        return all_results

    else:
        user_instruction = f"""
    Action list (choose from this list only): {system_variables['action_list']}
    Explaination for actions: {system_variables['action_description']}
    Guidances: {guidances_str}
    """
        print("Sending guidance for decomposition...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_instruction},
            ],
            temperature=temp,
            top_p=top_p,
        )

        llm_output = response.choices[0].message.content.strip()

        match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
        if match:
            llm_output = match.group(1).strip()
        try:
            issues_list = json.loads(llm_output)
            guidances = remove_empty_line(guidances_str.split("\n"))
            for i in range(len(issues_list)):
                guidance = guidances[i]
                guidances[i] = {}
                guidances[i]["guidance"] = guidance
                guidances[i]["action"] = issues_list[i]["action"]
                guidances[i]["common_constraints"] = issues_list[i][
                    "common_constraints"
                ]
                guidances[i]["allow_conditions"] = issues_list[i]["allow_conditions"]
                guidances[i]["disallow_conditions"] = issues_list[i][
                    "disallow_conditions"
                ]

            with open(output_file_decompose, "w") as f:
                json.dump(guidances, f, indent=4)

        except json.JSONDecodeError as e:
            print("Error parsing LLM output:", e)
            print("LLM output was:", llm_output)

        return guidances


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("MODEL_SONNET")
    temp = float(os.getenv("TEMP"))
    top_p = float(os.getenv("TOP_P"))
    guidance_file = os.getenv("GUIDANCE_FILE")
    output_file_decompose = os.getenv("DECOMP_FILE")
    output_file_flatten = os.getenv("FLATTEN_FILE")
    output_file_decompose_csv = os.getenv("DECOMP_FILE_CSV")
    batch_processing = os.getenv("BATCH_PROCESSING", "false").lower() == "true"
    batch_size = int(os.getenv("BATCH_SIZE", "10"))
    system_variables = {
        "action_list": ["salary_query", "purchase", "ticket_submit", "other Q&A"],
        "user_role": "manager",
        "user_department": "sales",
        "user_name": "Bob",
    }
    result = decompose_guidance(
        api_key,
        system_variables,
        guidance_file,
        openai_base_url,
        model,
        temp,
        top_p,
        output_file_decompose,
        output_file_flatten,
        batch_processing=batch_processing,
        batch_size=batch_size,
    )

    # print(type(result))
