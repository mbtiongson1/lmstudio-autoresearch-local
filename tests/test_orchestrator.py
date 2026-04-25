"""Unit tests for research orchestrator"""
import pytest
from unittest.mock import Mock, patch
from app.orchestrator import ResearchOrchestrator
from app.services.state_manager import StateManager


class TestResearchOrchestrator:
    """Test research orchestrator."""

    @pytest.fixture
    def orchestrator(self, mock_lm_client):
        """Create orchestrator instance."""
        state_manager = StateManager()
        return ResearchOrchestrator(mock_lm_client, state_manager)

    def test_parse_action_search(self, orchestrator):
        """Test parsing SEARCH action."""
        action_type, content = orchestrator._parse_action("SEARCH: climate change impacts")
        assert action_type == "search"
        assert content == "climate change impacts"

    def test_parse_action_think(self, orchestrator):
        """Test parsing THINK action."""
        action_type, content = orchestrator._parse_action("THINK: Climate change is caused by greenhouse gases")
        assert action_type == "think"
        assert content == "Climate change is caused by greenhouse gases"

    def test_parse_action_answer(self, orchestrator):
        """Test parsing ANSWER action."""
        action_type, content = orchestrator._parse_action("ANSWER: The primary causes are CO2 emissions")
        assert action_type == "answer"
        assert content == "The primary causes are CO2 emissions"

    def test_parse_action_unknown(self, orchestrator):
        """Test parsing unknown action."""
        action_type, content = orchestrator._parse_action("INVALID: something")
        assert action_type == "unknown"

    def test_compress_summary(self, orchestrator):
        """Test summary compression."""
        existing = "A" * 300
        new_finding = "B" * 200
        result = orchestrator._compress_summary(existing, new_finding)
        
        assert len(result) <= 350
        assert "A" in result
        assert "B" in result

    def test_agent_step(self, mock_lm_client, orchestrator):
        """Test agent step calls LM Studio."""
        mock_lm_client.chat_v1.return_value = "SEARCH: test query"
        result = orchestrator._agent_step("test topic", "summary", 1)
        
        assert result == "SEARCH: test query"
        mock_lm_client.chat_v1.assert_called_once()

    def test_emit_event(self, orchestrator):
        """Test event emission."""
        events = []
        
        def capture_event(task_id, event):
            events.append(event)
        
        orchestrator.callback = capture_event
        orchestrator._emit_event("task1", 1, "search", "query")
        
        assert len(events) == 1
        assert events[0]["action"] == "search"

    @patch('app.orchestrator.ResearchOrchestrator._agent_step')
    def test_research_loop_answer_on_turn_3(self, mock_agent_step, orchestrator):
        """Test research completes on ANSWER action."""
        # Mock agent to return different actions
        mock_agent_step.side_effect = [
            "SEARCH: initial query",
            "THINK: some insight",
            "ANSWER: Final answer to the question",
        ]
        
        state_manager = orchestrator.state_manager
        task_id = state_manager.create_session("test topic", max_turns=8)
        
        result = orchestrator.research(task_id, "test topic", max_turns=8)
        
        assert "Final answer" in result
        session = state_manager.get_session(task_id)
        assert session['status'] == 'completed'

    @patch('app.orchestrator.ResearchOrchestrator._agent_step')
    def test_research_forced_answer_on_max_turns(self, mock_agent_step, orchestrator):
        """Test research forces answer on max turns."""
        # Mock agent to never return ANSWER
        mock_agent_step.return_value = "THINK: just thinking"
        
        state_manager = orchestrator.state_manager
        task_id = state_manager.create_session("test topic", max_turns=2)
        
        result = orchestrator.research(task_id, "test topic", max_turns=2)
        
        session = state_manager.get_session(task_id)
        assert session['status'] == 'completed'
        assert session['current_turn'] == 2

    def test_research_error_handling(self, mock_lm_client, orchestrator):
        """Test research handles errors gracefully."""
        mock_lm_client.chat_v1.side_effect = Exception("API Error")
        
        state_manager = orchestrator.state_manager
        task_id = state_manager.create_session("test topic")
        
        with pytest.raises(Exception):
            orchestrator.research(task_id, "test topic", max_turns=1)
        
        session = state_manager.get_session(task_id)
        assert session['status'] == 'error'
