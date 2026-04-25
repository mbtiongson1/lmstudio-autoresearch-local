"""FastAPI application with research endpoints and WebSocket support"""
import asyncio
import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.models.schemas import (
    ResearchRequest, ResearchStatus,
    ModelsListResponse, ModelLoadRequest, ModelUnloadRequest
)
from app.services.lm_studio_client import LMStudioClient
from app.services.state_manager import StateManager
from app.services import db_manager
from app.orchestrator import ResearchOrchestrator

# Load environment variables from .env file
load_dotenv()


# Global instances
state_manager = StateManager()
lm_client = LMStudioClient()
active_websockets: dict = {}  # {task_id: [websocket, websocket, ...]}


def on_research_event(task_id: str, event: dict):
    """Callback called by orchestrator when an event occurs."""
    if task_id in active_websockets:
        for ws in active_websockets[task_id]:
            try:
                # This will be called from async context, so we schedule it
                asyncio.create_task(_send_ws_update(ws, event))
            except Exception as e:
                print(f"Error sending to websocket: {e}")


async def _send_ws_update(ws: WebSocket, event: dict):
    """Send update to websocket (async helper)."""
    try:
        await ws.send_json(event)
    except Exception as e:
        print(f"WebSocket send error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    print("🚀 AutoResearch Agent API starting...")
    yield
    print("🛑 AutoResearch Agent API shutting down...")


app = FastAPI(
    title="LM Studio AutoResearch Agent",
    description="Real-time research agent with local LM Studio",
    lifespan=lifespan
)


# Serve static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    print("Warning: static directory not found")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    return FileResponse("static/index.html")


@app.post("/api/research")
async def start_research(request: ResearchRequest):
    """Start a new research task."""
    task_id = state_manager.create_session(request.topic, request.max_turns)

    # Run research in background
    async def run_research():
        try:
            orchestrator = ResearchOrchestrator(lm_client, state_manager, callback=on_research_event)
            result = orchestrator.research(task_id, request.topic, request.max_turns)
            return result
        except Exception as e:
            state_manager.mark_error(task_id, str(e))
            raise

    # Start research as a background task
    asyncio.create_task(run_research())

    return {
        "task_id": task_id,
        "status": "started",
        "topic": request.topic
    }


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """Get the current status of a research task."""
    session = state_manager.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")

    return ResearchStatus(
        task_id=session["task_id"],
        status=session["status"],
        current_turn=session["current_turn"],
        history=session["history"]
    )


@app.get("/api/history")
async def get_history(query: str = None):
    """List research history."""
    sessions = db_manager.get_all_sessions(query)
    return [
        {
            "task_id": row[0],
            "topic": row[1],
            "status": row[2],
            "created_at": row[3]
        } for row in sessions
    ]


@app.get("/api/history/{task_id}")
async def get_session_details(task_id: str):
    """Get full details of a past session."""
    session, history = db_manager.get_session_details(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "task_id": session[0],
        "topic": session[1],
        "status": session[2],
        "history": [{"turn": h[0], "action": h[1], "content": h[2], "timestamp": h[3]} for h in history],
        "final_answer": session[6]
    }


@app.delete("/api/history/{task_id}")
async def delete_session(task_id: str):
    """Delete a session."""
    db_manager.delete_session(task_id)
    return {"message": "Session deleted"}


@app.post("/api/models/load")
async def load_model(request: ModelLoadRequest):
    """Load a specific model."""
    try:
        return lm_client.load_model(
            request.model,
            context_length=request.context_length,
            eval_batch_size=request.eval_batch_size,
            flash_attention=request.flash_attention,
            num_experts=request.num_experts,
            offload_kv_cache_to_gpu=request.offload_kv_cache_to_gpu,
            echo_load_config=request.echo_load_config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/unload")
async def unload_model(request: ModelUnloadRequest):
    """Unload a specific model instance."""
    try:
        return lm_client.unload_model(request.instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models")
async def list_models():
    """List available models."""
    try:
        return lm_client.list_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/set")
async def set_model(request: ModelLoadRequest):
    """Set the active model for research."""
    try:
        lm_client.set_model(request.model)
        return {"status": "success", "model": request.model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/research/{task_id}")
async def websocket_research(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time research updates."""
    await websocket.accept()

    # Check if task exists
    session = state_manager.get_session(task_id)
    if not session:
        await websocket.send_json({"error": "Task not found"})
        await websocket.close()
        return

    # Register websocket
    if task_id not in active_websockets:
        active_websockets[task_id] = []
    active_websockets[task_id].append(websocket)

    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "status": session["status"],
            "current_turn": session["current_turn"]
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Clients can send heartbeat or commands if needed
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Unregister websocket
        if task_id in active_websockets:
            active_websockets[task_id].remove(websocket)
            if not active_websockets[task_id]:
                del active_websockets[task_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
