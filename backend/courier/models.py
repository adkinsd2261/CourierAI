from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator

from backend.models import AppConfig
from backend.courier.state import MemoryWrite, Record

SAFE_KEYS = frozenset([*"abcdefghijklmnopqrstuvwxyz", *"0123456789",
    "space", "shift", "ctrl", "tab", "escape", "enter", "up", "down", "left", "right", "f5"])


class Action(Record):
    action: Literal["key_press", "mouse_move", "mouse_click", "wait"]
    key: str | None = None
    bbox: list[int] | None = Field(default=None, min_length=4, max_length=4)
    dx: int | None = Field(default=None, ge=-500, le=500)
    dy: int | None = Field(default=None, ge=-500, le=500)
    button: Literal["left", "right", "middle"] | None = None
    duration: float = Field(default=0.15, ge=0.01, le=2)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.action == "key_press":
            if self.key not in SAFE_KEYS:
                raise ValueError("Key is not in the game action allowlist")
        elif self.key is not None:
            raise ValueError("key is only valid for key_press")
        if self.button is not None and self.action != "mouse_click":
            raise ValueError("button is only valid for mouse_click")
        if self.bbox is not None:
            if self.action not in ("mouse_move", "mouse_click"):
                raise ValueError("bbox is only valid for a mouse action")
            y0, x0, y1, x1 = self.bbox
            if not (0 <= y0 <= y1 <= 999 and 0 <= x0 <= x1 <= 999):
                raise ValueError("bbox must be ordered and inside the game frame (0..999)")
        if self.dx is not None or self.dy is not None:
            if self.action != "mouse_move" or self.bbox is not None:
                raise ValueError("relative movement requires mouse_move without bbox")
        if self.action == "mouse_move" and self.bbox is None and self.dx is None and self.dy is None:
            raise ValueError("mouse_move needs a bbox or relative movement")
        return self


class CourierConfig(AppConfig):
    capture_duration: float = Field(default=1.0, ge=0.5, le=5)
    capture_fps: int = Field(default=2, ge=1, le=10)
    capture_width: int = Field(default=640, ge=320, le=1920)
    loop_interval: float = Field(default=2.0, ge=0.2, le=60)
    max_action_seconds: float = Field(default=1, ge=0.05, le=2)
    max_sequence_seconds: float = Field(default=3, ge=0.1, le=8)
    max_actions: int = Field(default=4, ge=1, le=8)
    allowed_keys: list[str] = Field(default_factory=lambda: sorted(SAFE_KEYS), max_length=64)
    root_instruction: str = Field(default=(
        "Play Fallout: New Vegas from the current save. Understand your situation, develop your own "
        "goals, explore, learn the controls, follow useful leads, and keep the character alive. "
        "Make small reversible experiments, learn from visible outcomes, and use human help only "
        "when stuck or facing major irreversible uncertainty."), min_length=10, max_length=6000)
    game_context: str = Field(default=(
        "Confirm against the user's game bindings: WASD move; mouse look; E interact; "
        "Tab Pip-Boy; Escape pause/back; Enter confirm; Space jump; Ctrl crouch; "
        "R reload; left mouse attack; right mouse aim; V VATS. Do not use the console."), max_length=6000)
    confidence_threshold: float = Field(default=0.35, ge=0.05, le=0.9)
    low_confidence_limit: int = Field(default=3, ge=1, le=20)
    failure_limit: int = Field(default=4, ge=1, le=30)
    no_progress_timeout: float = Field(default=180, ge=10, le=3600)
    system_error_limit: int = Field(default=3, ge=1, le=10)
    reflection_interval: int = Field(default=6, ge=2, le=50)
    retrieval_limit: int = Field(default=6, ge=1, le=12)

    @model_validator(mode="after")
    def keys_are_safe(self):
        if not self.allowed_keys or any(k not in SAFE_KEYS for k in self.allowed_keys):
            raise ValueError("allowed_keys must be a nonempty subset of the game allowlist")
        return self


class Observation(Record):
    summary: str = Field(min_length=1, max_length=1800)
    location: str = Field(default="Unknown", max_length=300)
    salient_entities: list[str] = Field(default_factory=list, max_length=12)
    hypotheses: list[str] = Field(default_factory=list, max_length=6)


class GoalUpdate(Record):
    secondary_goals: list[str] = Field(default_factory=list, max_length=8)
    active_plan: list[str] = Field(default_factory=list, max_length=8)
    reason: str = Field(default="", max_length=400)


class SkillProposal(Record):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=8, max_length=800)
    procedure: list[Action] = Field(min_length=1, max_length=8)
    preconditions: list[str] = Field(min_length=1, max_length=8)
    success_signals: list[str] = Field(min_length=1, max_length=8)
    failure_signals: list[str] = Field(min_length=1, max_length=8)
    source_episode_id: int | None = None


class Decision(Record):
    observation: str = Field(min_length=1, max_length=1800)
    current_goal: str = Field(min_length=1, max_length=600)
    reasoning_summary: str = Field(min_length=1, max_length=600)
    retrieved_memory_ids: list[int] = Field(default_factory=list, max_length=12)
    chosen_skill: int | None = None
    chosen_skill_preconditions_met: bool = False
    actions: list[Action] = Field(default_factory=list, max_length=8)
    expected_result: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0, le=1)
    memory_writes: list[MemoryWrite] = Field(default_factory=list, max_length=4)
    skill_updates: list[SkillProposal] = Field(default_factory=list, max_length=2)
    goal_updates: GoalUpdate = Field(default_factory=GoalUpdate)
    needs_human: bool = False
    human_question: str | None = Field(default=None, max_length=1200)
    irreversible_risk: bool = False
    plausible_interpretations: list[str] = Field(default_factory=list, max_length=5)


class Evaluation(Record):
    observation: str = Field(min_length=1, max_length=1800)
    outcome: Literal["success", "failure", "uncertain"]
    evidence: str = Field(min_length=1, max_length=1000)
    meaningful_progress: bool = False
    goal_completed: bool = False
    confidence: float = Field(ge=0, le=1)
    memory_writes: list[MemoryWrite] = Field(default_factory=list, max_length=4)
    confirmed_memory_ids: list[int] = Field(default_factory=list, max_length=12)
    contradicted_memory_ids: list[int] = Field(default_factory=list, max_length=12)
    skill_updates: list[SkillProposal] = Field(default_factory=list, max_length=2)


class Reflection(Record):
    summary: str = Field(min_length=1, max_length=1800)
    evidence_episode_ids: list[int] = Field(min_length=1, max_length=12)
    memory_writes: list[MemoryWrite] = Field(default_factory=list, max_length=4)
    skill_updates: list[SkillProposal] = Field(default_factory=list, max_length=3)
    goal_updates: GoalUpdate | None = None


def validate_actions(actions: list[Action], config: CourierConfig) -> list[Action]:
    # Revalidate saved/model-generated procedures immediately before execution.
    checked = [Action.model_validate(a.model_dump()) for a in actions]
    if len(checked) > config.max_actions:
        raise ValueError("Action sequence exceeds the configured action count")
    if sum(a.duration + config.action_delay for a in checked) > config.max_sequence_seconds:
        raise ValueError("Action sequence exceeds the configured time budget")
    for action in checked:
        if action.duration > config.max_action_seconds:
            raise ValueError("Action exceeds the configured duration")
        if action.key and action.key not in config.allowed_keys:
            raise ValueError("Key is not enabled in this control mapping")
    return checked
