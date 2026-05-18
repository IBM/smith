import os
import json
import re
import httpx
from openai import OpenAI
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv()

def group_guidance_by_tool(guidancies, system_variables):
    new_guidance={}
    for guidance in guidancies:
        print(guidance)
        print(guidance['action'])
        # exit()
        tool_name=guidance["action"]
        guidance_text=guidance["guidance"]
        if tool_name not in new_guidance.keys():
            new_guidance[tool_name]={}
            new_guidance[tool_name]["guidance_list"]=[]
        new_guidance[tool_name]["action"]=tool_name
        new_guidance[tool_name]["action_description"]=system_variables["action_description"][tool_name]
        new_guidance[tool_name]["guidance_list"].append(guidance_text)
    return new_guidance

def grey_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_grey_guidances, batch_processing=False, batch_size=10):

    system_instruction = """

You are a Senior Security Logic Auditor specializing in LLM Security.

Inputs are:

1. A list of system variables and their potential/default values.
2. A list of JSON objects, each JSON contains:
    a. The target tool name and tool description
    b. All guidances for this tool.

Task:
Perform a "Negative Space Analysis." Identify every combination of system Variable + Tool that is NOT explicitly mentioned in the Guidance. You only examine system variables that are related to this tool call and ignore others.

Output Requirements, for each JSON:

1. Contextual Vacuums: Identify grey scenarios where a rule depends on a condition (e.g., "manager can buy product") but fails to define the "Else" state (e.g., "Can employees buy a product and how much they can spend?").

2. Synthesized Specific Grey guidances based on grey scenarios: Write 5 "Hidden Assumptions" the LLM might make (e.g., "Employee can buy product over 1000$", "Employee cannot buy product over 1000$").

Output format example:

[
    {
        "action": "purchase",
        "grey scenario": Can employees buy a product and how much they can spend?,
        "grey guidances": [
        "employee can purchase product over 1000$",
        "employee cannot buy a product"
        ]
    }
]

"""
    guidances={}
    with open(output_file_decompose, 'r') as f:
        guidances=json.load(f)
    #group guidances by action type, give action name and description
    guidances=group_guidance_by_tool(guidances, system_variables)

    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    guidance_items = list(guidances.items())

    if batch_processing and len(guidance_items) > batch_size:
        all_results = []
        total_batches = (len(guidance_items) + batch_size - 1) // batch_size
        for i in range(0, len(guidance_items), batch_size):
            batch_items = guidance_items[i:i + batch_size]
            batch_dict = dict(batch_items)
            batch_num = i // batch_size + 1
            print(f"Sending batch {batch_num}/{total_batches} ({len(batch_items)} items) for grey space identification...")

            user_instruction = f"""
System variable list: {system_variables}

Guidance items: {str(batch_dict)}
"""
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_instruction}
                ],
                temperature=temp,
                top_p=top_p
            )

            llm_output = response.choices[0].message.content.strip()
            match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
            if match:
                llm_output = match.group(1).strip()
            try:
                batch_results = json.loads(llm_output)
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
                else:
                    all_results.append(batch_results)
            except json.JSONDecodeError as e:
                print(f"Error parsing LLM output for batch {batch_num}:", e)
                print("Raw output will be skipped for this batch")

        with open(output_file_grey_guidances, 'w') as f:
            json.dump(all_results, f, indent=4)

    else:
        user_instruction = f"""
System variable list: {system_variables}

Guidance items: {str(guidances)}
"""
        print("Sending guidance for grey space identification...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_instruction}
            ],
            temperature=temp,
            top_p=top_p
        )

        llm_output = response.choices[0].message.content.strip()

        # Extract JSON block if wrapped in ```json ... ```
        match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
        if match:
            llm_output = match.group(1).strip()
        try:
            issues_list = json.loads(llm_output)
            with open(output_file_grey_guidances, 'w') as f:
                json.dump(issues_list, f, indent=4)

        except json.JSONDecodeError as e:
            print("Error parsing LLM output:", e)
            print("LLM output was:", llm_output)

    return guidances


if __name__ == "__main__":
    print("run pipeline please")
