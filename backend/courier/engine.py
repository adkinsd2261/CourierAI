"""One persistent autonomous actor, independently testable without game input."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from backend.courier.models import Decision, Evaluation, Observation, Reflection, validate_actions
from backend.courier.ports import Model, PerceptionActions
from backend.courier.state import Episode
from backend.courier.storage import Store
from backend.courier.escalation import escalation_reason

logger = logging.getLogger("courier")


class Agent:
    def __init__(self, store: Store, io: PerceptionActions, model: Model, config, publish):
        self.store, self.io, self.model = store, io, model
        self.config, self.publish = config, publish
        self.state = store.load_state()
        self.task = None
        self.decision = None
        self.evaluation = None
        self.error = None
        self.phase = "restored" if self.state.iteration else "ready"

    def snapshot(self):
        return {"state": self.state.status, "iteration": self.state.iteration,
                "agent_state": self.state.model_dump(), "phase": self.phase,
                "decision": self.decision.model_dump() if self.decision else None,
                "evaluation": self.evaluation.model_dump() if self.evaluation else None,
                "error": self.error, "counts": self.store.counts(),
                "memories": self.store.recent("memories", 6), "skills": self.store.recent("skills", 6)}

    async def emit(self):
        self.store.save_state(self.state)
        await self.publish(self.snapshot())

    async def start(self):
        if self.task and not self.task.done():
            return
        if self.state.pending_help:
            self.state.status = "need_help"
            await self.emit()
            return
        config = self.config()
        if not config.gemini_api_key or not config.target_window:
            raise ValueError("Configure a Gemini API key and select the game window")
        self.io.arm()
        self.state.status = "running"
        self.error = None
        self.task = asyncio.create_task(self.run())
        await self.emit()

    def interrupt(self):
        self.io.interrupt()

    async def halt(self, status="paused"):
        self.interrupt()
        self.state.status = status
        task = self.task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.io.release()
        self.phase = status
        await self.emit()

    def context(self, config):
        return {"root_instruction": config.root_instruction, "game_controls": config.game_context,
                "state": self.state.model_dump(), "limits": {k: getattr(config, k) for k in
                ("allowed_keys", "max_action_seconds", "max_sequence_seconds", "max_actions", "action_delay")},
                "recent_episodes": self.store.recent("episodes", 8),
                "recent_human_lessons": self.store.recent("human_lessons", 4)}

    def retrieve(self, observation, config):
        return self.store.retrieve(" ".join([observation.summary, observation.location,
            *observation.salient_entities, self.state.current_goal]), config.retrieval_limit)

    async def before_action(self, decision, context, config):
        self.state.low_confidence_streak = (
            self.state.low_confidence_streak + 1 if decision.confidence < config.confidence_threshold else 0)
        reason = escalation_reason(self.state, decision, config)
        if reason:
            await self.request_help(reason, decision.human_question, decision)
            return False
        return True

    async def request_help(self, reason, question=None, decision=None):
        self.interrupt()
        await self.io.release()
        self.state.status = "need_help"
        self.phase = "need_help"
        self.state.pending_help = {
            "id": str(uuid.uuid4()), "question": question or f"How should I proceed toward: {self.state.current_goal}?",
            "goal": self.state.current_goal, "reason": reason,
            "tried": self.store.recent_trials(6),
            "uncertainty": decision.plausible_interpretations if decision else [reason],
            "observation": self.state.recent_observations[-1] if self.state.recent_observations else "Unavailable",
        }
        self.state.statistics["help_requests"] += 1
        logger.info("need_help", extra={"event_data": self.state.pending_help})
        await self.emit()

    async def answer_help(self, request_id: str, answer: str):
        answer = answer.strip()
        if not answer or len(answer) > 4000:
            raise ValueError("Answer must contain 1 to 4000 characters")
        request = self.state.pending_help
        if not request or request["id"] != request_id:
            raise ValueError("This help request was already answered or replaced")
        should_resume = self.state.status == "need_help"
        with self.store.atomic():
            self.store.add_human_lesson(request["question"], answer,
                {"goal": request["goal"], "observation": request["observation"], "reason": request["reason"]},
                ["human", self.state.current_location_description])
            self.state.pending_help = None
            self.state.objective_failures = 0
            self.state.low_confidence_streak = 0
            self.state.no_progress_seconds = 0
            self.state.system_errors = 0
            self.state.statistics["human_answers"] += 1
            self.store.save_state(self.state)
        if self.task and not self.task.done():
            await self.task
        if should_resume:
            await self.start()
        else:
            await self.emit()

    def learn(self, decision, evaluation, retrieved, episode_id):
        if evaluation.confidence >= 0.6:
            for memory in evaluation.memory_writes:
                self.store.add_memory(memory)
            available = {m["id"] for m in retrieved["memories"]}
            contradicted = set(evaluation.contradicted_memory_ids) & available
            confirmed = (set(evaluation.confirmed_memory_ids) & available) - contradicted
            for ids, outcome in ((confirmed, "success"), (contradicted, "failure")):
                for record_id in ids:
                    self.store.feedback("memories", record_id, episode_id, outcome)
            if decision.chosen_skill:
                self.store.feedback("skills", decision.chosen_skill, episode_id, evaluation.outcome)
            for proposal in [*decision.skill_updates, *evaluation.skill_updates]:
                self.store.acquire_skill(proposal, episode_id)

    async def reflect(self, context, config):
        trials = self.store.recent_trials(config.reflection_interval)
        episodes = self.store.recent("episodes", 12)
        reflection = await self.model.ask(Reflection, "reflect", {
            **context, "state": self.state.model_dump(), "recent_trials": trials, "recent_episodes": episodes,
            "questions": ["What happened recently?", "What did I learn?", "Is there a reusable procedure?",
                "Which belief was wrong?", "What matters about a person, place, mechanic or objective?",
                "Should my priorities change?"],
        }, config)
        valid_ids = {e["id"] for e in episodes}
        if not set(reflection.evidence_episode_ids) <= valid_ids:
            raise ValueError("Reflection cited unavailable episodes")
        with self.store.atomic():
            for memory in reflection.memory_writes:
                self.store.add_memory(memory)
            for proposal in reflection.skill_updates:
                if proposal.source_episode_id in {t["episode_id"] for t in trials}:
                    self.store.acquire_skill(proposal, proposal.source_episode_id)
            if reflection.goal_updates:
                self.state.secondary_goals = reflection.goal_updates.secondary_goals
                self.state.active_plan = reflection.goal_updates.active_plan
            self.store.add_episode(Episode(summary=reflection.summary, goal=self.state.current_goal,
                result="reflection", lessons=[m.content for m in reflection.memory_writes]))
            self.state.statistics["reflections"] += 1
            self.store.save_state(self.state)

    async def step(self):
        config = self.config()
        started = time.monotonic()
        self.phase = "observing"
        await self.emit()
        video = await self.io.capture(config)
        context = self.context(config)
        observation = await self.model.ask(Observation, "observe", context, config, video)
        if self.state.pending_action:
            self.store.add_episode(Episode(summary="Prior action interrupted; outcome unknown. Observed again without replay.",
                goal=self.state.current_goal, result="interrupted"))
            self.state.pending_action = None
        self.state.current_location_description = observation.location
        self.state.current_hypotheses = observation.hypotheses
        self.state.recent_observations = (self.state.recent_observations + [observation.summary])[-12:]
        retrieved = self.retrieve(observation, config)
        context = {**self.context(config), "observation": observation.model_dump(), "retrieved": retrieved}
        self.phase = "deciding"
        await self.emit()
        decision = await self.model.ask(Decision, "decide", context, config)
        self.decision = decision
        self.evaluation = None
        self.state.iteration += 1
        self.state.statistics["decisions"] += 1
        self.state.current_goal = decision.current_goal
        self.state.secondary_goals = decision.goal_updates.secondary_goals
        self.state.active_plan = decision.goal_updates.active_plan
        if not await self.before_action(decision, context, config):
            return
        actions = validate_actions(decision.actions, config)
        if not set(decision.retrieved_memory_ids) <= {m["id"] for m in retrieved["memories"]}:
            raise ValueError("Decision cited unavailable memories")
        if decision.chosen_skill is not None:
            skill = next((s for s in retrieved["skills"] if s["id"] == decision.chosen_skill), None)
            if (not skill or not decision.chosen_skill_preconditions_met
                    or skill["procedure"] != [a.model_dump() for a in actions]):
                raise ValueError("Chosen skill must match its retrieved procedure and visible preconditions")
        self.state.pending_action = decision.model_dump()
        self.phase = "acting"
        await self.emit()  # Durable intent before the external side effect.
        logger.info("decision", extra={"event_data": {"iteration": self.state.iteration, **decision.model_dump()}})
        await self.io.execute(actions, config)
        self.state.statistics["actions"] += len(actions)
        self.phase = "evaluating"
        await self.emit()
        after = await self.io.capture(config)
        evaluation = await self.model.ask(Evaluation, "evaluate", {
            **context, "executed_decision": decision.model_dump(),
            "before_observation": observation.model_dump(),
        }, config, after)
        self.evaluation = evaluation
        reliable = evaluation.confidence >= 0.6
        outcome = evaluation.outcome if reliable else "uncertain"
        progress = reliable and outcome == "success" and evaluation.meaningful_progress
        self.state.no_progress_seconds = 0 if progress else self.state.no_progress_seconds + time.monotonic() - started
        # A goal rename or an unverified claimed success cannot reset the failure budget.
        self.state.objective_failures = 0 if progress else self.state.objective_failures + (outcome == "failure")
        self.state.statistics[{"success": "successes", "failure": "failures", "uncertain": "uncertain"}[outcome]] += 1
        self.state.recent_observations = (self.state.recent_observations + [evaluation.observation])[-12:]
        self.state.pending_action = None
        self.state.system_errors = 0
        with self.store.atomic():
            episode_id = self.store.add_episode(Episode(summary=evaluation.evidence,
                location_if_known=observation.location, goal=decision.current_goal, result=outcome,
                lessons=[m.content for m in evaluation.memory_writes] if reliable else []))
            self.store.record_trial(episode_id, decision, evaluation)
            self.learn(decision, evaluation, retrieved, episode_id)
            self.store.save_state(self.state)
        logger.info("evaluation", extra={"event_data": {"iteration": self.state.iteration, **evaluation.model_dump()}})
        reason = escalation_reason(self.state, decision, config)
        if reason:
            await self.request_help(reason, decision.human_question, decision)
            return
        if self.state.iteration % config.reflection_interval == 0:
            self.phase = "reflecting"
            await self.emit()
            await self.reflect(context, config)
        self.phase = "waiting"
        await self.emit()

    async def run(self):
        try:
            while self.state.status == "running":
                try:
                    await self.step()
                    if self.state.status != "running":
                        break
                    interval = self.config().loop_interval
                    await asyncio.sleep(interval)
                    self.state.no_progress_seconds += interval
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self.io.release()
                    self.state.system_errors += 1
                    self.error = f"{type(exc).__name__}: action loop interrupted"
                    logger.error("iteration_error", extra={"event_data": {"type": type(exc).__name__}})
                    from backend.courier.adapters import WindowUnavailable
                    if isinstance(exc, WindowUnavailable):
                        self.interrupt()
                        self.error = str(exc)
                        self.state.status = "paused"
                        self.phase = "paused"
                    elif self.state.system_errors >= self.config().system_error_limit:
                        await self.request_help("Capture, model or action validation failed repeatedly. Check the game and API settings.",
                            "Please correct the game/API setup or explain how to proceed, then answer to retry.")
                    await self.emit()
                    if self.state.status == "running":
                        await asyncio.sleep(min(2 ** self.state.system_errors, 10))
        except asyncio.CancelledError:
            pass
        finally:
            await self.io.release()
            if self.state.status == "running":
                self.state.status = "paused"
            await self.emit()
