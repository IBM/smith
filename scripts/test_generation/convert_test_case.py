import json
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv()

data_scope_map={
    "create_ticket": ["ticket_content"], 
    "submit_ticket": ["ticket_content"], 
    "send_email": ["ticket_content"], 
    "ask_for_workpolicy": ["ticket_content"], 
    "return_product": ["ticket_content"], 
    "view_team_compensation": ["ticket_content"], 
    "export_compensation_data": ["ticket_content"], 
    "email_compensation_report": ["ticket_content"], 
    "ask_for_salary": ["ticket_content"], 
    "purchase": ["ticket_content"], 
    "other": ["content"],
    "Promptfoo": ["content"]
}

allow_arg_mapping={
    "view_team_compensation": ["select_fields", "id", "time_range", "format", "include_benefits"],
    "ask_for_salary": ["question"],
    "export_compensation_data": ["select_fields", "id", "format", "time_range", "export_type", "business_justification", "external_sharing"],
    "email_compensation_report": ["destination", "report_data", "external_sharing", "encryption_required"],
    "send_email": ["recipient_email", "subject", "bpdy", "email_content", "attached_file"],
    "create_ticket": ["ticket_content"],
    "submit_ticket": ["ticket_content"],
    "ask_for_workpolicy": ["question"],
    "get_w2_form": [],
    "purchase": ["amount", "product_name", "category", "justification"],
    "return_product": ["amount", "product_name"],
    "export_content_as_file": ["data", "file_name"],
    "set_user_role": ["user_role"],
    "test_purchase_policy": ["amount", "product"],
    "other":[],
    "Promptfoo": []
}


def translate_case(output_file_cases, test_case_template_file, output_file_ready_cases, output_file_attack, output_file_attack_promptfoo):
    test_cases_translated={}
    test_cases_translated["allow"]=[]
    test_cases_translated["disallow"]=[]
    test_cases_translated["malicious"]=[]

    with open(output_file_cases, 'r') as f:
        test_cases=json.load(f)
    
    test_cases=merge_with_ares(test_cases, output_file_attack)
    test_cases=merge_with_promptfoo(test_cases, output_file_attack_promptfoo)
    
    test_case_template={}
    for test_case in test_cases:
        with open(test_case_template_file, 'r') as f:
            test_case_template=json.load(f)
        test_case_template["name"]=test_case["action"]
        test_case_template["extensions"]["agent"]['input']=test_case["user_input"]
        if "user_role" in test_case["system_variables"]:
            test_case_template["extensions"]["subject"]["roles"]=[test_case["system_variables"]["user_role"]]
        if "user_name" in test_case["system_variables"]:
            test_case_template["extensions"]["subject"]["id"]=test_case["system_variables"]["user_name"]
        if "user_team" in test_case["system_variables"]:
            test_case_template["extensions"]["subject"]["teams"]=[test_case["system_variables"]["user_team"]]
        test_cases_translated[test_case["label"]].append(test_case_template)
    
    # for label in test_cases_translated.keys():
    #     for test_case_index in range(len(test_cases_translated[label])):
    #         with open(output_file_ready_cases+label+"/test_case"+str(test_case_index)+".json", 'w') as f:
    #             json.dump(test_cases_translated[label][test_case_index], f, indent=4)
    test_cases=test_case_field_mapping(test_cases_translated, output_file_ready_cases)
    return test_cases

def merge_with_ares(test_cases, output_file_attack):
    with open(output_file_attack, 'r') as f:
        attack_cases=json.load(f)
    for test_cluster in attack_cases:
        
        formatted_test_case={}
        formatted_test_case["action"]=test_cluster["action"]
        formatted_test_case["condition"]=test_cluster["condition"]
        formatted_test_case["system_variables"]=test_cluster["system_variables"]
        formatted_test_case["label"]="malicious"

        for attack_kind in test_cluster["attack_conditions"].keys():
            if len(test_cluster["attack_conditions"][attack_kind])>0:
                for attack_case in test_cluster["attack_conditions"][attack_kind]:
                    formatted_test_case["user_input"]=attack_case
                    test_cases.append(formatted_test_case)

    return test_cases

def merge_with_promptfoo(test_cases, output_file_attack_promptfoo):
    with open(output_file_attack_promptfoo, 'r') as f:
        attack_cases=json.load(f)
    for test_cluster in attack_cases:
        formatted_test_case={}
        formatted_test_case["action"]="Promptfoo"
        formatted_test_case["system_variables"]=test_cluster["system_variables"]
        formatted_test_case["label"]="malicious"
        formatted_test_case["user_input"]=test_cluster["user_input"]
        test_cases.append(formatted_test_case)
    return test_cases

def test_case_field_mapping(test_cases_translated, output_file_ready_cases):
    for condition in test_cases_translated.keys():
        test_cases=test_cases_translated[condition]
        for test_case_index in range(len(test_cases)):
            test_cases[test_case_index]["arguments"]=allow_arg_mapping[test_cases[test_case_index]["name"]]
            test_cases[test_case_index]["extensions"]["object"]["data_scope"]=data_scope_map[test_cases[test_case_index]["name"]]
            test_cases[test_case_index]["extensions"]["subject"]["permissions"]=["write:purchase", "write:return_product", "write:send_email", "read:ask_for_workpolicy", "write:create_ticket", "write:submit_ticket", "read:get_w2_form", "read:ask_for_salary", "write:export_content_as_file"]
            test_cases[test_case_index]["extensions"]["object"]["permissions"]=["write:purchase", "write:return_product", "write:send_email", "read:ask_for_workpolicy", "write:create_ticket", "write:submit_ticket", "read:get_w2_form", "read:ask_for_salary", "write:export_content_as_file"]
            if test_cases[test_case_index]["extensions"]["subject"]["roles"]=="manager":
                test_cases[test_case_index]["extensions"]["subject"]["permissions"]=["write:purchase", "write:return_product", "write:send_email", "read:ask_for_workpolicy", "write:create_ticket", "write:submit_ticket", "read:get_w2_form", "read:ask_for_salary", "write:export_content_as_file"]
                test_cases[test_case_index]["extensions"]["object"]["permissions"].extend(["read:view_team_compensation", "export:file", "read:export_compensation_data", "write:email_compensation_report"])
            test_case_template_final={}
            test_case_template_final["input"]=test_cases[test_case_index]

            with open(output_file_ready_cases+condition+"/test_case"+str(test_case_index)+".json", 'w') as f:
                json.dump(test_case_template_final, f, indent=4)
    print("test case generation finished.")
    return test_cases




