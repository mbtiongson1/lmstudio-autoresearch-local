"""Run manager for out-of-process train worker execution."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Dict, Optional


class RunManager:
    """Controls worker lifecycle for research runs."""

    def __init__(
        self,
        store,
        worker_script: str = "train.py",
        python_executable: Optional[str] = None,
        cwd: Optional[str] = None,
    ):
        self.store = store
        self.worker_script = worker_script
        self.python_executable = python_executable or sys.executable
        self.cwd = cwd or os.getcwd()
        self._procs: Dict[str, subprocess.Popen] = {}

    def _spawn(self, task_id: str) -> subprocess.Popen:
        cmd = [self.python_executable, self.worker_script, "--task-id", task_id]
        return subprocess.Popen(cmd, cwd=self.cwd)

    def _get_live_proc(self, task_id: str) -> Optional[subprocess.Popen]:
        proc = self._procs.get(task_id)
        if proc is None:
            return None
        if proc.poll() is not None:
            self._procs.pop(task_id, None)
            return None
        return proc

    def start_run(self, task_id: str) -> int:
        proc = self._spawn(task_id)
        self._procs[task_id] = proc
        self.store.update_session_status(task_id, "running")
        self.store.insert_process(task_id=task_id, pid=proc.pid)
        self.store.update_heartbeat(task_id=task_id, pid=proc.pid)
        return proc.pid

    def resume_run(self, task_id: str) -> int:
        session = self.store.get_session(task_id)
        if not session:
            raise ValueError(f"session not found for task_id={task_id}")
        if session.get("status") not in {"failed", "paused"}:
            raise ValueError("resume is only allowed for failed or paused sessions")
        self.store.increment_restart_count(task_id)
        return self.start_run(task_id)

    def pause_run(self, task_id: str) -> None:
        proc = self._get_live_proc(task_id)
        if proc is not None:
            os.kill(proc.pid, signal.SIGTERM)
            self._procs.pop(task_id, None)
        self.store.update_session_status(task_id, "paused")

    def cancel_run(self, task_id: str) -> None:
        proc = self._get_live_proc(task_id)
        if proc is not None:
            os.kill(proc.pid, signal.SIGKILL)
            self._procs.pop(task_id, None)
        self.store.update_session_status(task_id, "canceled")
