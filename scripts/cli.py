from policy_agent.scripts.parse_ast_to_graph import init_graph
from policy_agent.red_feedback.red_feedback import cluster_commands
from policy_agent.policy_analysis.update_policy_analysis import update_policy_analysis_feedback
from policy_agent.policy_evaluation.run_policy_evaluation import run_policy_evaluation
import os
from policy_agent.reduce_improve.detect_redundancy import write_graph_suggestion
from policy_agent.policy_analysis.regal.regal_finder import create_regal_suggestion
from dotenv import load_dotenv
import json
from test_generation.decompose import decompose_guidance
from test_generation.variable_extraction import variable_extraction
from test_generation.attack import attack
from test_generation.case_generation import case_generation
from test_generation.convert_test_case import translate_case
from test_generation.grey_condition import grey_extraction
from test_generation.attack_promptfoo import create_promptfoo_cases
from test_case_evaluation.classify_guidance import classify_promptfoo_cases
from test_case_evaluation.validate_labels import run_validation
from test_case_evaluation.visualization.build_report import build_visualization


load_dotenv()
import argparse

class BlueAgent:
    def __init__(self):
        self.base_url=os.getenv("BASE_URL")
        self.data_dir=self.base_url+os.getenv("DATA_DIR")
        self.user_input_dir=self.base_url+os.getenv("DATA_DIR")+"inputs/"
        self.user_output_dir=self.base_url+os.getenv("DATA_DIR")+"outputs/"

        self.graph_path = self.user_output_dir+os.getenv("GRAPH_PATH")
        self.opa_ast_path = self.user_output_dir+os.getenv("OPA_AST_PATH")
        self.cluster_results=self.user_output_dir+os.getenv("CLUSTER_RESULTS")
        self.cluster_eps=float(os.getenv("CLUSTER_EPS", "0.3"))
        self.cluster_min_samples=int(os.getenv("CLUSTER_MIN_SAMPLES", "2"))

        self.policy_dir=self.base_url+os.getenv("POLICY_DIR")
        self.policy_path = self.policy_dir+os.getenv("POLICY_PATH")

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.MODEL = os.getenv("MODEL_SONNET")
        self.openai_base_url=os.getenv("OPENAI_BASE_URL")
        self.temp=float(os.getenv("TEMP"))
        self.top_p=float(os.getenv("TOP_P"))

        self.regal_suggestion_path=self.user_output_dir+os.getenv("REGAL_SUGGESTION_PATH")
        self.regal_result_output=self.user_output_dir+os.getenv("REGAL_RESULT_OUTPUT")
        self.modified_policy_regal=self.user_output_dir+os.getenv("MODIFIED_POLICY_REGAL")
        self.test_dir=self.base_url+"scripts/"
        self.test_path=self.test_dir+os.getenv("TEST_PATH")
        self.test_results_path=self.test_path+os.getenv("TEST_RESULT_PATH")

        self.modified_policy_deduplicate=self.user_output_dir+os.getenv("MODIFIED_POLICY_DEDUPLICATE")
        self.graph_suggestion_path= self.user_output_dir+os.getenv("GRAPH_SUGGESTION_PATH")
        # shutil.copy(self.user_input_dir+os.getenv("POLICY_PATH"), self.policy_path)
        self.G=init_graph(self.opa_ast_path, self.policy_dir, self.graph_path)
        
    def get_regal_feedback(self):
        print("collecting regal feedbacks")
        return create_regal_suggestion(self.policy_path, self.regal_suggestion_path)
    
    def get_duplication_feedback(self):
        init_graph(self.opa_ast_path, self.policy_dir, self.graph_path)
        results="Below is LLM generated redundancy suggestions: \n"
        results=results+update_policy_analysis_feedback(self.api_key, self.user_output_dir, self.openai_base_url, self.policy_path, self.MODEL, self.temp, self.top_p)
        results=results+"Below is graph generated redundancy suggestions, the nodes are rule names, each subgraph indicates the rules and relations in this subgraph is non reachable thus redundant. \n"
        results=results+write_graph_suggestion(self.graph_path, self.graph_suggestion_path)
        return results
    
    def get_red_feedback(self):
        return '\n'.join(cluster_commands(self.cluster_results, self.test_path, self.cluster_eps, self.cluster_min_samples))
    
    def policy_checking_results(self):
        return run_policy_evaluation(self.test_dir, self.test_results_path)

