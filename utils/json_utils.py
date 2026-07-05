#---------------------------------
# JSON Utils
#   - Load JSON from file
#   - Save JSON to file
#---------------------------------

import json
from pathlib import Path

def load_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
