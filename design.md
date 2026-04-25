# LM Studio AutoResearch Agent – Design Document

## Overview
A localhost web application that enables real-time research tasks using a local LM Studio model. Users submit research topics via a web interface and monitor the agent's iterative search, reasoning, and answer generation process in real-time.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Web UI)                                      │
│  - Input form for research topic                        │
│  - Real-time output stream display                      │
│  - Progress visualization (current turn, status)        │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP/WebSocket
┌────────────────▼────────────────────────────────────────┐
│  Backend API (Flask/FastAPI)                            │
│  - POST /api/research → start research task             │
│  - WebSocket /ws/research/{task_id} → stream updates    │
│  - GET /api/status/{task_id} → retrieve task status     │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  Research Orchestrator                                  │
│  - Manages 8-turn research loop                         │
│  - Parses agent outputs (SEARCH/THINK/ANSWER)           │
│  - Delegates to Web Search & LM Studio services         │
│  - Maintains research session state                     │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
    ┌───▼────┐      ┌─────▼──┐
    │  Web   │      │   LM   │
    │ Search │      │ Studio │
    │(DuckGo)│      │ Client │
    └────────┘      └────────┘
```

## Component Design

### 1. **Backend (FastAPI/Flask)**
   - **Endpoint: `POST /api/research`**
     - Input: `{"topic": "...", "max_turns": 8}`
     - Output: `{"task_id": "...", "status": "started"}`
   - **Endpoint: `WebSocket /ws/research/{task_id}`**
     - Streams JSON updates as research progresses
     - Format: `{"type": "action", "turn": 1, "action": "search", "content": "..."}`
   - **Endpoint: `GET /api/status/{task_id}`**
     - Returns current research state and history

### 2. **Research Orchestrator**
   - `ResearchSession` class: manages task lifecycle
   - `agentStep()`: calls LM Studio for next action
   - `parseAction()`: extracts SEARCH/THINK/ANSWER from output
   - `executeSearch()`: queries DuckDuckGo
   - `compressSummary()`: maintains rolling context window
   - Emits events to observer pattern for real-time updates

### 3. **Services**
   - **LMStudioClient**: wraps OpenAI SDK, handles model calls
   - **SearchService**: wraps DuckDuckGo API
   - **StateManager**: in-memory session storage (extensible to DB)

### 4. **Frontend (HTML/CSS/JS)**
   - Topic input form
   - Real-time log viewer (WebSocket listener)
   - Status indicator (turn counter, current action)
   - Final answer display with styling

## Directory Structure

```
lmstudio-autoresearch-local/
├── design.md                          # This file
├── README.md
├── LICENSE
├── AGENTS.md
├── requirements.txt                   # Python dependencies
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app & routes
│   ├── orchestrator.py                # Research orchestrator
│   ├── services/
│   │   ├── __init__.py
│   │   ├── lm_studio_client.py       # LM Studio API wrapper
│   │   ├── search_service.py         # DuckDuckGo wrapper
│   │   └── state_manager.py          # Session state
│   └── models/
│       ├── __init__.py
│       └── schemas.py                 # Pydantic models
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py
│   ├── test_services.py
│   ├── test_api.py
│   └── conftest.py                    # Shared fixtures
├── static/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── .gitignore
```

## Key Design Decisions

1. **FastAPI over Flask**: Better async support for WebSocket streaming, built-in API docs.
2. **WebSocket for real-time**: Lower latency than polling; better UX for streaming updates.
3. **In-memory state (v1)**: Simple, fast for prototyping. Extend with Redis/DB later.
4. **Event emitter pattern**: Decouples orchestrator from API; easier to test and extend.
5. **Pydantic models**: Type safety, automatic API documentation.

## Testing Strategy

- **Unit tests**: Orchestrator, services (mock LM Studio and DuckDuckGo)
- **Integration tests**: API endpoints with in-memory state
- **Fixtures**: Mock LM Studio responses, mock search results

## Deployment Notes

- **Local dev**: `uvicorn app.main:app --reload`
- **Environment**: Set `LM_STUDIO_URL`, `MODEL_NAME` in `.env`
- **Port**: Default 8000 (configurable)

## Future Enhancements

- Persistent storage (SQLite, PostgreSQL)
- Research history/export (JSON, Markdown)
- Multi-session management
- Custom system prompts
- Model selection UI
- Rate limiting
- Error recovery & retries
