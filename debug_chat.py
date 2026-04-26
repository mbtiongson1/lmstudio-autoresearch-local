import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_chat():
    url = "http://localhost:1234/api/v1/chat"
    token = os.getenv("LM_API_TOKEN")
    print(f"Using token: {token}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen3.5-4b-mlx",
        "input": "Research the performance comparison between Qwen 3.6 and Qwen 3.5 models.",
        "system_prompt": "You are a research agent. Search for information and provide an answer.",
        "context_length": 2048,
        "temperature": 0.1
    }
    
    print(f"Request Payload: {json.dumps(payload, indent=2)}")
    response = requests.post(url, headers=headers, json=payload)
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text}")

if __name__ == "__main__":
    test_chat()
