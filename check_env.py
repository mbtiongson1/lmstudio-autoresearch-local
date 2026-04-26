import os
from dotenv import load_dotenv

load_dotenv()
print(f"MODEL_NAME: {os.getenv('MODEL_NAME')}")
print(f"LM_API_TOKEN: {os.getenv('LM_API_TOKEN')}")
