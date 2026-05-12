import os
import json
import re
from pathlib import Path
import csv
import httpx
from openai import OpenAI
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv()

def variable_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_variables):

    system_instruction = """
    You are a policy variable extraction agent.

    Input:
    - A trusted list of system variables (names must not be modified).
    - A JSON array of guidance items.
    Each item contains:
    - guidance text
    - common_constraints
    - allow_conditions
    - disallow_conditions

    Task:
    For EACH guidance item, extract the minimal set of system and prompt variables that affect allow/disallow decisions.

    Rules:
    1) System variables:
    - You may ONLY select variable names from the provided system_variable_list.
    - Do NOT rename, modify, or invent system variable names.
    - Only include system variables that are actually required for decision logic.

    2) Prompt variables:
    - Define new variables only if necessary, include variable types e.g., int, string etc.
    - Prompt variables represent user input semantics (scope, target, amount, domain relevance, etc.).
    - Do NOT include action_type (it is already provided elsewhere).

    3) You should not give each variable a value at this time, just list variable names.
    4) For each guidance item, return its system variable names and prompt variable names.

    Output: your output should be a list of json data. Each json maps to each guidance item, should only include its system variable names and prompt variable names.

    Output format example: 

    [
        {
            "system_variables": a list of system variables,
            "prompt_variables": a list of prompt variables
        }
    ]

    """
    guidances={}
    with open(output_file_decompose, 'r') as f:
        guidances=json.load(f)
    print(system_variables)
    del system_variables["action_list"]
    del system_variables["action_description"]
    user_instruction = f"""
    System variable list: {system_variables}

    Guidance items: {str(guidances)}
    """
    # Initialize OpenAI client
    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)


    print("Sending guidance for variable extraction...")
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
        for i in range(len(issues_list)):
            guidances[i]["system_variables"]=issues_list[i]["system_variables"]
            guidances[i]["prompt_variables"]=issues_list[i]["prompt_variables"]
        with open(output_file_variables, 'w') as f:
            json.dump(guidances, f, indent=4)

    except json.JSONDecodeError as e:
        print("Error parsing LLM output:", e)
        print("LLM output was:", llm_output)

    return guidances


if __name__ == "__main__":
    print("run pipeline please")