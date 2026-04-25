import requests
import os

url = "http://localhost:1234/api/v1/models"
api_key = os.getenv("LM_API_TOKEN", "lm-studio")
headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    print(f"Requesting: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
