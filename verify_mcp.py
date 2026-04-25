import os
import json
from dotenv import load_dotenv
from app.services.lm_studio_client import LMStudioClient
from app.services.state_manager import StateManager
from app.orchestrator import ResearchOrchestrator

# Load environment variables
load_dotenv()

from unittest.mock import patch, MagicMock

def verify():
    # Load environment variables
    load_dotenv()
    
    client = LMStudioClient()
    state = StateManager()
    orchestrator = ResearchOrchestrator(client, state)
    
    task_id = state.create_session("Hugging Face Trending Models")
    print(f"--- [PREVIEW MODE] Starting Research Task: {task_id} ---")
    print(f"Note: This is a simulated run to preview the workflow logic.\n")
    
    # Mock responses for 3 turns to show the flow
    # Turn 1: Uses the new HF MCP tool
    # Turn 2: Uses standard web search
    # Turn 3: Provides final answer
    mock_responses = [
        "THINK: I should check Hugging Face for trending models first.",
        "SEARCH: latest trending models on huggingface",
        "ANSWER: The top trending model on Hugging Face is currently the 'Gemma 2' series, followed by various Llama-3 derivatives."
    ]
    
    with patch.object(LMStudioClient, 'chat_v1') as mock_chat:
        mock_chat.side_effect = mock_responses
        
        try:
            result = orchestrator.research(task_id, "What is the top trending model on hugging face?", max_turns=3)
            print(f"\n--- Final Answer ---\n{result}")
            
            session = state.get_session(task_id)
            print("\n--- Research History (as seen in StateManager) ---")
            for entry in session.get('history', []):
                print(f"Turn {entry['turn']} [{entry['action']}]: {entry['content']}")
                
        except Exception as e:
            print(f"\nPreview failed: {e}")

if __name__ == "__main__":
    verify()
