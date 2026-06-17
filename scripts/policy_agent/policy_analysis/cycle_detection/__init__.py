from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()


def cycle_detection(
    api_key,
    openai_base_url,
    policy_path,
    model,
    feedback_dir,
    temperature=0.2,
    top_p=0.9,
):
    """
    Analyze an OPA Rego policy for:
    1. Cyclic rule dependencies.
    2. Redundant or subsumed rules.

    Saves the feedback to a markdown file in feedback_dir and prints it.
    """
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key, base_url=openai_base_url)

    # Validate policy file
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    # Read policy content
    with open(policy_path, "r", encoding="utf-8") as file:
        rego_policy = file.read()

    # System prompt for analysis
    system_instruction = """
    You are a code linting assistant specialized in analyzing Open Policy Agent (OPA) Rego policies.
    Your tasks are:

    1. Detect cycles in rule references or dependencies.
    2. Detect rules that may be entirely subsumed by earlier rules.

    Acceptance Criteria:

    Cyclic Rule Dependencies:
    - Represent rule dependencies as a directed graph.
    - Detect cycles (direct or indirect references).
    - Provide a trace of each cycle and the rules involved.

    Subsumed or Redundant Rules:
    - Identify rules that are logically impossible or fully subsumed by earlier rules.
    - Flag these rules and provide clear reasons.

    Focus solely on semantic and logical issues; ignore formatting and style.
    """

    print("Sending policy to model for analysis...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": rego_policy},
        ],
        temperature=temperature,
        top_p=top_p,
    )

    feedback = response.choices[0].message.content

    # Print feedback
    print("\n=== Linting Feedback ===\n")
    print(feedback)
    print("\n=======================\n")

    # Save feedback
    if not feedback_dir:
        raise ValueError("FEEDBACK_DIR not set in environment variables")
    os.makedirs(feedback_dir, exist_ok=True)

    output_file = os.path.join(feedback_dir, "linting_feedback_cycle-detection.md")
    with open(output_file, "w", encoding="utf-8") as out_file:
        out_file.write(feedback)

    print(f"Feedback saved to {output_file}")
    return feedback


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    policy_path = os.getenv("POLICY_PATH")
    model = os.getenv("MODEL_SONNET")
    feedback_dir = os.getenv("FEEDBACK_DIR")

    cycle_detection(api_key, base_url, policy_path, model, feedback_dir)
