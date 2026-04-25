"""LM Studio client wrapper for OpenAI SDK"""
import os
import requests
from openai import OpenAI


class LMStudioClient:
    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        # OpenAI SDK base (v1)
        self.openai_base_url = base_url or os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
        # Native V1 API base
        self.v1_base_url = os.getenv("LM_STUDIO_V1_URL", "http://localhost:1234/api/v1")
        
        self.model = model or os.getenv("MODEL_NAME", "ibm/granite-4-micro")
        self.api_key = api_key or os.getenv("LM_API_TOKEN", "lm-studio")
        self.client = OpenAI(base_url=self.openai_base_url, api_key=self.api_key)

    def chat_v1(self, input_text: str, system_prompt: str = None, integrations: list = None, context_length: int = 8000) -> str:
        """Call the native LM Studio V1 API with support for MCP integrations."""
        url = f"{self.v1_base_url}/chat"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": input_text,
            "context_length": context_length
        }
        
        if system_prompt:
            payload["system_prompt"] = system_prompt
            
        if integrations:
            payload["integrations"] = integrations

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        output_items = data.get("output", [])
        
        combined_text = ""
        for item in output_items:
            if item.get("type") in ["message", "reasoning"]:
                combined_text += item.get("content", "")
            elif item.get("type") == "tool_call":
                # If the tool has already been executed and result is in output
                if "output" in item:
                    # We could potentially add this to the context for the model
                    # but LM Studio usually provides the final message after tool execution
                    pass
                    
        return combined_text.strip()

    def call_model(self, system_prompt: str, user_message: str, max_tokens: int = 80, temperature: float = 0.3) -> str:
        """Fallback to OpenAI-compatible SDK call if needed."""
        try:
            # Try using the V1 API first for reasoning/tool support if the model is compatible
            return self.chat_v1(user_message, system_prompt=system_prompt)
        except Exception:
            # Fallback to standard OpenAI SDK
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
