# LM Studio Integration Improvement Plan

**Goal:** Enhance the `LMStudioClient` with robust tool/MCP support and improve streaming output visibility.

**Architecture:** Adopt the mature `chat_v1` implementation from the `fix-lmstudio-integration` worktree.

**Tech Stack:** Python, requests, OpenAI SDK.

---

### Task 1: Update LMStudioClient with improved chat_v1

**Files:**
- Modify: `app/services/lm_studio_client.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: Replace chat_v1 and add logging in `app/services/lm_studio_client.py`**

```python
    def chat_v1(self, input_text: str, system_prompt: str = None, integrations: list = None, context_length: int = 2048) -> str:
        """Call the native LM Studio V1 API with support for MCP integrations."""
        base = self.v1_base_url.rstrip("/")
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        
        url = f"{base}/chat"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": input_text,
            "context_length": context_length
        }
        
        if system_prompt:
            payload["system_prompt"] = system_prompt
            
        if integrations:
            payload["integrations"] = integrations

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            output_items = data.get("output", [])
            
            combined_text = ""
            for item in output_items:
                if item.get("type") in ["message", "reasoning"]:
                    combined_text += item.get("content", "")
                elif item.get("type") == "tool_call":
                    # Tool tracing
                    print(f"DEBUG: Tool Call -> {item.get('tool')}")
                    
            return combined_text.strip()
        except Exception as e:
            print(f"DEBUG: V1 API Error: {str(e)}")
            raise
```

- [ ] **Step 2: Update `call_model` to use `chat_v1` correctly**

```python
    def call_model(self, system_prompt: str, user_message: str, max_tokens: int = 80, temperature: float = 0.3) -> str:
        """Fallback to OpenAI-compatible SDK call if needed."""
        try:
            return self.chat_v1(user_message, system_prompt=system_prompt)
        except Exception:
            # Fallback
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["\n"]
            )
            return response.choices[0].message.content.strip()
```

- [ ] **Step 3: Run existing tests to ensure compatibility**

Run: `pytest tests/test_services.py`
Expected: PASS (Ensure `chat_v1` is called correctly by existing code)

- [ ] **Step 4: Commit**

```bash
git add app/services/lm_studio_client.py tests/test_services.py
git commit -m "feat: improve lmstudio client with chat_v1 support"
```

### Task 2: Enhance chat_v1_stream events

**Files:**
- Modify: `app/services/lm_studio_client.py`

- [ ] **Step 1: Ensure `chat_v1_stream` logs event types**

Update the `chat_v1_stream` method in `app/services/lm_studio_client.py` to ensure all event types are processed and yielded correctly.

```python
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("event:"):
                            event_type = decoded_line.split(":")[1].strip()
                            continue
                        if decoded_line.startswith("data:"):
                            data = json.loads(decoded_line.split(":", 1)[1].strip())
                            # Keep event_type updated
                            yield event_type, data
```

- [ ] **Step 2: Commit**

```bash
git add app/services/lm_studio_client.py
git commit -m "feat: ensure event types are correctly yielded in stream"
```
