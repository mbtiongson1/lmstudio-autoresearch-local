from openai import OpenAI
import requests, re, json

client = OpenAI(baseURL="http://localhost:1234/v1", apiKey="lm-studio")
MODEL = "gemma-4-e2b-it"  # match your LM Studio model name

SYSTEM = """You are a research agent. Each turn output EXACTLY one line:
  SEARCH: <query under 8 words>
  THINK: <one insight under 25 words>
  ANSWER: <final answer under 80 words>
Nothing else."""

def webSearch(query):
    # DuckDuckGo instant answers (no API key needed)
    r = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1}
    )
    data = r.json()
    abstract = data.get("AbstractText", "")
    related = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3]]
    raw = abstract + " ".join(related)
    return raw[:400] if raw.strip() else "No results found."

def compressSummary(existing, newFinding):
    # Naive compression — keep last 200 chars + new finding (fits in tiny context)
    combined = existing[-200:] + " | " + newFinding[:200]
    return combined[-350:]

def agentStep(topic, summary, turn):
    stateBlock = f"Topic: {topic}\nFindings: {summary}\nTurn: {turn}/8"
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": stateBlock}
        ],
        max_tokens=80,
        temperature=0.3,
        stop=["\n"]
    )
    return response.choices[0].message.content.strip()

def parseAction(raw):
    if raw.startswith("SEARCH:"):
        return "search", raw[7:].strip()
    elif raw.startswith("THINK:"):
        return "think", raw[6:].strip()
    elif raw.startswith("ANSWER:"):
        return "answer", raw[7:].strip()
    return "unknown", raw

def research(topic, maxTurns=8):
    summary = ""
    for turn in range(1, maxTurns + 1):
        raw = agentStep(topic, summary, turn)
        print(f"[{turn}] {raw}")
        
        actionType, content = parseAction(raw)

        if actionType == "search":
            finding = webSearch(content)
            summary = compressSummary(summary, finding)

        elif actionType == "think":
            summary = compressSummary(summary, content)

        elif actionType == "answer":
            print(f"\n✅ Final Answer:\n{content}")
            return content

        # Safety: force answer on last turn
        if turn == maxTurns:
            print("\n⚠️ Max turns reached — forcing answer.")
            break

    return summary

if __name__ == "__main__":
    topic = input("Research topic: ")
    research(topic)