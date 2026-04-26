# LM Studio API-Only Worker Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the app so FastAPI is the only run-control surface while `train.py` runs the research loop out-of-process with durable checkpoints and resume support.

**Architecture:** Introduce a DB-backed state store and run manager, then move loop policy into `train.py` worker runtime. FastAPI endpoints orchestrate worker lifecycle (`start`, `status`, `resume`, `pause`, `cancel`) and read durable state from SQLite instead of in-memory state.

**Tech Stack:** Python 3.9+, FastAPI, sqlite3, subprocess, pytest, httpx, requests.

---

## File Structure and Responsibilities

- Create: `app/services/state_store.py`
  - Single source of truth for sessions, checkpoints, process rows, and run events.
- Create: `app/services/run_manager.py`
  - Spawns/controls worker process (`train.py`) and maps lifecycle transitions to state store updates.
- Create: `train.py`
  - Worker entrypoint and loop policy owner (`SEARCH/THINK/ANSWER` protocol).
- Create: `tests/test_state_store.py`
  - Verifies DB schema and atomic turn-commit behavior.
- Create: `tests/test_run_manager.py`
  - Verifies worker spawn, pause/cancel, and resume gating.
- Create: `tests/test_train_worker.py`
  - Verifies protocol parsing and resume-from-checkpoint turn progression.
- Modify: `app/main.py`
  - Replace in-memory orchestration with run-manager/state-store control flow.
- Modify: `app/models/schemas.py`
  - Add request/response models for resume/pause/cancel and richer status payload.
- Modify: `tests/test_api.py`
  - Re-point API tests to new lifecycle endpoints and durable status model.
- Modify: `README.md`
  - Document API-only worker architecture and new control endpoints.

### Task 1: Build Durable State Store Foundation

**Files:**
- Create: `tests/test_state_store.py`
- Create: `app/services/state_store.py`

- [ ] **Step 1: Write the failing state store tests**

```python
# tests/test_state_store.py
import sqlite3
from app.services.state_store import StateStore


def test_init_schema_creates_checkpoint_and_process_tables(tmp_path):
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()

    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()

    assert "sessions" in tables
    assert "history_entries" in tables
    assert "run_checkpoints" in tables
    assert "run_processes" in tables
    assert "run_events" in tables


def test_commit_turn_updates_history_session_and_checkpoint_atomically(tmp_path):
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()
    task_id = store.create_session(topic="test topic", max_turns=3)

    store.commit_turn(
        task_id=task_id,
        turn=1,
        action="search",
        content="query",
        summary_snapshot="result summary",
        status="running",
    )

    session = store.get_session(task_id)
    history = store.get_history(task_id)
    checkpoint = store.get_checkpoint(task_id)

    assert session["current_turn"] == 1
    assert len(history) == 1
    assert history[0]["action"] == "search"
    assert checkpoint["last_completed_turn"] == 1
    assert checkpoint["summary_snapshot"] == "result summary"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_state_store.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.state_store'`

- [ ] **Step 3: Implement `StateStore` and schema initialization**

```python
# app/services/state_store.py
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class StateStore:
    def __init__(self, db_path: str = "research_history.db"):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                task_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                max_turns INTEGER NOT NULL,
                current_turn INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                final_answer TEXT,
                error TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS history_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                turn INTEGER NOT NULL,
                action TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS run_checkpoints (
                task_id TEXT PRIMARY KEY,
                last_completed_turn INTEGER NOT NULL,
                summary_snapshot TEXT NOT NULL,
                worker_state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS run_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL,
                exit_code INTEGER,
                failure_reason TEXT,
                restart_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()
```

- [ ] **Step 4: Add CRUD and atomic `commit_turn` methods**

