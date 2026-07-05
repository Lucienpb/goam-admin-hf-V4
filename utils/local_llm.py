# utils/local_llm.py
from pathlib import Path
from llama_cpp import Llama

MODEL_PATH = Path("models/gemma-2b-it.Q4_K_M.gguf")

class LocalLLM:
    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

        self.llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=4096,
            n_threads=4,
            n_gpu_layers=0,   # CPU only
            verbose=False
        )

    def chat(self, prompt: str, max_tokens: int = 512) -> str:
        output = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
            stop=["</s>"]
        )
        return output["choices"][0]["text"].strip()
