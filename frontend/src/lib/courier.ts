export type Action = { action: string; key?: string; button?: string; duration: number; bbox?: number[]; dx?: number; dy?: number };
export type Memory = { id: number; type: string; content: string; confidence: number; importance: number; tags: string[]; confirmation_count: number; failure_count: number };
export type Skill = { id: number; name: string; description: string; procedure: Action[]; preconditions: string[]; success_signals: string[]; failure_signals: string[]; confidence: number; success_count: number; failure_count: number };
export type Trial = { episode_id: number; decision: { current_goal: string; actions: Action[]; expected_result: string }; evaluation: { outcome: string; evidence: string } };
export type HelpRequest = { id: string; question: string; goal: string; reason: string; tried: Trial[]; uncertainty: string[]; observation: string };
export type AgentStatus = {
  state: string; iteration: number; phase: string; error: string | null;
  agent_state: { current_goal: string; secondary_goals: string[]; current_hypotheses: string[]; current_location_description: string;
    recent_observations: string[]; active_plan: string[]; pending_help: HelpRequest | null;
    statistics: Record<string, number>; no_progress_seconds: number; objective_failures: number; low_confidence_streak: number };
  decision: { observation: string; current_goal: string; reasoning_summary: string; confidence: number; actions: Action[]; expected_result: string; chosen_skill: number | null } | null;
  evaluation: { observation: string; outcome: string; evidence: string; meaningful_progress: boolean } | null;
  counts: Record<string, number>; memories: Memory[]; skills: Skill[];
};
export type Config = {
  gemini_api_key: string; model: string; capture_duration: number; capture_fps: number; capture_width: number; loop_interval: number;
  game_context: string; target_window: string | null; temperature: number; media_resolution: string; thinking_level: string;
  root_instruction: string; confidence_threshold: number; low_confidence_limit: number; failure_limit: number; no_progress_timeout: number;
  max_action_seconds: number; max_actions: number; max_sequence_seconds: number; allowed_keys: string[]; reflection_interval: number;
};
export const actionText = (actions: Action[]) => actions.map(a => `${a.action}${a.key ? ` ${a.key}` : a.button ? ` ${a.button}` : ""}${a.dx !== undefined || a.dy !== undefined ? ` (${a.dx ?? 0}, ${a.dy ?? 0})` : ""} · ${a.duration}s`).join(" → ");
