"""Deterministic escalation policy. A model request by itself is insufficient."""
from backend.courier.models import CourierConfig, Decision
from backend.courier.state import AgentState


def escalation_reason(state: AgentState, decision: Decision, config: CourierConfig) -> str | None:
    if decision.irreversible_risk and len(decision.plausible_interpretations) >= 2:
        return "Major irreversible choice has multiple plausible interpretations"
    if decision.confidence < 0.1:
        return "Confidence is too low for a useful autonomous experiment"
    if state.low_confidence_streak >= config.low_confidence_limit:
        return "Confidence stayed below the configured threshold"
    if state.objective_failures >= config.failure_limit:
        return "Repeated attempts have failed without meaningful progress"
    if state.no_progress_seconds >= config.no_progress_timeout:
        return "No meaningful progress within the configured active time"
    return None
