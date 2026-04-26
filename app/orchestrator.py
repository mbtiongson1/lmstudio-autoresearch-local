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

    def _agent_step(self, task_id: str, topic: str, summary: str, turn: int) -> str:
        state_block = f"Topic: {topic}\nFindings: {summary}\nTurn: {turn}/8"
        integrations = [{"type": "plugin", "id": "mcp/fetch", "allowed_tools": ["fetch"]}]
        try:
            # Need to handle mocked chat_v1 vs chat_v1_stream in tests
            if hasattr(self.lm_client, "chat_v1_stream"):
                stream = self.lm_client.chat_v1_stream(state_block, system_prompt=SYSTEM_PROMPT, integrations=integrations)
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
                action_type = "search" if raw.startswith("SEARCH:") else ("think" if raw.startswith("THINK:") else ("answer" if raw.startswith("ANSWER:") else "unknown"))
                content = raw.split(":", 1)[1].strip() if ":" in raw else raw
                
                self.state_manager.add_history_entry(task_id, turn, action_type, content)
                if action_type == "search": summary = summary[-200:] + " | " + self.search_service.search(content)[:200]
                elif action_type == "answer":
                    self.state_manager.mark_completed(task_id, content)
                    return content
            except Exception as e:
                self.state_manager.mark_error(task_id, str(e))
                raise
        return summary
