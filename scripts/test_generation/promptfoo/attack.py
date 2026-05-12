import subprocess
import yaml
import os
from dotenv import load_dotenv
load_dotenv()
base_url=str(os.getenv("BASE_SKILL_URL"))

def run_attack():
    promptfoo_config=str(os.getenv("PROMPTFOO_CONFIG_FILE"))
    promptfoo_config=base_url+promptfoo_config
    try:
        result=subprocess.run(["promptfoo", "redteam", "run", "--config", promptfoo_config], cwd="./", check=True)
    except subprocess.CalledProcessError:
        print("promptfoo finished")
    print("PROMPTFOO ATTACK FINISHED........")

def read_test_cases():
    promptfoo_output=str(os.getenv("PROMPTFOO_OUTPUT_FILE"))
    with open(base_url+promptfoo_output) as f:
        data=yaml.safe_load(f)
    print(data.keys())

if __name__ == "__main__":
    run_attack()
    read_test_cases()
