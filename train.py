"""Out-of-process worker runtime for research loop execution."""

from __future__ import annotations

import argparse
from typing import Any, Dict, Optional, Tuple

from app.services.lm_studio_client import LMStudioClient
from app.services.search_service import SearchService

try:
    from app.services.state_store import StateStore
except Exception:  # pragma: no cover - fallback until StateStore lands
    class StateStore:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("StateStore is unavailable in this environment.")


SYSTEM_PROMPT = """You are a research worker. Output exactly one line:
SEARCH: <query>
THINK: <insight>
ANSWER: <final answer>
No extra text."""


def parse_action(raw: str) -> Tuple[str, str]:
    """Parse a strict protocol action line."""
    text = (raw or "").strip()
    for prefix in ("SEARCH:", "THINK:", "ANSWER:"):
        if text.startswith(prefix):
            content = text[len(prefix) :].strip()
            if not content:
                raise ValueError("action content is empty")
            return prefix[:-1], content
    raise ValueError(f"invalid action: {raw}")


def next_turn_from_checkpoint(checkpoint: Optional[Dict[str, Any]]) -> int:
    """Compute the next turn index from durable checkpoint state."""
    if not checkpoint:
        return 1
    last_completed = int(checkpoint.get("last_completed_turn", 0))
    return last_completed + 1


def _build_input(topic: str, summary: str, turn: int, max_turns: int) -> str:
    return (
        f"Topic: {topic}\n"
        f"Summary: {summary}\n"
        f"Turn: {turn}/{max_turns}\n"
        "Return exactly one protocol line."
    )


def _update_summary(summary: str, new_text: str, max_chars: int = 1200) -> str:
    merged = f"{summary}\n{new_text}".strip() if summary else new_text.strip()
    return merged[-max_chars:]


def run_task(task_id: str, db_path: str = "research_history.db") -> Optional[str]:
    """Run research loop for a task using strict SEARCH/THINK/ANSWER protocol."""
    store = StateStore(db_path)
    lm_client = LMStudioClient()
    search_service = SearchService()
    try:
        session = store.get_session(task_id)
        if not session:
            raise ValueError(f"session not found: {task_id}")

        checkpoint = store.get_checkpoint(task_id) or {}
        summary = checkpoint.get("summary_snapshot", "") or ""
        turn = next_turn_from_checkpoint(checkpoint)
        max_turns = int(session.get("max_turns", 8))
        topic = session.get("topic", "")

        while turn <= max_turns:
            raw = lm_client.chat_v1(
                _build_input(topic=topic, summary=summary, turn=turn, max_turns=max_turns),
                system_prompt=SYSTEM_PROMPT,
            )
            action, content = parse_action(raw)

            if action == "SEARCH":
                search_result = search_service.search(content)
                summary = _update_summary(summary, search_result)
                store.commit_turn(task_id, turn, action, content, summary, "running")
            elif action == "THINK":
                summary = _update_summary(summary, content)
                store.commit_turn(task_id, turn, action, content, summary, "running")
            elif action == "ANSWER":
                store.commit_turn(task_id, turn, action, content, summary, "completed")
                store.complete_session(task_id, content)
                return content
            else:  # pragma: no cover - parse_action enforces this
                raise ValueError(f"invalid action: {raw}")

            turn += 1

        raise RuntimeError("max turns reached without ANSWER")
    except ValueError as exc:
        store.fail_session(task_id, str(exc))
        return None
    except Exception as exc:
        store.fail_session(task_id, str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run research worker task.")
    parser.add_argument("--task-id", required=True, help="Session task identifier")
    parser.add_argument(
        "--db-path",
        default="research_history.db",
        help="SQLite database path used by StateStore",
    )
    args = parser.parse_args()
    run_task(task_id=args.task_id, db_path=args.db_path)


if __name__ == "__main__":
    main()
