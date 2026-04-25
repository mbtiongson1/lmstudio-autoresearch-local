import os
import json
from app.services.lm_studio_client import LMStudioClient
from app.services.state_manager import StateManager
from app.orchestrator import ResearchOrchestrator

def verify():
    # Ensure environment variables are set or use defaults
    # os.environ["LM_API_TOKEN"] = "lm-studio"
    
    client = LMStudioClient()
    state = StateManager()
    orchestrator = ResearchOrchestrator(client, state)
    
    task_id = state.create_session("Hugging Face Trending Models")
    print(f"--- Starting Research Task: {task_id} ---")
    print(f"Model: {client.model}")
    print(f"V1 API: {client.v1_base_url}")
    
    try:
        # This will trigger the research loop which now uses chat_v1 and MCP integrations
        result = orchestrator.research(task_id, "What is the top trending model on hugging face?")
        print(f"\n--- Final Answer ---\n{result}")
        
        # Print session history to see actions taken
        session = state.get_session(task_id)
        print("\n--- Research History ---")
        for entry in session.get('history', []):
            print(f"Turn {entry['turn']} [{entry['action']}]: {entry['content']}")
            
    except Exception as e:
        print(f"\nVerification failed: {e}")
        print("Make sure LM Studio 0.4.0+ is running with 'Allow per-request MCPs' enabled.")

if __name__ == "__main__":
    verify()
