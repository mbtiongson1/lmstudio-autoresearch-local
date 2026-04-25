"""In-memory session state manager"""
import uuid
from typing import Dict, Any, List
from datetime import datetime


class StateManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, topic: str, max_turns: int = 8) -> str:
        """Create a new research session and return its ID."""
        task_id = str(uuid.uuid4())
        self.sessions[task_id] = {
            "task_id": task_id,
            "topic": topic,
            "max_turns": max_turns,
            "status": "started",
            "current_turn": 0,
            "summary": "",
            "history": [],
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "final_answer": None
        }
        return task_id

    def get_session(self, task_id: str) -> Dict[str, Any]:
        """Get session by task ID."""
        return self.sessions.get(task_id)

    def update_session(self, task_id: str, **kwargs):
        """Update session state."""
        if task_id in self.sessions:
            self.sessions[task_id].update(kwargs)

    def add_history_entry(self, task_id: str, turn: int, action: str, content: str):
        """Add a history entry to the session."""
        if task_id in self.sessions:
            self.sessions[task_id]["history"].append({
                "turn": turn,
                "action": action,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })

    def update_summary(self, task_id: str, summary: str):
        """Update the rolling summary."""
        if task_id in self.sessions:
            self.sessions[task_id]["summary"] = summary

    def get_summary(self, task_id: str) -> str:
        """Get current summary."""
        session = self.get_session(task_id)
        return session["summary"] if session else ""

    def mark_started(self, task_id: str):
        """Mark session as running."""
        if task_id in self.sessions:
            self.sessions[task_id]["status"] = "running"
            self.sessions[task_id]["started_at"] = datetime.now().isoformat()

    def mark_completed(self, task_id: str, final_answer: str):
        """Mark session as completed."""
        if task_id in self.sessions:
            self.sessions[task_id]["status"] = "completed"
            self.sessions[task_id]["final_answer"] = final_answer
            self.sessions[task_id]["completed_at"] = datetime.now().isoformat()

    def mark_error(self, task_id: str, error: str):
        """Mark session as errored."""
        if task_id in self.sessions:
            self.sessions[task_id]["status"] = "error"
            self.sessions[task_id]["error"] = error
