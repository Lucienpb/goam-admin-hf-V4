import json
from pathlib import Path

AI_CONFIG_PATH = Path("data") / "ai_config.json"

DEFAULT_AI_CONFIG = {
    "zero_cost_mode": True,
    "parser_fallback_enabled": True,
    "low_confidence_threshold": 0.60,
    "min_regression_pass_rate": 0.85,
    "fast_model_id": "meta-llama/Llama-3.1-8B-Instruct",
    "smart_model_id": "meta-llama/Llama-3.1-70B-Instruct",
    "high_accuracy_actions": [
        "compare_players",
        "compare_trends",
        "predict_next",
    ],
}


def load_ai_config():
    if not AI_CONFIG_PATH.exists():
        return dict(DEFAULT_AI_CONFIG)

    try:
        data = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(DEFAULT_AI_CONFIG)

        merged = dict(DEFAULT_AI_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_AI_CONFIG)


def get_ai_setting(key, default=None):
    cfg = load_ai_config()
    if key in cfg:
        return cfg[key]
    return default
