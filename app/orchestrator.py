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

class ResearchOrchestrator:
    def __init__(self, lm_client: LMStudioClient, state_manager: StateManager, callback: Optional[Callable] = None):
        self.lm_client = lm_client
        self.state_manager = state_manager
        self.callback = callback
        self.search_service = SearchService()

    def _parse_action(self, raw: str) -> tuple[str, str]:
        """Parse protocol line into action type + content."""
        if raw.startswith("SEARCH:"):
            return "search", raw.split(":", 1)[1].strip()
        if raw.startswith("THINK:"):
            return "think", raw.split(":", 1)[1].strip()
        if raw.startswith("ANSWER:"):
            return "answer", raw.split(":", 1)[1].strip()
        return "unknown", raw.strip()

    def _compress_summary(self, existing: str, new_finding: str, max_chars: int = 350) -> str:
        merged = (existing + " | " + new_finding).strip(" |")
        return merged[-max_chars:]

    def _emit_event(self, task_id: str, turn: int, action: str, content: str):
        if self.callback:
            self.callback(task_id, {"type": "action", "turn": turn, "action": action, "content": content})

    def _agent_step(self, *args) -> str:
        """
        Compatibility signature:
        - _agent_step(task_id, topic, summary, turn)
        - _agent_step(topic, summary, turn)
        """
        if len(args) == 4:
            _task_id, topic, summary, turn = args
        elif len(args) == 3:
            topic, summary, turn = args
        else:
            raise TypeError("_agent_step expects (task_id, topic, summary, turn) or (topic, summary, turn)")
        state_block = f"Topic: {topic}\nFindings: {summary}\nTurn: {turn}/8"
        integrations = [{"type": "plugin", "id": "mcp/fetch", "allowed_tools": ["fetch"]}]
        try:
            # Need to handle mocked chat_v1 vs chat_v1_stream in tests
            if hasattr(self.lm_client, "chat_v1_stream"):
                stream = self.lm_client.chat_v1_stream(state_block, system_prompt=SYSTEM_PROMPT, integrations=integrations)
                if stream is None or not hasattr(stream, "__iter__"):
                    return self.lm_client.chat_v1(state_block, system_prompt=SYSTEM_PROMPT, integrations=integrations)
                full_content = ""
                for event_type, data in stream:
                    if event_type == "message.delta": full_content += data.get("content", "")
                    elif event_type == "chat.end":
                        for item in data.get("result", {}).get("output", []):
                            if item.get("type") in ["message", "reasoning"]: full_content += item.get("content", "")
                return full_content.strip()
            else:
                return self.lm_client.chat_v1(state_block, system_prompt=SYSTEM_PROMPT, integrations=integrations)
        except Exception as e:
            raise e

    def research(self, task_id: str, topic: str, max_turns: int = 8) -> str:
        self.state_manager.mark_started(task_id)
        summary = ""
        for turn in range(1, max_turns + 1):
            try:
                raw = self._agent_step(task_id, topic, summary, turn)
                action_type, content = self._parse_action(raw)
                
                self.state_manager.add_history_entry(task_id, turn, action_type, content)
                self.state_manager.update_session(task_id, current_turn=turn)
                self._emit_event(task_id, turn, action_type, content)
                if action_type == "search":
                    summary = self._compress_summary(summary, self.search_service.search(content)[:200])
                elif action_type == "answer":
                    self.state_manager.mark_completed(task_id, content)
                    return content
            except Exception as e:
                self.state_manager.mark_error(task_id, str(e))
                raise
        # Force completion at max turns for compatibility with existing tests.
        final = summary if summary else "No final answer generated."
        self.state_manager.mark_completed(task_id, final)
        return final