```python
# app/services/state_store.py (append)
import json

    def create_session(self, topic: str, max_turns: int) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sessions (task_id, topic, status, max_turns, current_turn, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, topic, "queued", max_turns, 0, now),
        )
        cur.execute(
            "INSERT INTO run_checkpoints (task_id, last_completed_turn, summary_snapshot, worker_state_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, 0, "", "{}", now),
        )
        conn.commit()
        conn.close()
        return task_id

    def get_session(self, task_id: str):
        conn = self._conn()
        row = conn.execute("SELECT * FROM sessions WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_history(self, task_id: str):
        conn = self._conn()
        rows = conn.execute(
            "SELECT turn, action, content, timestamp FROM history_entries WHERE task_id = ? ORDER BY turn ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_checkpoint(self, task_id: str):
        conn = self._conn()
        row = conn.execute("SELECT * FROM run_checkpoints WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_session_status(self, task_id: str, status: str) -> None:
        now = datetime.now().isoformat()
        conn = self._conn()
        if status == "running":
            conn.execute("UPDATE sessions SET status = ?, started_at = COALESCE(started_at, ?) WHERE task_id = ?", (status, now, task_id))
        elif status in {"completed", "failed", "canceled"}:
            conn.execute("UPDATE sessions SET status = ?, completed_at = ? WHERE task_id = ?", (status, now, task_id))
        else:
            conn.execute("UPDATE sessions SET status = ? WHERE task_id = ?", (status, task_id))
        conn.commit()
        conn.close()

    def insert_process(self, task_id: str, pid: int) -> None:
        now = datetime.now().isoformat()
        conn = self._conn()
        conn.execute(
            "INSERT INTO run_processes (task_id, pid, started_at, heartbeat_at, restart_count) VALUES (?, ?, ?, ?, 0)",
            (task_id, pid, now, now),
        )
        conn.commit()
        conn.close()

    def commit_turn(self, task_id: str, turn: int, action: str, content: str, summary_snapshot: str, status: str) -> None:
        now = datetime.now().isoformat()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute(
            "INSERT INTO history_entries (task_id, turn, action, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (task_id, turn, action, content, now),
        )
        cur.execute(
            "UPDATE sessions SET current_turn = ?, status = ? WHERE task_id = ?",
            (turn, status, task_id),
        )
        cur.execute(
            "UPDATE run_checkpoints SET last_completed_turn = ?, summary_snapshot = ?, worker_state_json = ?, updated_at = ? WHERE task_id = ?",
            (turn, summary_snapshot, json.dumps({"turn": turn}), now, task_id),
        )
        conn.commit()
        conn.close()

    def complete_session(self, task_id: str, final_answer: str) -> None:
        conn = self._conn()
        conn.execute(
            "UPDATE sessions SET status = ?, final_answer = ?, completed_at = ? WHERE task_id = ?",
            ("completed", final_answer, datetime.now().isoformat(), task_id),
        )
        conn.commit()
        conn.close()

    def fail_session(self, task_id: str, error: str) -> None:
        conn = self._conn()
        conn.execute(
            "UPDATE sessions SET status = ?, error = ?, completed_at = ? WHERE task_id = ?",
            ("failed", error, datetime.now().isoformat(), task_id),
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_state_store.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/state_store.py tests/test_state_store.py
git commit -m "feat: add durable state store with checkpoint tables"
```

### Task 2: Add Worker Lifecycle Run Manager

**Files:**
- Create: `tests/test_run_manager.py`
- Create: `app/services/run_manager.py`

- [ ] **Step 1: Write failing run manager tests**

```python
# tests/test_run_manager.py
from unittest.mock import Mock, patch
from app.services.run_manager import RunManager


def test_start_run_spawns_train_worker_and_marks_running():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "queued", "max_turns": 3}

    with patch("app.services.run_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 777
        mgr = RunManager(store=store)
        mgr.start_run("t1")

    store.update_session_status.assert_called_with("t1", "running")
    store.insert_process.assert_called()


def test_resume_requires_failed_or_paused_status():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "running"}
    mgr = RunManager(store=store)

    try:
        mgr.resume_run("t1")
        assert False, "resume_run should raise for running sessions"
    except ValueError as exc:
        assert "failed or paused" in str(exc)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_run_manager.py -v`  
Expected: FAIL with `ModuleNotFoundError` for `app.services.run_manager`

- [ ] **Step 3: Implement minimal run manager**

