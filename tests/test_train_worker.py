"""Tests for train.py worker runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

import train


def test_parse_action_search() -> None:
    action, content = train.parse_action("SEARCH: lm studio mcp")
    assert action == "SEARCH"
    assert content == "lm studio mcp"


def test_parse_action_think() -> None:
    action, content = train.parse_action("THINK: this is a useful synthesis")
    assert action == "THINK"
    assert content == "this is a useful synthesis"


def test_parse_action_answer() -> None:
    action, content = train.parse_action("ANSWER: here is the final response")
    assert action == "ANSWER"
    assert content == "here is the final response"


def test_parse_action_invalid_raises() -> None:
    with pytest.raises(ValueError):
        train.parse_action("INVALID: nope")


def test_next_turn_from_checkpoint() -> None:
    assert train.next_turn_from_checkpoint(None) == 1
    assert train.next_turn_from_checkpoint({"last_completed_turn": 0}) == 1
    assert train.next_turn_from_checkpoint({"last_completed_turn": 4}) == 5


def test_run_task_loop_calls_commit_and_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: List[Tuple[int, str, str, str]] = []
    complete_calls: List[str] = []
    fail_calls: List[str] = []

    class FakeStateStore:
        def __init__(self, _db_path: str) -> None:
            pass

        def get_session(self, _task_id: str) -> Dict[str, Any]:
            return {"topic": "local llm research", "max_turns": 5}

        def get_checkpoint(self, _task_id: str) -> Dict[str, Any]:
            return {"last_completed_turn": 0, "summary_snapshot": ""}

        def commit_turn(
            self,
            _task_id: str,
            turn: int,
            action: str,
            content: str,
            summary_snapshot: str,
            _status: str,
        ) -> None:
            commits.append((turn, action, content, summary_snapshot))

        def complete_session(self, _task_id: str, final_answer: str) -> None:
            complete_calls.append(final_answer)

        def fail_session(self, _task_id: str, reason: str) -> None:
            fail_calls.append(reason)

    class FakeLMStudioClient:
        def __init__(self) -> None:
            self.outputs = iter(
                [
                    "SEARCH: best local llm tools",
                    "THINK: consolidate search findings",
                    "ANSWER: LM Studio can run this autoresearch loop through API control.",
                ]
            )

        def chat_v1(self, *_args: Any, **_kwargs: Any) -> str:
            return next(self.outputs)

    class FakeSearchService:
        def search(self, _query: str) -> str:
            return "search-results"

    monkeypatch.setattr(train, "StateStore", FakeStateStore)
    monkeypatch.setattr(train, "LMStudioClient", FakeLMStudioClient)
    monkeypatch.setattr(train, "SearchService", FakeSearchService)

    result = train.run_task("task-123", db_path=":memory:")

    assert result == "LM Studio can run this autoresearch loop through API control."
    assert [item[1] for item in commits] == ["SEARCH", "THINK", "ANSWER"]
    assert len(complete_calls) == 1
    assert fail_calls == []

