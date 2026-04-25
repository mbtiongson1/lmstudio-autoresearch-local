"""LM Studio client wrapper for OpenAI SDK"""
import os
import requests
import json
from openai import OpenAI


class LMStudioClient:
    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        # OpenAI SDK base (v1)
        self.openai_base_url = base_url or os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
        # Native V1 API base
        self.v1_base_url = os.getenv("LM_STUDIO_V1_URL", "http://localhost:1234/api/v1")
        
        self.api_key = api_key or os.getenv("LM_API_TOKEN", "lm-studio")
        self.client = OpenAI(base_url=self.openai_base_url, api_key=self.api_key)
        
        # Auto-detect loaded model
        self.model = model or os.getenv("MODEL_NAME")
        if not self.model:
            try:
                models_data = self.list_models()
                for m in models_data.get("models", []):
                    if m.get("loaded_instances"):
                        self.model = m["key"]
                        break
            except Exception:
                self.model = "ibm/granite-4-micro"

    def set_model(self, model: str):
        self.model = model

    def chat_v1(self, input_text: str, system_prompt: str = None, integrations: list = None, context_length: int = 2048) -> str:
        """Call the native LM Studio V1 API with support for MCP integrations."""
        base = self.v1_base_url.rstrip("/")
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        
        url = f"{base}/chat"
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

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            output_items = data.get("output", [])
            
            combined_text = ""
            for item in output_items:
                if item.get("type") in ["message", "reasoning"]:
                    combined_text += item.get("content", "")
                elif item.get("type") == "tool_call":
                    # Tool tracing
                    print(f"DEBUG: Tool Call -> {item.get('tool')}")
                    
            return combined_text.strip()
        except Exception as e:
            print(f"DEBUG: V1 API Error: {str(e)}")
            raise

    def call_model(self, system_prompt: str, user_message: str, max_tokens: int = 80, temperature: float = 0.3) -> str:
        """Fallback to OpenAI-compatible SDK call if needed."""
        try:
            return self.chat_v1(user_message, system_prompt=system_prompt)
        except Exception:
            # Fallback
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

    def list_models(self) -> dict:
        """List available models via LM Studio V1 API."""
        base = self.v1_base_url.rstrip("/")
        url = f"{base}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def load_model(self, model_key: str, **kwargs) -> dict:
        """Load a model via LM Studio V1 API."""
        base = self.v1_base_url.rstrip("/")
        url = f"{base}/models/load"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": model_key}
        payload.update(kwargs)
        response = requests.post(url, headers=headers, json=payload, timeout=300)  # Loading can take time
        response.raise_for_status()
        return response.json()

    def unload_model(self, instance_id: str) -> dict:
        """Unload a model via LM Studio V1 API."""
        base = self.v1_base_url.rstrip("/")
        url = f"{base}/models/unload"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"instance_id": instance_id}
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
