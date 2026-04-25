"""Research orchestrator - manages the 8-turn research loop"""
from typing import Callable, Optional
from app.services.lm_studio_client import LMStudioClient
from app.services.search_service import SearchService
from app.services.state_manager import StateManager


SYSTEM_PROMPT = """You are a research agent. Each turn output EXACTLY one line:
  SEARCH: <query under 8 words>
  THINK: <one insight under 25 words>
  ANSWER: <final answer under 80 words>
Nothing else.

You have access to Hugging Face model search via MCP. You can use it as needed before providing your next line of output."""

DEFAULT_INTEGRATIONS = [
    {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
    }
]


class ResearchOrchestrator:
    def __init__(self, lm_client: LMStudioClient, state_manager: StateManager, callback: Optional[Callable] = None, integrations: list = None):
        self.lm_client = lm_client
        self.state_manager = state_manager
        self.callback = callback  # Optional: called on each event for real-time updates
        self.search_service = SearchService()
        self.integrations = integrations if integrations is not None else DEFAULT_INTEGRATIONS

    def _emit_event(self, task_id: str, turn: int, action: str, content: str):
        """Emit an event to observers (for real-time updates)."""
        event = {
            "type": "action",
            "turn": turn,
            "action": action,
            "content": content
        }
        if self.callback:
            self.callback(task_id, event)

    def _compress_summary(self, existing: str, new_finding: str) -> str:
        """Compress summary: keep last 200 chars + new finding."""
        combined = existing[-200:] + " | " + new_finding[:200]
        return combined[-350:]

    def _parse_action(self, raw: str) -> tuple:
        """Parse agent output into (action_type, content)."""
        if raw.startswith("SEARCH:"):
            return "search", raw[7:].strip()
        elif raw.startswith("THINK:"):
            return "think", raw[6:].strip()
        elif raw.startswith("ANSWER:"):
            return "answer", raw[7:].strip()
        return "unknown", raw

    def _agent_step(self, topic: str, summary: str, turn: int) -> str:
        """Call the LM Studio model for next action."""
        state_block = f"Topic: {topic}\nFindings: {summary}\nTurn: {turn}/8"
        if hasattr(self.lm_client, "chat_v1"):
            return self.lm_client.chat_v1(state_block, system_prompt=SYSTEM_PROMPT, integrations=self.integrations)
        return self.lm_client.call_model(SYSTEM_PROMPT, state_block, max_tokens=80, temperature=0.3)

    def research(self, task_id: str, topic: str, max_turns: int = 8) -> str:
        """Execute the 8-turn research loop."""
        self.state_manager.mark_started(task_id)
        summary = ""

        for turn in range(1, max_turns + 1):
            try:
                raw = self._agent_step(topic, summary, turn)
                self.state_manager.update_session(task_id, current_turn=turn)

                action_type, content = self._parse_action(raw)

                # Emit event and add to history
                self._emit_event(task_id, turn, action_type, content)
                self.state_manager.add_history_entry(task_id, turn, action_type, content)

                if action_type == "search":
                    finding = self.search_service.search(content)
                    summary = self._compress_summary(summary, finding)

                elif action_type == "think":
                    summary = self._compress_summary(summary, content)

                elif action_type == "answer":
                    self.state_manager.mark_completed(task_id, content)
                    return content

                # Force answer on last turn
                if turn == max_turns:
                    forced_answer = f"Research completed after {max_turns} turns. Summary: {summary[:200]}"
                    self.state_manager.mark_completed(task_id, forced_answer)
                    return forced_answer

            except Exception as e:
                error_msg = f"Error on turn {turn}: {str(e)}"
                self.state_manager.mark_error(task_id, error_msg)
                raise

        return summary
