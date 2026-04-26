import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_chat():
    url = "http://localhost:1234/api/v1/chat"
    token = os.getenv("LM_API_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Try a query that would benefit from a search tool
    payload = {
        "model": "qwen3.5-4b-mlx",
        "input": "Search for the current weather in Paris.",
        "temperature": 0.1
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test_chat()
