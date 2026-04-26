"""FastAPI application with research endpoints and WebSocket support"""
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.models.schemas import (
    ResearchRequest,
    ResearchStatus,
    LifecycleResponse,
    ModelLoadRequest,
    ModelUnloadRequest,
)
from app.services.lm_studio_client import LMStudioClient
from app.services.state_store import StateStore
from app.services.run_manager import RunManager

# Load environment variables from .env file
load_dotenv()


# Global instances
lm_client = LMStudioClient()
state_store = StateStore()
run_manager = RunManager(store=state_store)
active_websockets: dict = {}  # {task_id: [websocket, websocket, ...]}


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
    task_id = state_store.create_session(request.topic, request.max_turns)
    try:
        run_manager.start_run(task_id)
    except Exception as e:
        state_store.fail_session(task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start worker: {e}") from e

    return {
        "task_id": task_id,
        "status": "started",
        "topic": request.topic
    }


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """Get the current status of a research task."""
    session = state_store.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")

    return ResearchStatus(
        task_id=session["task_id"],
        status=session["status"],
        current_turn=session["current_turn"],
        max_turns=session.get("max_turns", 8),
        history=state_store.get_history(task_id),
        final_answer=session.get("final_answer"),
        error=session.get("error"),
    )


@app.get("/api/history")
async def get_history(query: str = None):
    """List research history."""
    sessions = state_store.list_sessions(query)
    return [
        {
            "task_id": row["task_id"],
            "topic": row["topic"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in sessions
    ]


@app.get("/api/history/{task_id}")
async def get_session_details(task_id: str):
    """Get full details of a past session."""
    session = state_store.get_session(task_id)
    history = state_store.get_history(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "task_id": session["task_id"],
        "topic": session["topic"],
        "status": session["status"],
        "history": history,
        "final_answer": session.get("final_answer"),
    }


@app.delete("/api/history/{task_id}")
async def delete_session(task_id: str):
    """Delete a session."""
    state_store.delete_session(task_id)
    return {"message": "Session deleted"}


@app.post("/api/research/{task_id}/resume", response_model=LifecycleResponse)
async def resume_research(task_id: str):
    """Resume a failed/paused research task."""
    session = state_store.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        run_manager.resume_run(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return LifecycleResponse(task_id=task_id, status="running", message="resume requested")


@app.post("/api/research/{task_id}/pause", response_model=LifecycleResponse)
async def pause_research(task_id: str):
    """Pause a running research task."""
    session = state_store.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")
    run_manager.pause_run(task_id)
    return LifecycleResponse(task_id=task_id, status="paused", message="pause requested")


@app.post("/api/research/{task_id}/cancel", response_model=LifecycleResponse)
async def cancel_research(task_id: str):
    """Cancel a running research task."""
    session = state_store.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")
    run_manager.cancel_run(task_id)
    return LifecycleResponse(task_id=task_id, status="canceled", message="cancel requested")


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
    session = state_store.get_session(task_id)
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

        # Keep connection alive and stream status snapshots.
        while True:
            await asyncio.sleep(1)
            latest = state_store.get_session(task_id)
            if not latest:
                await websocket.send_json({"type": "error", "message": "Task deleted"})
                return
            await websocket.send_json({
                "type": "status",
                "status": latest["status"],
                "current_turn": latest["current_turn"],
            })
            if latest["status"] in {"completed", "failed", "canceled", "paused"}:
                return
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