def generate_test(base_url, system_variables, api_key, openai_base_url, model, temp, top_p, guidance_file, output_file_decompose, output_file_attack, output_file_variables, output_file_attack_csv, test_case_template_file, output_file_ready_cases, output_file_grey_guidances, output_file_attack_promptfoo, test_generation_path, output_file_flatten, output_file_cases, output_promptfoo, case_generation_batch_size, batch_processing=False, batch_size=10, flatten_flag=False):
    flatten_flag=True
    # decompose_guidance(api_key, system_variables, guidance_file, openai_base_url, model, temp, top_p, output_file_decompose, output_file_flatten, flatten_flag, batch_processing, batch_size)
    # grey_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_grey_guidances, batch_processing, batch_size)
    # variable_extraction(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_decompose, output_file_variables, batch_processing, batch_size)
    # case_generation(api_key, system_variables, openai_base_url, model, temp, top_p, output_file_variables, output_file_cases, batch_processing, batch_size=case_generation_batch_size)
    # attack(output_file_cases, output_file_attack, output_file_attack_csv, test_generation_path)
    # create_promptfoo_cases(base_url, output_promptfoo, output_file_attack_promptfoo, test_generation_path)
    translate_case(output_file_cases, test_case_template_file, output_file_ready_cases, output_file_attack, output_file_attack_promptfoo)
    return ''

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    base_url=os.getenv("BASE_URL")
    model = os.getenv("MODEL_SONNET")
    temp=float(os.getenv("TEMP"))
    top_p=float(os.getenv("TOP_P"))
    guidance_file=base_url+os.getenv("GUIDANCE_FILE")
    output_file_decompose=base_url+os.getenv("DECOMP_FILE")
    output_file_attack_csv=base_url+os.getenv("TEST_GENERATION_PATH")+os.getenv("ATTACK_FILE_CSV")
    output_file_attack=base_url+os.getenv("ATTACK_FILE")
    output_file_variables=base_url+os.getenv("VARS_FILE")
    output_file_cases=base_url+os.getenv("CASE_FILE")
    system_var_file=base_url+os.getenv("SYSTEM_VAR_FILE")
    test_case_template_file=base_url+os.getenv("TEST_CASE_TEMPLATE")
    output_file_ready_cases=base_url+os.getenv("FINAL_TEST_CASES")
    output_file_grey_guidances=base_url+os.getenv("GREY_GUIDANCE_FILE")
    output_promptfoo=base_url+os.getenv("PROMPTFOO_OUTPUT_FILE")
    output_file_attack_promptfoo=base_url+os.getenv("ATTACK_FILE_PROMPT")
    test_generation_path=base_url+os.getenv("TEST_GENERATION_PATH")
    system_variables={}
    output_file_flatten=base_url+os.getenv("FLATTEN_FILE")
    batch_processing=os.getenv("BATCH_PROCESSING", "false").lower() == "true"
    batch_size=int(os.getenv("BATCH_SIZE", "10"))
    case_generation_batch_size=int(os.getenv("CASE_GENERATION_BATCH_SIZE", "5"))
    
    with open(system_var_file, encoding="utf-8") as f:
        system_variables = json.load(f)


    parser = argparse.ArgumentParser()
    parser.add_argument('--flag', help='what advices you want to generate?')
    args = parser.parse_args()
    agent=BlueAgent()
    
    load_dotenv()
    if args.flag=="policy_testing":
        agent.policy_checking_results()
    if args.flag=="regal_suggestion":
        results=agent.get_regal_feedback()
        print(results)
    if args.flag=="duplication_suggestion":
        results=agent.get_duplication_feedback()
        print(results)
    if args.flag=="red_suggestion":
        results=agent.get_red_feedback()
    if args.flag=="test_generation":
        generate_test(base_url, system_variables, api_key, openai_base_url, model, temp, top_p, guidance_file, output_file_decompose, output_file_attack, output_file_variables, output_file_attack_csv, test_case_template_file, output_file_ready_cases, output_file_grey_guidances, output_file_attack_promptfoo, test_generation_path, output_file_flatten, output_file_cases, output_promptfoo, case_generation_batch_size, batch_processing, batch_size)
    if args.flag=="test_case_evaluation":
        output_file_classified = base_url + os.getenv("CLASSIFIED_PROMPTFOO_FILE", "references/decomp_attack_file_promptfoo_classified.json")
        top_n = int(os.getenv("CLASSIFY_TOP_N", "3"))
        # Step 1: Classify promptfoo cases to match them to guidance
        classify_promptfoo_cases(api_key, openai_base_url, model, temp, top_p,
                                  output_file_decompose, output_file_attack_promptfoo,
                                  output_file_classified, top_n=top_n)
        # Step 2: Validate labels (Tier 1 rules + Tier 2 NLI + Tier 3 LLM)
        validation_output = base_url + "references/label_validation_results.json"
        tier2_high = float(os.getenv("TIER2_HIGH_THRESHOLD", "0.70"))
        tier2_low = float(os.getenv("TIER2_LOW_THRESHOLD", "0.35"))
        max_llm = os.getenv("MAX_LLM_CALLS", None)
        max_llm_calls = int(max_llm) if max_llm else None

        run_validation(
            test_cases_file=output_file_cases,
            classified_promptfoo_file=output_file_classified,
            output_file=validation_output,
            tier2_high_threshold=tier2_high,
            tier2_low_threshold=tier2_low,
            max_llm_calls=max_llm_calls,
            api_key=api_key,
            openai_base_url=openai_base_url,
            model=model,
            temp=temp,
            top_p=top_p,
        )

        # Step 3: Generate HTML report
        report_output = base_url + "references/test_case_report.html"
        build_visualization(
            output_file_cases,
            output_file_attack,
            output_file_classified,
            validation_output,
            report_output,
        )
        print(f"\nFinal report: {report_output}")


if __name__ == "__main__":
    main()
