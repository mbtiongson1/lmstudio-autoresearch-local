# 1. Force early searches (prevent hallucinating from training data)
if turn <= 2 and actionType != "search":
    raw = "SEARCH: " + topic  # override

# 2. Reject malformed output and retry once
if actionType == "unknown":
    raw = agentStep(topic, summary, turn)  # one retry
    actionType, content = parseAction(raw)

# 3. Upgrade summarizer (optional — use a second local model call)
def llmSummarize(text):
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": f"Summarize in 30 words: {text}"}],
        max_tokens=50
    )
    return r.choices[0].message.content.strip()