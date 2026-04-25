from pydantic import BaseModel
from typing import Optional, List


class ResearchRequest(BaseModel):
    topic: str
    max_turns: int = 8


class ResearchStatus(BaseModel):
    task_id: str
    status: str  # "started", "running", "completed", "error"
    current_turn: int
    history: List[dict]


class ActionEvent(BaseModel):
    type: str  # "action", "complete", "error"
    turn: int
    action: str  # "search", "think", "answer"
    content: str