```python
# app/services/run_manager.py
import os
import signal
import subprocess
import sys
from typing import Dict


class RunManager:
    def __init__(self, store):
        self.store = store
        self._procs: Dict[str, subprocess.Popen] = {}

    def _spawn(self, task_id: str) -> subprocess.Popen:
        cmd = [sys.executable, "train.py", "--task-id", task_id]
        return subprocess.Popen(cmd, cwd=os.getcwd())

    def start_run(self, task_id: str) -> int:
        proc = self._spawn(task_id)
        self._procs[task_id] = proc
        self.store.update_session_status(task_id, "running")
        self.store.insert_process(task_id=task_id, pid=proc.pid)
        return proc.pid

    def resume_run(self, task_id: str) -> int:
        session = self.store.get_session(task_id)
        if session["status"] not in {"failed", "paused"}:
            raise ValueError("resume is only allowed for failed or paused sessions")
        return self.start_run(task_id)

    def pause_run(self, task_id: str) -> None:
        proc = self._procs.get(task_id)
        if proc is not None:
            os.kill(proc.pid, signal.SIGTERM)
        self.store.update_session_status(task_id, "paused")

    def cancel_run(self, task_id: str) -> None:
        proc = self._procs.get(task_id)
        if proc is not None:
            os.kill(proc.pid, signal.SIGKILL)
        self.store.update_session_status(task_id, "canceled")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_run_manager.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/run_manager.py tests/test_run_manager.py
git commit -m "feat: add run manager for out-of-process train worker"
```

### Task 3: Implement `train.py` Worker Runtime and Protocol Loop

**Files:**
- Create: `tests/test_train_worker.py`
- Create: `train.py`

- [ ] **Step 1: Write failing worker tests**

```python
# tests/test_train_worker.py
from train import parse_action, next_turn_from_checkpoint


def test_parse_action_accepts_search_think_answer():
    assert parse_action("SEARCH: query") == ("search", "query")
    assert parse_action("THINK: insight") == ("think", "insight")
    assert parse_action("ANSWER: done") == ("answer", "done")


def test_next_turn_from_checkpoint():
    assert next_turn_from_checkpoint({"last_completed_turn": 0}) == 1
    assert next_turn_from_checkpoint({"last_completed_turn": 4}) == 5
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_train_worker.py -v`  
Expected: FAIL with import error for `train.py` symbols

- [ ] **Step 3: Implement worker parsing and resume helpers**

```python
# train.py
import argparse
from typing import Tuple


def parse_action(raw: str) -> Tuple[str, str]:
    raw = raw.strip()
    if raw.startswith("SEARCH:"):
        return "search", raw.split(":", 1)[1].strip()
    if raw.startswith("THINK:"):
        return "think", raw.split(":", 1)[1].strip()
    if raw.startswith("ANSWER:"):
        return "answer", raw.split(":", 1)[1].strip()
    return "unknown", raw


def next_turn_from_checkpoint(checkpoint: dict) -> int:
    return int(checkpoint.get("last_completed_turn", 0)) + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    print(f"worker boot for task_id={args.task_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add loop skeleton with durable commit boundaries**

```python
# train.py (append)
from app.services.state_store import StateStore
from app.services.lm_studio_client import LMStudioClient
from app.services.search_service import SearchService

SYSTEM_PROMPT = """You are a research agent. Output exactly one line:
SEARCH: <query>
THINK: <insight>
ANSWER: <final answer>"""


def run_task(task_id: str, db_path: str = "research_history.db") -> None:
    store = StateStore(db_path)
    lm = LMStudioClient()
    session = store.get_session(task_id)
    checkpoint = store.get_checkpoint(task_id)
    turn = next_turn_from_checkpoint(checkpoint)
    summary = checkpoint["summary_snapshot"]

    while turn <= session["max_turns"]:
        prompt = f"Topic: {session['topic']}\nFindings: {summary}\nTurn: {turn}/{session['max_turns']}"
        raw = lm.chat_v1(prompt, system_prompt=SYSTEM_PROMPT)
        action, content = parse_action(raw)
        if action == "search":
            summary = (summary + " | " + SearchService.search(content, max_chars=200))[-500:]
            store.commit_turn(task_id, turn, action, content, summary, "running")
        elif action == "think":
            store.commit_turn(task_id, turn, action, content, summary, "running")
        elif action == "answer":
            store.commit_turn(task_id, turn, action, content, summary, "completed")
            store.complete_session(task_id, content)
            return
        else:
            store.fail_session(task_id, f"invalid action: {raw}")
            raise RuntimeError(f"invalid action: {raw}")
        turn += 1
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_train_worker.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add train.py tests/test_train_worker.py
git commit -m "feat: add train.py worker protocol and resume helpers"
```

### Task 4: Refactor API to FastAPI-Only Control Plane

**Files:**
- Modify: `app/models/schemas.py`
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests for lifecycle endpoints**

```python
# tests/test_api.py (add)
def test_resume_endpoint_exists_and_returns_200(client):
    response = client.post("/api/research/task-1/resume")
    assert response.status_code in {200, 404}


