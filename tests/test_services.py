"""Unit tests for services"""
import pytest
from unittest.mock import Mock, patch
from app.services.lm_studio_client import LMStudioClient
from app.services.search_service import SearchService
from app.services.state_manager import StateManager


class TestLMStudioClient:
    """Test LM Studio client wrapper."""

    def test_init_default_values(self):
        """Test client initialization with defaults."""
        with patch.dict('os.environ', {'LM_STUDIO_URL': 'http://localhost:1234/v1', 'MODEL_NAME': 'gemma-4-2b'}):
            client = LMStudioClient()
            assert client.base_url == 'http://localhost:1234/v1'
            assert client.model == 'gemma-4-2b'

    def test_init_custom_values(self):
        """Test client initialization with custom values."""
        client = LMStudioClient(base_url='http://custom:5000/v1', model='custom-model')
        assert client.base_url == 'http://custom:5000/v1'
        assert client.model == 'custom-model'

    def test_call_model(self, mock_lm_client):
        """Test model calling."""
        response = mock_lm_client.call_model("System", "User prompt")
        assert response == "SEARCH: climate change facts"
        mock_lm_client.call_model.assert_called_once()


class TestSearchService:
    """Test DuckDuckGo search service."""

    @patch('app.services.search_service.requests.get')
    def test_search_with_results(self, mock_get):
        """Test search with successful results."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'AbstractText': 'Climate change is...',
            'RelatedTopics': [
                {'Text': 'Global warming'},
                {'Text': 'Greenhouse gases'}
            ]
        }
        mock_get.return_value = mock_response

        result = SearchService.search('climate change')
        assert 'Climate change is' in result
        assert len(result) <= 400

    @patch('app.services.search_service.requests.get')
    def test_search_no_results(self, mock_get):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'AbstractText': '',
            'RelatedTopics': []
        }
        mock_get.return_value = mock_response

        result = SearchService.search('zzzzzzzzz')
        assert result == "No results found."

    @patch('app.services.search_service.requests.get')
    def test_search_error_handling(self, mock_get):
        """Test search error handling."""
        mock_get.side_effect = Exception("Network error")

        result = SearchService.search('query')
        assert "Search error" in result


class TestStateManager:
    """Test in-memory state manager."""

    def test_create_session(self):
        """Test creating a new session."""
        manager = StateManager()
        task_id = manager.create_session('test topic', max_turns=8)

        assert task_id is not None
        session = manager.get_session(task_id)
        assert session['topic'] == 'test topic'
        assert session['status'] == 'started'

    def test_update_session(self):
        """Test updating session state."""
        manager = StateManager()
        task_id = manager.create_session('test topic')
        manager.update_session(task_id, current_turn=5)

        session = manager.get_session(task_id)
        assert session['current_turn'] == 5

    def test_add_history_entry(self):
        """Test adding history entries."""
        manager = StateManager()
        task_id = manager.create_session('test topic')
        manager.add_history_entry(task_id, 1, 'search', 'test query')

        session = manager.get_session(task_id)
        assert len(session['history']) == 1
        assert session['history'][0]['action'] == 'search'

    def test_summary_management(self):
        """Test managing rolling summary."""
        manager = StateManager()
        task_id = manager.create_session('test topic')
        
        manager.update_summary(task_id, 'Summary 1')
        assert manager.get_summary(task_id) == 'Summary 1'
        
        manager.update_summary(task_id, 'Summary 2')
        assert manager.get_summary(task_id) == 'Summary 2'

    def test_mark_completed(self):
        """Test marking session as completed."""
        manager = StateManager()
        task_id = manager.create_session('test topic')
        manager.mark_completed(task_id, 'Final answer here')

        session = manager.get_session(task_id)
        assert session['status'] == 'completed'
        assert session['final_answer'] == 'Final answer here'

    def test_mark_error(self):
        """Test marking session with error."""
        manager = StateManager()
        task_id = manager.create_session('test topic')
        manager.mark_error(task_id, 'Something went wrong')

        session = manager.get_session(task_id)
        assert session['status'] == 'error'
        assert session['error'] == 'Something went wrong'

    def test_get_nonexistent_session(self):
        """Test getting a nonexistent session."""
        manager = StateManager()
        session = manager.get_session('nonexistent')
        assert session is None
