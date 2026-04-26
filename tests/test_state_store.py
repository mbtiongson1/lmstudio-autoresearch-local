import sqlite3

from app.services.state_store import StateStore


def test_state_store_initializes_required_schema(tmp_path):
    db_path = tmp_path / "state_store.db"
    store = StateStore(str(db_path))

    task_id = store.create_session("test topic", 8)
    assert task_id

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

    assert "sessions" in table_names
    assert "history_entries" in table_names
    assert "run_checkpoints" in table_names
    assert "run_processes" in table_names
    assert "run_events" in table_names

    session = store.get_session(task_id)
    checkpoint = store.get_checkpoint(task_id)

    assert session is not None
    assert session["topic"] == "test topic"
    assert session["max_turns"] == 8
    assert session["current_turn"] == 0
    assert checkpoint is not None
    assert checkpoint["last_completed_turn"] == 0


def test_commit_turn_is_atomic_on_failure(tmp_path):
    db_path = tmp_path / "state_store.db"
    store = StateStore(str(db_path))
    task_id = store.create_session("atomic topic", 6)

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE run_checkpoints")
        conn.commit()

    before_session = store.get_session(task_id)
    assert before_session is not None
    assert before_session["current_turn"] == 0
    assert store.get_history(task_id) == []

    try:
        store.commit_turn(
            task_id=task_id,
            turn=1,
            action="search",
            content="query",
            summary_snapshot="summary after turn 1",
            worker_state={"last_action": "search"},
        )
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError("Expected OperationalError due to missing run_checkpoints table")

    after_session = store.get_session(task_id)
    assert after_session is not None
    assert after_session["current_turn"] == 0
    assert after_session["summary"] == ""
    assert store.get_history(task_id) == []
