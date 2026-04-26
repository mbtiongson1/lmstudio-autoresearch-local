import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_mcp():
    url = "http://localhost:1234/api/v1/chat"
    token = os.getenv("LM_API_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen3.5-4b-mlx",
        "input": "Fetch content from https://example.com",
        "integrations": [
            {
                "type": "plugin",
                "id": "mcp/fetch",
                "allowed_tools": ["fetch"]
            }
        ],
        "temperature": 0.1
    }
    
    print(f"Request Payload: {json.dumps(payload, indent=2)}")
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test_mcp()
