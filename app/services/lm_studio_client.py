"""LM Studio client wrapper for OpenAI SDK"""
import os
from openai import OpenAI


class LMStudioClient:
    def __init__(self, base_url: str = None, model: str = None, api_key: str = "lm-studio"):
        self.base_url = base_url or os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
        self.model = model or os.getenv("MODEL_NAME", "gemma-4-2b")
        self.api_key = api_key
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def call_model(self, system_prompt: str, user_message: str, max_tokens: int = 80, temperature: float = 0.3) -> str:
        """Call the LM Studio model and return the response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["\n"]
        )
        return response.choices[0].message.content.strip()
