"""Unit tests for run manager worker lifecycle."""

from unittest.mock import Mock, patch

import pytest

from app.services.run_manager import RunManager


def test_start_run_spawns_train_worker_and_marks_running():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "queued", "max_turns": 3}

    with patch("app.services.run_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 777
        mgr = RunManager(store=store)
        pid = mgr.start_run("t1")

    assert pid == 777
    mock_popen.assert_called_once()
    store.update_session_status.assert_called_once_with("t1", "running")
    store.insert_process.assert_called_once_with(task_id="t1", pid=777)
    store.update_heartbeat.assert_called_once_with(task_id="t1", pid=777)


def test_resume_requires_failed_or_paused_status():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "running"}
    mgr = RunManager(store=store)

    with pytest.raises(ValueError, match="failed or paused"):
        mgr.resume_run("t1")


def test_resume_run_increments_restart_count_and_spawns_worker():
    store = Mock()
    store.get_session.return_value = {"task_id": "t1", "status": "failed", "max_turns": 3}

    with patch("app.services.run_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 1234
        mgr = RunManager(store=store)
        pid = mgr.resume_run("t1")

    assert pid == 1234
    store.increment_restart_count.assert_called_once_with("t1")
    store.update_session_status.assert_called_once_with("t1", "running")
    store.insert_process.assert_called_once_with(task_id="t1", pid=1234)
    store.update_heartbeat.assert_called_once_with(task_id="t1", pid=1234)


def test_pause_run_terminates_process_and_marks_paused():
    store = Mock()
    proc = Mock()
    proc.pid = 777
    proc.poll.return_value = None

    mgr = RunManager(store=store)
    mgr._procs["t1"] = proc

    with patch("app.services.run_manager.os.kill") as mock_kill:
        mgr.pause_run("t1")

    mock_kill.assert_called_once()
    args, _kwargs = mock_kill.call_args
    assert args[0] == 777
    store.update_session_status.assert_called_once_with("t1", "paused")
    assert "t1" not in mgr._procs


def test_cancel_run_kills_process_and_marks_canceled():
    store = Mock()
    proc = Mock()
    proc.pid = 888
    proc.poll.return_value = None

    mgr = RunManager(store=store)
    mgr._procs["t1"] = proc

    with patch("app.services.run_manager.os.kill") as mock_kill:
        mgr.cancel_run("t1")

    mock_kill.assert_called_once()
    args, _kwargs = mock_kill.call_args
    assert args[0] == 888
    store.update_session_status.assert_called_once_with("t1", "canceled")
    assert "t1" not in mgr._procs


def test_pause_and_cancel_without_live_process_still_update_status():
    store = Mock()
    mgr = RunManager(store=store)

    with patch("app.services.run_manager.os.kill") as mock_kill:
        mgr.pause_run("t1")
        mgr.cancel_run("t2")

    mock_kill.assert_not_called()
    store.update_session_status.assert_any_call("t1", "paused")
    store.update_session_status.assert_any_call("t2", "canceled")
