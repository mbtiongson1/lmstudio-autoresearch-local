import pytest
from unittest.mock import Mock, patch
from app.orchestrator import ResearchOrchestrator
from app.services.lm_studio_client import LMStudioClient
from app.services.state_manager import StateManager

def test_orchestrator_provides_tools():
    lm_client = Mock(spec=LMStudioClient)
    state_manager = Mock(spec=StateManager)
    orchestrator = ResearchOrchestrator(lm_client, state_manager)
    
    # Mock stream response
    stream = [("chat.end", {"result": {"output": [{"type": "message", "content": "Done"}]}})]
    lm_client.chat_v1_stream.return_value = stream
    
    # Execute a step
    orchestrator._agent_step("task1", "topic", "findings", 1)
    
    # Verify the client was called with integrations
    args, kwargs = lm_client.chat_v1_stream.call_args
    # This currently fails because it doesn't pass integrations
    assert "integrations" in kwargs