def test_pause_endpoint_exists_and_returns_200(client):
    response = client.post("/api/research/task-1/pause")
    assert response.status_code in {200, 404}


def test_cancel_endpoint_exists_and_returns_200(client):
    response = client.post("/api/research/task-1/cancel")
    assert response.status_code in {200, 404}
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_api.py -v`  
Expected: FAIL with `405`/`404` for missing lifecycle endpoints

- [ ] **Step 3: Add lifecycle schema models**

```python
# app/models/schemas.py (add)
class LifecycleResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ResearchStatusV2(BaseModel):
    task_id: str
    status: str
    current_turn: int
    max_turns: int
    history: List[dict]
    final_answer: Optional[str] = None
    error: Optional[str] = None
```

- [ ] **Step 4: Wire API endpoints to `StateStore` + `RunManager`**

```python
# app/main.py (core changes)
from app.services.state_store import StateStore
from app.services.run_manager import RunManager

store = StateStore()
store.init_schema()
run_manager = RunManager(store=store)

@app.post("/api/research")
async def start_research(request: ResearchRequest):
    task_id = store.create_session(topic=request.topic, max_turns=request.max_turns)
    run_manager.start_run(task_id)
    return {"task_id": task_id, "status": "started", "topic": request.topic}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    session = store.get_session(task_id)
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")
    return ResearchStatusV2(
        task_id=session["task_id"],
        status=session["status"],
        current_turn=session["current_turn"],
        max_turns=session["max_turns"],
        history=store.get_history(task_id),
        final_answer=session.get("final_answer"),
        error=session.get("error"),
    )

@app.post("/api/research/{task_id}/resume")
async def resume_research(task_id: str):
    run_manager.resume_run(task_id)
    return {"task_id": task_id, "status": "running", "message": "resume requested"}

@app.post("/api/research/{task_id}/pause")
async def pause_research(task_id: str):
    run_manager.pause_run(task_id)
    return {"task_id": task_id, "status": "paused", "message": "pause requested"}

