from pathlib import Path
import json
import os
import pandas as pd
import logging
from pprint import pprint

os.environ["ARES_HOME"] = ".."

logger = logging.getLogger("ares")
logger.setLevel(logging.INFO)
from ares.redteam import RedTeamer
from ares.utils import parse_config
from ares.utils import parse_connectors
config_path = Path("example_configs/owasp/qwen-owasp-llm-01.yaml")
config = parse_config(config_path)
connectors = parse_connectors(config_path)
rt = RedTeamer(config, connectors["connectors"], verbose=False)


pprint(rt.config.user_config['target'])

try:
    rt.target()
except (EnvironmentError, ModuleNotFoundError) as env_err:
    print("Error")
pprint(rt.config.goal)
rt.goal(limit=False) # limit is the optional flag that limits number of goals to 5 by default (this number could be updated using an additional first_n parameter)

pprint(rt.config.strategy)
rt.strategy()
#rt.evaluate()
