
import os
import json
from dotenv import load_dotenv
from decompose import decompose_guidance
from variable_extraction import variable_extraction
from attack import attack
from case_generation import case_generation
from convert_test_case import translate_case
from grey_condition import grey_extraction
from attack_promptfoo import create_promptfoo_cases

load_dotenv()



def generate_test(system_variables, api_key, openai_base_url, model, temp, top_p, guidance_file, output_file_decompose, output_file_attack, output_file_variables, output_file_attack_csv, test_case_template_file, output_file_ready_cases, output_file_grey_guidances, output_file_attack_promptfoo, test_generation_path, output_file_flatten, output_file_cases):
    decompose_guidance(api_key, system_variables, guidance_file, openai_base_url, model, temp, top_p, output_file_decompose, output_file_flatten)
    grey_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_grey_guidances)
    variable_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_variables)
    case_generation(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_variables,output_file_cases)
    attack(output_file_cases, output_file_attack, output_file_attack_csv, test_generation_path)
    create_promptfoo_cases(base_skill_url, output_file_attack_promptfoo, test_generation_path)
    translate_case(output_file_cases, test_case_template_file, output_file_ready_cases, output_file_attack, output_file_attack_promptfoo)
    return ''

if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    base_skill_url=os.getenv("BASE_SKILL_URL")
    model = os.getenv("MODEL_SONNET")
    temp=float(os.getenv("TEMP"))
    top_p=float(os.getenv("TOP_P"))
    guidance_file=base_skill_url+os.getenv("GUIDANCE_FILE")
    output_file_decompose=base_skill_url+os.getenv("DECOMP_FILE")
    output_file_flatten=base_skill_url+os.getenv("FLATTEN_FILE")
    output_file_attack_csv=base_skill_url+os.getenv("TEST_GENERATION_PATH")+os.getenv("ATTACK_FILE_CSV")
    output_file_attack=base_skill_url+os.getenv("ATTACK_FILE")
    output_file_variables=base_skill_url+os.getenv("VARS_FILE")
    output_file_cases=base_skill_url+os.getenv("CASE_FILE")
    system_var_file=base_skill_url+os.getenv("SYSTEM_VAR_FILE")
    test_case_template_file=base_skill_url+os.getenv("TEST_CASE_TEMPLATE")
    output_file_ready_cases=base_skill_url+os.getenv("FINAL_TEST_CASES")
    output_file_grey_guidances=base_skill_url+os.getenv("GREY_GUIDANCE_FILE")
    output_file_attack_promptfoo=base_skill_url+os.getenv("ATTACK_FILE_PROMPT")
    test_generation_path=base_skill_url+os.getenv("TEST_GENERATION_PATH")
    system_variables={}
    with open(system_var_file, encoding="utf-8") as f:
        system_variables = json.load(f)

    generate_test(system_variables, api_key, openai_base_url, model, temp, top_p, guidance_file, output_file_decompose, output_file_attack, output_file_variables, output_file_attack_csv, test_case_template_file, output_file_ready_cases, output_file_grey_guidances, output_file_attack_promptfoo, test_generation_path, output_file_flatten)
