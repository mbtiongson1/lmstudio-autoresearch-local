# LM Studio AutoResearch Agent

A real-time research agent that leverages a local LM Studio model to autonomously conduct multi-turn research by searching the web and synthesizing findings.

## Features

- 🤖 **Autonomous Research**: 8-turn iterative research loop with SEARCH → THINK → ANSWER actions.
- 🧭 **API-Only Control Plane**: FastAPI is the only run control surface (start/status/resume/pause/cancel).
- ⚙️ **Out-of-Process Worker**: `train.py` executes research loops in a separate process for isolation and recoverability.
- 💾 **Durable Resume State**: SQLite-backed checkpoints, process metadata, and run events for resuming failed runs.
- 🌐 **Web Search Integration**: DuckDuckGo API for live research data.
- 📡 **Real-time Monitoring**: WebSocket status updates during run execution.
- 🎨 **Modern Web UI**: Responsive frontend with live progress tracking.
- 🧪 **Fully Tested**: 51 unit tests across API, worker runtime, run manager, state store, and LM Studio integration.
- ⚡ **Fast Setup**: `uv` for rapid Python dependency management.

## Quick Start

### Prerequisites

- **LM Studio 0.4.0+**
  - **Server Settings**: Enable "Allow per-request MCPs".
  - **Model**: Recommended to use `ibm/granite-4-micro` or similar models that support tool use and reasoning.
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
Run Manager (app/services/run_manager.py)
    ├─ Worker Runtime (train.py)
    │   ├─ LM Studio Client (app/services/lm_studio_client.py) [V1 API + MCP]
    │   └─ Search Service (app/services/search_service.py)
    └─ State Store (app/services/state_store.py) [SQLite sessions/checkpoints/processes/events]
```

### Key Components

- **LM Studio Client (V1 API)**: Uses the native `/api/v1/chat` endpoint to support reasoning, tool calls, and MCP integrations.
- **Run Manager**: Spawns and controls the isolated `train.py` worker process.
- **State Store**: Durable session/history/checkpoint/process persistence and resume state.

## Run Control Endpoints

- `POST /api/research` - start a new run
- `GET /api/status/{task_id}` - current durable run status
- `POST /api/research/{task_id}/resume` - resume a failed/paused run
- `POST /api/research/{task_id}/pause` - pause a run
- `POST /api/research/{task_id}/cancel` - cancel a run

## Configuration

Set environment variables to customize:

```bash
export LM_STUDIO_V1_URL=http://localhost:1234/api/v1
export MODEL_NAME=ibm/granite-4-micro
export LM_API_TOKEN=your-token-here
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=app --cov-report=html
```

## MCP Integration

The agent automatically configures the **Hugging Face ephemeral MCP server** for every research task. This allows the model to use the `model_search` tool to find trending models on Hugging Face when relevant to the research topic.

### Verifying MCP

A helper script is provided to verify your local LM Studio setup:

```bash
uv run python verify_mcp.py
```

## Troubleshooting

### "Connection refused: localhost:1234"
- Ensure LM Studio is running on the correct URL.
- Ensure "Allow per-request MCPs" is enabled in LM Studio settings.

### "Multiple top-level packages discovered"
- This has been resolved in `pyproject.toml` by explicitly configuring package discovery. Ensure you use `uv sync` to apply changes.

## License

See `LICENSE` file for details.
