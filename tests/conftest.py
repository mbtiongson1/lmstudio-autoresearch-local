"""Shared pytest fixtures and configuration"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.lm_studio_client import LMStudioClient
from app.services.state_manager import StateManager


@pytest.fixture
def mock_lm_client():
    """Mock LM Studio client."""
    client = Mock(spec=LMStudioClient)
    client.call_model = Mock(return_value="SEARCH: climate change facts")
    return client


@pytest.fixture
def state_manager():
    """In-memory state manager instance."""
    return StateManager()


@pytest.fixture
def mock_search_service():
    """Mock search service."""
    from unittest.mock import patch
    with patch('app.services.search_service.SearchService.search') as mock_search:
        mock_search.return_value = "Climate change is the long-term shift in global temperatures. It is caused by human activities."
        yield mock_search


@pytest.fixture
def sample_research_session():
    """Sample research session data."""
    return {
        "task_id": "test-task-123",
        "topic": "climate change",
        "status": "running",
        "current_turn": 1,
        "history": [
            {
                "turn": 1,
                "action": "search",
                "content": "climate change facts"
            }
        ]
    }