@app.post("/api/research/{task_id}/cancel")
async def cancel_research(task_id: str):
    run_manager.cancel_run(task_id)
    return {"task_id": task_id, "status": "canceled", "message": "cancel requested"}
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_api.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/models/schemas.py tests/test_api.py
git commit -m "feat: add api lifecycle control for worker runs"
```

### Task 5: Complete Resume/Failure Semantics and Process Tracking

**Files:**
- Modify: `app/services/state_store.py`
- Modify: `app/services/run_manager.py`
- Modify: `tests/test_run_manager.py`
- Modify: `tests/test_state_store.py`

- [ ] **Step 1: Write failing tests for failed->resume flow**

```python
# tests/test_run_manager.py (add)
def test_resume_increments_restart_count():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "failed"}
    with patch("app.services.run_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 888
        mgr = RunManager(store=store)
        mgr.resume_run("t1")
    store.increment_restart_count.assert_called_with("t1")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_run_manager.py::test_resume_increments_restart_count -v`  
Expected: FAIL because `increment_restart_count` is not called

- [ ] **Step 3: Implement restart tracking and heartbeat updates**

```python
# app/services/run_manager.py (update)
    def start_run(self, task_id: str) -> int:
        proc = self._spawn(task_id)
        self._procs[task_id] = proc
        self.store.update_session_status(task_id, "running")
        self.store.insert_process(task_id=task_id, pid=proc.pid)
        self.store.update_heartbeat(task_id, pid=proc.pid)
        return proc.pid

    def resume_run(self, task_id: str) -> int:
        session = self.store.get_session(task_id)
        if session["status"] not in {"failed", "paused"}:
            raise ValueError("resume is only allowed for failed or paused sessions")
        self.store.increment_restart_count(task_id)
        return self.start_run(task_id)
```

- [ ] **Step 4: Implement missing state-store methods**

```python
# app/services/state_store.py (add)
    def increment_restart_count(self, task_id: str) -> None:
        conn = self._conn()
        conn.execute(
            """UPDATE run_processes
               SET restart_count = restart_count + 1
               WHERE id = (SELECT id FROM run_processes WHERE task_id = ? ORDER BY id DESC LIMIT 1)""",
            (task_id,),
        )
        conn.commit()
        conn.close()

    def update_heartbeat(self, task_id: str, pid: int) -> None:
        now = datetime.now().isoformat()
        conn = self._conn()
        conn.execute(
            "UPDATE run_processes SET heartbeat_at = ? WHERE task_id = ? AND pid = ?",
            (now, task_id, pid),
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 5: Run targeted tests**

Run: `uv run pytest tests/test_run_manager.py tests/test_state_store.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/run_manager.py app/services/state_store.py tests/test_run_manager.py tests/test_state_store.py
git commit -m "feat: add restart-count and heartbeat process tracking"
```

### Task 6: Remove In-Memory Loop Ownership and Final Regression Pass

**Files:**
- Modify: `app/main.py`
- Modify: `app/orchestrator.py`
- Modify: `app/services/state_manager.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_orchestrator.py`
- Modify: `tests/test_services.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing regression tests proving API does not rely on `StateManager`**

```python
# tests/test_services.py (add)
def test_state_manager_is_not_required_for_api_startup():
    from app.main import app
    assert app is not None
```

- [ ] **Step 2: Run regression tests to capture current dependency**

Run: `uv run pytest tests/test_services.py::test_state_manager_is_not_required_for_api_startup -v`  
Expected: FAIL if API import still depends on in-memory session state

- [ ] **Step 3: Remove orchestrator/state manager as runtime owners**

```python
# app/orchestrator.py
class ResearchOrchestrator:
    def __init__(self, *args, **kwargs):
        self.message = "ResearchOrchestrator is deprecated. Use FastAPI + RunManager + train.py worker."

    def research(self, *args, **kwargs):
        raise RuntimeError(self.message)
```

```python
# app/services/state_manager.py
from app.services.state_store import StateStore

class StateManager:
    def __init__(self):
        self._store = StateStore()

    def create_session(self, topic: str, max_turns: int = 8) -> str:
        return self._store.create_session(topic=topic, max_turns=max_turns)
```

```python
# tests/conftest.py (remove in-memory dependency)
from app.services.state_store import StateStore

@pytest.fixture
def state_manager(tmp_path):
    store = StateStore(str(tmp_path / "test.db"))
    store.init_schema()
    return store
```

- [ ] **Step 4: Update README architecture and API endpoint docs**

```markdown
## Architecture
FastAPI is the only run-control interface.
`train.py` executes research loops out-of-process.
Run state, checkpoints, and process metadata are persisted in SQLite.

### Lifecycle Endpoints
- POST /api/research
- GET /api/status/{task_id}
- POST /api/research/{task_id}/resume
- POST /api/research/{task_id}/pause
- POST /api/research/{task_id}/cancel
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/orchestrator.py app/services/state_manager.py tests/conftest.py tests/test_orchestrator.py tests/test_services.py README.md
git commit -m "refactor: switch runtime ownership to api control plane and worker"
```

## Final Verification Checklist

- [ ] `uv run pytest tests/test_state_store.py -v`
- [ ] `uv run pytest tests/test_run_manager.py -v`
- [ ] `uv run pytest tests/test_train_worker.py -v`
- [ ] `uv run pytest tests/test_api.py -v`
- [ ] `uv run pytest tests/ -v`
- [ ] Manual smoke:
  - Start API: `uv run uvicorn app.main:app --reload --port 8000`
  - Start run: `curl -X POST localhost:8000/api/research -H "Content-Type: application/json" -d '{"topic":"local llm research","max_turns":3}'`
  - Resume failed run: `curl -X POST localhost:8000/api/research/<task_id>/resume`
  - Confirm status transitions via `/api/status/<task_id>`
