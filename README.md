# LM Studio AutoResearch Agent

[![Powered by Gaia](https://gaia.tiongson.co/badges/powered-by-gaia.svg)](https://gaia.tiongson.co/)

A real-time research agent that leverages a local LM Studio model to autonomously conduct multi-turn research by searching the web and synthesizing findings.

## Features

- 🤖 **Autonomous Research**: 8-turn iterative research loop with SEARCH → THINK → ANSWER actions
- 🌐 **Web Search Integration**: DuckDuckGo API for live research data
- 📡 **Real-time Monitoring**: WebSocket updates showing research progress turn-by-turn
- 🎨 **Modern Web UI**: Responsive frontend with live progress tracking
- 🧪 **Fully Tested**: 32 comprehensive unit tests covering all components
- ⚡ **Fast Setup**: `uv` for rapid Python dependency management

## Quick Start

### Prerequisites

- **LM Studio** running on `http://localhost:1234/v1` (default configuration)
- **Python 3.9+**
- **uv** package manager (`brew install uv`)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd lmstudio-autoresearch-local

# Install dependencies using uv
uv sync --all-extras

# Run tests to verify setup
uv run pytest tests/ -v
```

### Running the Application

```bash
# Activate the virtual environment (created by uv)
source .venv/bin/activate

# Start the FastAPI server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in your browser.

## Architecture

The application is built with a modular architecture:

```
Frontend (HTML/CSS/JS)
    ↓ HTTP/WebSocket
FastAPI Server (app/main.py)
    ↓
Research Orchestrator (app/orchestrator.py)
    ├─ LM Studio Client (services/lm_studio_client.py)
    ├─ Search Service (services/search_service.py)
    └─ State Manager (services/state_manager.py)
```

### Key Components

- **FastAPI Backend**: REST API + WebSocket endpoints
  - `POST /api/research` - Start a new research task
  - `GET /api/status/{task_id}` - Get task status
  - `WebSocket /ws/research/{task_id}` - Real-time updates

- **Orchestrator**: Manages the research loop
  - Calls LM Studio for next action (SEARCH/THINK/ANSWER)
  - Executes searches via DuckDuckGo
  - Maintains rolling summary of findings

- **Services**: Modular components
  - `LMStudioClient`: OpenAI SDK wrapper for local model
  - `SearchService`: DuckDuckGo API integration
  - `StateManager`: Session state tracking

## Configuration

Set environment variables to customize:

```bash
export LM_STUDIO_URL=http://localhost:1234/v1
export MODEL_NAME=gemma-4-2b
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_services.py -v

# Run with coverage
uv run pytest tests/ --cov=app --cov-report=html
```

### Test Coverage

- **test_services.py**: 11 tests for LM Studio client, search, and state management
- **test_orchestrator.py**: 9 tests for research loop logic and action parsing
- **test_api.py**: 12 tests for API endpoints and schemas

## Development Workflow

### Adding Dependencies

```bash
# Add a new dependency
uv pip install package-name

# Sync environment
uv sync
```

### Running in Development Mode

```bash
# With hot reload
uv run uvicorn app.main:app --reload
```

### Committing Changes

```bash
# Commit with descriptive message
git add .
git commit -m "feat: description of changes"
```

## Project Structure

```
lmstudio-autoresearch-local/
├── app/                           # Main application code
│   ├── main.py                   # FastAPI app & routes
│   ├── orchestrator.py           # Research loop orchestrator
│   ├── models/
│   │   └── schemas.py            # Pydantic models
│   └── services/
│       ├── lm_studio_client.py   # LM Studio wrapper
│       ├── search_service.py     # DuckDuckGo integration
│       └── state_manager.py      # Session management
├── tests/                         # Unit tests
│   ├── test_api.py
│   ├── test_orchestrator.py
│   ├── test_services.py
│   └── conftest.py               # Pytest fixtures
├── static/                        # Frontend assets
│   ├── index.html                # Main page
│   ├── style.css                 # Styling
│   └── script.js                 # Client-side logic
├── pyproject.toml                # Project metadata & dependencies
├── requirements.txt              # Legacy requirements (for reference)
├── design.md                     # Architecture documentation
└── README.md                     # This file
```

## How It Works

1. **User submits a research topic** via the web interface
2. **API creates a research session** and starts the orchestrator
3. **Orchestrator begins 8-turn loop**:
   - Calls LM Studio model to get next action
   - Parses response (SEARCH, THINK, or ANSWER)
   - If SEARCH: queries DuckDuckGo and updates findings
   - If THINK: reflects on findings
   - If ANSWER: returns final answer
4. **WebSocket streams real-time updates** to frontend
5. **Frontend displays** research progress and final answer

## Example Research Flow

```
Turn 1: SEARCH → "climate change causes"
→ DuckDuckGo returns: "CO2, methane, greenhouse gases..."

Turn 2: SEARCH → "climate change impact"
→ DuckDuckGo returns: "Rising temperatures, extreme weather..."

Turn 3: THINK → "Combining findings: primary causes are greenhouse gases..."

Turn 4-7: Alternating SEARCH and THINK actions...

Turn 8: ANSWER → "Climate change is primarily caused by human greenhouse gas 
emissions, leading to rising temperatures and extreme weather events."
```

## Troubleshooting

### "Connection refused: localhost:1234"
- Ensure LM Studio is running on the correct URL
- Check `LM_STUDIO_URL` environment variable
- LM Studio should be accessible at `http://localhost:1234/v1`

### Tests failing with import errors
- Ensure dependencies are synced: `uv sync --all-extras`
- Check Python version compatibility (3.9+)

### WebSocket not connecting
- Check browser console for errors
- Verify FastAPI server is running with WebSocket support
- Check firewall settings

## Performance Notes

- LM Studio model inference time depends on hardware
- DuckDuckGo API is rate-limited; expect 500ms-2s per search
- Frontend updates stream in real-time via WebSocket
- In-memory state management suitable for development; consider Redis/DB for production

## Future Enhancements

- [ ] Persistent database for research history
- [ ] Custom system prompts per research topic
- [ ] Multiple LM Studio model selection
- [ ] Research export (PDF, Markdown)
- [ ] Rate limiting and usage statistics
- [ ] Authentication and multi-user support
- [ ] Error recovery and retry logic

## License

See `LICENSE` file for details.

## Contributing

Commit guidelines:
- Use conventional commits (`feat:`, `fix:`, `test:`, `docs:`)
- Run tests before committing: `uv run pytest tests/ -v`
- Update documentation for significant changes
