from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AgentState(Record):
    current_goal: str = "Understand the current situation and begin the adventure."
    secondary_goals: list[str] = Field(default_factory=list)
    current_hypotheses: list[str] = Field(default_factory=list)
    current_location_description: str = "Unknown"
    recent_observations: list[str] = Field(default_factory=list)
    active_plan: list[str] = Field(default_factory=list)
    status: Literal["idle", "running", "paused", "need_help", "stopped", "emergency_stopped", "error"] = "idle"
    iteration: int = 0
    objective_failures: int = 0
    low_confidence_streak: int = 0
    no_progress_seconds: float = 0
    system_errors: int = 0
    pending_action: dict | None = None
    pending_help: dict | None = None
    statistics: dict[str, int] = Field(default_factory=lambda: {
        "decisions": 0, "actions": 0, "successes": 0, "failures": 0,
        "uncertain": 0, "reflections": 0, "help_requests": 0, "human_answers": 0,
    })


class MemoryWrite(Record):
    type: Literal["person", "place", "mechanic", "objective", "strategy", "correction"]
    content: str = Field(min_length=8, max_length=1500)
    tags: list[str] = Field(default_factory=list, max_length=12)
    importance: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class Episode(Record):
    summary: str = Field(max_length=2000)
    location_if_known: str = "Unknown"
    goal: str
    result: Literal["success", "failure", "uncertain", "interrupted", "reflection"]
    lessons: list[str] = Field(default_factory=list)
