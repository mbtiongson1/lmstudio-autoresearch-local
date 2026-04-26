# Orchestrator Tool Integration Fix Plan

**Goal:** Enable the agent to use the search tool by passing it to the LM Client.

**Architecture:** Update `ResearchOrchestrator` to pass search tool integration via `chat_v1_stream`.

---

### Task 1: Update Orchestrator to pass tools

**Files:**
- Modify: `app/orchestrator.py`
- Test: `tests/test_orchestrator_tools.py`

- [ ] **Step 1: Modify `ResearchOrchestrator._agent_step`**

```python
    def _agent_step(self, task_id: str, topic: str, summary: str, turn: int) -> str:
        state_block = f"Topic: {topic}\nFindings: {summary}\nTurn: {turn}/8"
        
        # Add tool integrations
        integrations = [
            {
                "type": "plugin",
                "id": "mcp/search",
                "allowed_tools": ["search"]
            }
        ]
        
        full_content = ""
        try:
            # Update to pass integrations (will need to update LMStudioClient.chat_v1_stream first)
            stream = self.lm_client.chat_v1_stream(state_block, system_prompt=SYSTEM_PROMPT, integrations=integrations)
            # ...
```

- [ ] **Step 2: Update `LMStudioClient.chat_v1_stream`**

- Modify: `app/services/lm_studio_client.py`

```python
    def chat_v1_stream(self, input_text: str, system_prompt: str = None, integrations: list = None, context_length: int = 2048):
        # ...
        payload = {
            "model": self.model,
            "input": input_text,
            "context_length": context_length,
            "stream": True
        }
        if integrations:
            payload["integrations"] = integrations
        # ...
```

- [ ] **Step 3: Verify with `tests/test_orchestrator_tools.py`**
