import os
from huggingface_hub import InferenceClient
from goam_ai.config import load_ai_config

def _routing_config():
    cfg = load_ai_config()
    fast_model = os.environ.get("GOAM_AI_FAST_MODEL", cfg.get("fast_model_id", "meta-llama/Llama-3.1-8B-Instruct"))
    smart_model = os.environ.get("GOAM_AI_SMART_MODEL", cfg.get("smart_model_id", "meta-llama/Llama-3.1-70B-Instruct"))
    high_accuracy_actions = set(cfg.get("high_accuracy_actions", []))
    return fast_model, smart_model, high_accuracy_actions


def get_client(model_id: str | None = None) -> InferenceClient:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN missing in Hugging Face Secrets")
    fast_model, _, _ = _routing_config()
    return InferenceClient(model_id or fast_model, token=token)


def choose_model_id(action: str | None = None) -> str:
    fast_model, smart_model, high_accuracy_actions = _routing_config()
    if action in high_accuracy_actions:
        return smart_model
    return fast_model


def call_llm(
    prompt: str,
    max_new_tokens: int = 300,
    temperature: float = 0.2,
    action: str | None = None,
    model_id: str | None = None,
) -> str:
    """
    Sends a chat-style prompt to a routed model.
    - fast model by default
    - smart model for high-accuracy actions
    """

    selected_model = model_id or choose_model_id(action)
    client = get_client(selected_model)

    response = client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_new_tokens,
        temperature=temperature,
    )

    return response.choices[0].message["content"]
