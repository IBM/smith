import os
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

import torch
import random
import numpy as np

# Various seeds and flags for better reproducibility.
seed = 20
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

from ares_autodan.strategies.autodan import AutoDAN
from ares.connectors.huggingface import HuggingFaceConnector
def test_full_pipeline():
    config = {
        "input_path": "../..//assets/autodan_example.json",
        "output_path": "../../autodan_results.json",
        "num_steps": 20, # Use the default (200) iterations to acutally jailbreak the model.
        "type": "autodan",
        "model": "llama-3",
        "batch_size":8,
        "early_stop": False
    }

    llm_config = {
        "name": "Llama",
        "type": "huggingface",
        "model_config": {
            "pretrained_model_name_or_path": "Qwen/Qwen2-0.5B-Instruct",
            "torch_dtype": "float16",
        },
        "tokenizer_config": {"pretrained_model_name_or_path": "Qwen/Qwen2-0.5B-Instruct"},
        "device": "auto",
    }

    connector = HuggingFaceConnector(llm_config)
    autodan_attack = AutoDAN(target_connector=connector, config=config)
    autodan_attack.generate()
test_full_pipeline()
