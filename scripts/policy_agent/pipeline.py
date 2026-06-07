from scripts.parse_ast_to_graph import init_graph
from red_feedback.red_feedback import cluster_commands
from policy_refinement.regal_update import regal_update
from policy_analysis.update_policy_analysis import update_policy_analysis_feedback
from policy_evaluation.run_policy_evaluation import run_policy_evaluation
import os
from reduce_improve.detect_redundancy import write_graph_suggestion
import shutil
from policy_analysis.regal.regal_finder import create_regal_suggestion
from dotenv import load_dotenv
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

def main():

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






if __name__ == "__main__":
    main()
