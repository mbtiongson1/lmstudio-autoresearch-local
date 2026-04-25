# LM Studio AutoResearch Agent

A real-time research agent that leverages a local LM Studio model to autonomously conduct multi-turn research by searching the web and synthesizing findings.

## Features

- 🤖 **Autonomous Research**: 8-turn iterative research loop with SEARCH → THINK → ANSWER actions.
- 🛠️ **MCP Tool Support**: Native integration with LM Studio 0.4.0+ V1 API for Model Context Protocol tools (e.g., Hugging Face model search).
- 🌐 **Web Search Integration**: DuckDuckGo API for live research data.
- 📡 **Real-time Monitoring**: WebSocket updates showing research progress turn-by-turn.
- 🎨 **Modern Web UI**: Responsive frontend with live progress tracking.
- 🧪 **Fully Tested**: 33 comprehensive unit tests covering all components, including V1 API and MCP logic.
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
Research Orchestrator (app/orchestrator.py)
    ├─ LM Studio Client (services/lm_studio_client.py) [V1 API + MCP]
    ├─ Search Service (services/search_service.py)
    └─ State Manager (services/state_manager.py)
```

### Key Components

- **LM Studio Client (V1 API)**: Uses the native `/api/v1/chat` endpoint to support reasoning, tool calls, and MCP integrations.
- **Orchestrator**: Manages the research loop, injecting MCP tool configurations (like Hugging Face) into every model turn.

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
