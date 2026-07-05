# utils/llm_client.py
import requests

# FREE model endpoint (no token required)
FREE_MODEL_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"


class FreeLLMClient:
    """
    Free LLM client using Hugging Face public inference API.
    No API token required.
    Slower than paid endpoints but completely free.
    """

    def __init__(self, api_url: str = FREE_MODEL_URL):
        self.api_url = api_url

    def chat(self, prompt: str, max_new_tokens: int = 300) -> str:
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_new_tokens,
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }

        response = requests.post(self.api_url, json=payload, timeout=60)

        # Free API sometimes returns 503 on cold start — retry once
        if response.status_code == 503:
            response = requests.post(self.api_url, json=payload, timeout=60)

        response.raise_for_status()
        data = response.json()

        # HF returns list format
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("generated_text", "").strip()

        return str(data)
