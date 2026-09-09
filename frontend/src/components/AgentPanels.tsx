"use client";
import { useState } from "react";
import { AgentStatus, HelpRequest, Memory, Skill, actionText } from "@/lib/courier";

const panel = "rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-3";
const label = "text-xs font-semibold uppercase tracking-wider text-zinc-400";

function HumanHelp({ request, connected, onAnswer }: { request: HelpRequest; connected: boolean; onAnswer: (id: string, answer: string) => void }) {
  const [answer, setAnswer] = useState("");
  return <section className="rounded-xl border-2 border-amber-400/70 bg-amber-950/30 p-5 space-y-3" aria-live="polite">
    <h2 className="text-amber-300 font-semibold">NEED HELP · Game actions paused</h2>
    <p className="text-lg text-zinc-100">{request.question}</p>
    <p><strong>Trying to:</strong> {request.goal}</p>
    <p className="text-amber-200">{request.reason}</p>
    <p><strong>What I see:</strong> {request.observation}</p>
    {request.uncertainty.length > 0 && <p><strong>Uncertain:</strong> {request.uncertainty.join(" / ")}</p>}
    <details><summary className="cursor-pointer text-zinc-300">What I tried ({request.tried.length})</summary>
      <ul className="mt-2 space-y-2 text-sm">{request.tried.map(t => <li key={t.episode_id}>
        {actionText(t.decision.actions)} — {t.evaluation.outcome}: {t.evaluation.evidence}
      </li>)}</ul>
    </details>
    <form onSubmit={e => { e.preventDefault(); if (answer.trim()) onAnswer(request.id, answer.trim()); }} className="space-y-3">
      <label className="block text-sm" htmlFor="human-answer">Your answer becomes a persistent lesson</label>
      <textarea id="human-answer" value={answer} onChange={e => setAnswer(e.target.value)} maxLength={4000} required
        className="w-full rounded-lg bg-zinc-950 border border-amber-500/50 p-3" rows={3} />
      <button disabled={!connected || !answer.trim()} className="rounded-lg px-4 py-2 bg-amber-300 text-zinc-950 font-medium disabled:opacity-40">Save lesson & resume</button>
    </form>
  </section>;
}

export function MemoryRows({ items }: { items: Memory[] }) {
  return <ul className="space-y-3">{items.map(m => <li key={m.id} className="border-b border-zinc-800 pb-3 last:border-0">
    <p>{m.content}</p><p className="mt-1 text-xs text-zinc-400">#{m.id} · {m.type} · {Math.round(m.confidence * 100)}% confidence · {m.confirmation_count} confirmations / {m.failure_count} failures</p>
    <p className="text-xs text-emerald-400/80">{m.tags.join(" · ")}</p>
  </li>)}</ul>;
}

export function SkillRows({ items }: { items: Skill[] }) {
  return <ul className="space-y-3">{items.map(s => <li key={s.id} className="border-b border-zinc-800 pb-3 last:border-0">
    <details><summary className="cursor-pointer font-medium">{s.name} <span className="text-xs text-emerald-400">{Math.round(s.confidence * 100)}%</span></summary>
      <p className="my-2">{s.description}</p><p className="text-sm"><strong>When:</strong> {s.preconditions.join("; ")}</p>
      <p className="font-mono text-xs my-2">{actionText(s.procedure)}</p>
      <p className="text-sm"><strong>Success:</strong> {s.success_signals.join("; ")}</p>
      <p className="text-sm"><strong>Failure:</strong> {s.failure_signals.join("; ")}</p>
    </details><p className="mt-1 text-xs text-zinc-400">#{s.id} · {s.success_count} successes / {s.failure_count} failures</p>
  </li>)}</ul>;
}

export function AgentPanels({ status, connected, onAnswer }: { status: AgentStatus | null; connected: boolean; onAnswer: (id: string, answer: string) => void }) {
  if (!status) return <section className={panel}><p className="text-zinc-400">Waiting for the CourierAI backend.</p></section>;
  const { agent_state: state, decision, evaluation } = status;
  return <div className="space-y-4">
    {state.pending_help && <HumanHelp key={state.pending_help.id} request={state.pending_help} connected={connected} onAnswer={onAnswer} />}
    <section className={panel}>
      <div className="flex justify-between gap-4"><h2 className={label}>Current goal</h2><span className="text-xs text-emerald-400 uppercase">{status.phase}</span></div>
      <p className="text-xl font-medium text-zinc-100">{state.current_goal}</p>
      <p className="text-xs text-zinc-400">Location: {state.current_location_description}</p>
      {state.secondary_goals.length > 0 && <p className="text-sm text-zinc-400">Longer term: {state.secondary_goals.join(" · ")}</p>}
    </section>
    <section className={panel}>
      <h2 className={label}>Current observation</h2><p>{state.recent_observations.at(-1) || "No game observations yet."}</p>
      {state.current_hypotheses.length > 0 && <p className="text-sm text-zinc-400">Hypotheses: {state.current_hypotheses.join(" · ")}</p>}
    </section>
    <section className={panel}>
      <div className="flex justify-between gap-4"><h2 className={label}>{status.phase === "acting" ? "Current action" : "Latest decision"}</h2>
        <span className="text-emerald-300 font-mono">{decision ? `${Math.round(decision.confidence * 100)}% confidence` : "—"}</span></div>
      <p className="font-mono text-sm">{decision ? actionText(decision.actions) || "Observe without input" : "Awaiting first decision"}</p>
      <p className="text-sm text-zinc-300">{decision?.reasoning_summary}</p>
      {decision && <p className="text-sm text-zinc-400">Expected: {decision.expected_result}</p>}
      {evaluation && <p className="text-sm"><strong className={evaluation.outcome === "success" ? "text-emerald-400" : "text-amber-300"}>{evaluation.outcome}: </strong>{evaluation.evidence}</p>}
    </section>
    <section className={panel}><h2 className={label}>Current plan</h2>
      {state.active_plan.length ? <ol className="list-decimal pl-5 space-y-1">{state.active_plan.map((step, i) => <li key={i}>{step}</li>)}</ol> : <p className="text-zinc-500">The agent will form a plan after observing the game.</p>}
    </section>
    <div className="grid md:grid-cols-2 gap-4">
      <section className={panel}><h2 className={label}>Recent memories · {status.counts.memories}</h2>{status.memories.length ? <MemoryRows items={status.memories} /> : <p className="text-sm text-zinc-500">Meaningful discoveries will appear here.</p>}</section>
      <section className={panel}><h2 className={label}>Learned skills · {status.counts.skills}</h2>{status.skills.length ? <SkillRows items={status.skills} /> : <p className="text-sm text-zinc-500">Verified procedures will appear here.</p>}</section>
    </div>
    <section className={panel}><h2 className={label}>Session statistics · persisted totals</h2>
      <div className="grid grid-cols-3 gap-3">{Object.entries(state.statistics).map(([name, count]) => <div key={name} className="rounded-lg bg-zinc-800/50 p-3"><p className="text-xl font-mono">{count}</p><p className="text-xs text-zinc-400">{name.replaceAll("_", " ")}</p></div>)}</div>
      <p className="text-xs text-zinc-400">{Math.round(state.no_progress_seconds)}s active without progress · {state.objective_failures} unsuccessful attempts · {state.low_confidence_streak} low-confidence decisions</p>
    </section>
  </div>;
}
