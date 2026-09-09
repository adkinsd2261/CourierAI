"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GameWebSocket } from "@/lib/websocket";
import { WindowSelector } from "@/components/WindowSelector";
import { SettingsPanel } from "@/components/SettingsPanel";
import { AgentPanels } from "@/components/AgentPanels";
import { KnowledgeViewer } from "@/components/KnowledgeViewer";
import { AgentStatus, Config } from "@/lib/courier";

type WindowInfo = { title: string; geometry: { x: number; y: number; w: number; h: number } | null };
const field = "w-full rounded-lg bg-zinc-800/60 border border-zinc-700 p-3 text-sm text-zinc-200";
const panel = "rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4";
const button = "rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed";

export default function Home() {
  const wsRef = useRef<GameWebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [windows, setWindows] = useState<WindowInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [viewer, setViewer] = useState<"memories" | "skills" | null>(null);
  const [saving, setSaving] = useState(false);
  const fetchWindows = useCallback(async () => {
    try { const res = await fetch("/api/windows"); if (res.ok) setWindows((await res.json()).windows); }
    catch { setError("Cannot refresh game windows. Check the backend connection."); }
  }, []);
  const fetchConfig = useCallback(async () => {
    try { const res = await fetch("/api/config"); if (res.ok) setConfig(await res.json()); }
    catch { setError("Cannot load configuration. Check the backend connection."); }
  }, []);
  useEffect(() => {
    const ws = new GameWebSocket(); wsRef.current = ws;
    ws.on("connected", () => { setConnected(true); void fetchConfig(); void fetchWindows(); });
    ws.on("disconnected", () => setConnected(false));
    ws.on("agent_status", data => setStatus(data as AgentStatus));
    ws.on("error", data => { setError(String(data)); setNotice(""); });
    ws.on("ack", data => { setNotice(`Accepted: ${String(data).replaceAll("_", " ")}`); setError(null); });
    ws.connect();
    return () => ws.disconnect();
  }, [fetchConfig, fetchWindows]);
  const update = useCallback((updates: Record<string, unknown>) => {
    setConfig(previous => previous ? { ...previous, ...updates } : previous);
    setNotice("Unsaved configuration changes");
  }, []);
  const command = (name: string, data?: unknown) => { setError(null); wsRef.current?.send(name, data); };
  const save = async (start = false) => {
    if (!config) return;
    setSaving(true); setError(null);
    try {
      const payload: Partial<Config> = { ...config };
      if (!payload.gemini_api_key || payload.gemini_api_key.includes("...") || payload.gemini_api_key === "***") delete payload.gemini_api_key;
      const res = await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error("Check the configuration limits and control key names.");
      setNotice("Configuration saved. Root instruction and controls persist across restarts.");
      if (start) command("start");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save configuration"); }
    finally { setSaving(false); }
  };
  const running = status?.state === "running";
  const resumable = ["paused", "stopped", "emergency_stopped", "error"].includes(status?.state ?? "");
  const closeViewer = useCallback(() => setViewer(null), []);
  return <div className="min-h-screen">
    <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-6 py-8">
      <header className="mb-6 border-b border-zinc-800 pb-6 flex justify-between gap-5 flex-wrap">
        <div><h1 className="text-3xl font-bold text-emerald-300">CourierAI</h1><p className="mt-1 text-sm text-zinc-400">Autonomous Fallout: New Vegas companion · Built on Gamini</p></div>
        <div className="text-sm"><p className={connected ? "text-emerald-400" : "text-amber-300"}>{connected ? "Backend connected" : "Backend disconnected"}</p><p className="text-xs text-zinc-400 mt-2">F12 emergency stop · Local control</p></div>
      </header>
      {(error || status?.error) && <p role="alert" className="mb-4 rounded-lg border border-red-800 bg-red-950/40 p-4 text-red-200">{error || status?.error}</p>}
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
        <aside className="space-y-4">
          <section className={panel}>
            <div className="flex justify-between text-sm"><h2 className="font-semibold">Control</h2><span className="text-emerald-300 uppercase">{status?.state.replaceAll("_", " ") ?? "Offline"}</span></div>
            <div className="grid grid-cols-2 gap-2">
              <button className={button + " text-emerald-300"} disabled={!connected || !config || running || saving || !!status?.agent_state.pending_help} onClick={() => void save(true)}>Start</button>
              <button className={button} disabled={!connected || !running} onClick={() => command("pause")}>Pause</button>
              <button className={button} disabled={!connected || !resumable || !!status?.agent_state.pending_help} onClick={() => command("resume")}>Resume</button>
              <button className={button} disabled={!connected} onClick={() => command("stop")}>Stop</button>
            </div>
            <button className="w-full rounded-lg bg-red-700 hover:bg-red-600 py-3 text-white font-semibold disabled:opacity-40" disabled={!connected} onClick={() => command("emergency_stop")}>Emergency Stop</button>
            <p className="text-xs text-zinc-400">Pause and Stop release input. Resume observes again before acting. Changing settings pauses an active run.</p>
            <div className="grid grid-cols-2 gap-2"><button className={button} onClick={() => setViewer("memories")}>Memory Viewer</button><button className={button} onClick={() => setViewer("skills")}>Skills Viewer</button></div>
            {notice && <p role="status" className="text-xs text-zinc-400">{notice}</p>}
          </section>
          {config && <>
            <WindowSelector windows={windows} selected={config.target_window} onSelect={title => update({ target_window: title })} onRefresh={fetchWindows} />
            <section className={panel}>
              <label className="block text-sm font-semibold" htmlFor="root-instruction">Permanent root instruction</label>
              <textarea id="root-instruction" className={field} rows={6} value={config.root_instruction} maxLength={6000} onChange={e => update({ root_instruction: e.target.value })} />
              <label className="block text-sm font-semibold" htmlFor="game-controls">Game control mapping</label>
              <textarea id="game-controls" className={field} rows={6} value={config.game_context} maxLength={6000} onChange={e => update({ game_context: e.target.value })} />
              <p className="text-xs text-zinc-400">Confirm these bindings against your game. The agent chooses its own immediate goals.</p>
              <button disabled={!connected || saving} className={button + " w-full text-emerald-300"} onClick={() => void save()}>{saving ? "Saving…" : "Save configuration"}</button>
            </section>
            <SettingsPanel apiKey={config.gemini_api_key} model={config.model} captureDuration={config.capture_duration} captureFps={config.capture_fps} temperature={config.temperature} mediaResolution={config.media_resolution} thinkingLevel={config.thinking_level} onUpdate={update} />
            <section className={panel}>
              <h2 className="font-semibold text-sm">Performance & autonomy</h2>
              {([
                ["capture_width", "Capture width (pixels)", 320, 1920, 2],
                ["loop_interval", "Interval between cycles (seconds)", 0.2, 60, 0.2],
                ["confidence_threshold", "Low confidence threshold", 0.05, 0.9, 0.05],
                ["low_confidence_limit", "Low confidence decisions before help", 1, 20, 1],
                ["failure_limit", "Failed attempts before help", 1, 30, 1],
                ["no_progress_timeout", "Active seconds without progress", 10, 3600, 10],
                ["max_action_seconds", "Maximum action duration", 0.05, 2, 0.05],
                ["max_actions", "Maximum actions per sequence", 1, 8, 1],
                ["max_sequence_seconds", "Maximum sequence duration", 0.1, 8, 0.1],
                ["reflection_interval", "Reflect every N decisions", 2, 50, 1],
              ] as const).map(([name, title, min, max, step]) => <label key={name} className="block text-xs text-zinc-400">{title}<input className={field + " mt-1"} type="number" value={config[name]} min={min} max={max} step={step} onChange={e => update({ [name]: Number(e.target.value) })} /></label>)}
              <label className="block text-xs text-zinc-400">Allowed keyboard keys (comma separated)<input className={field + " mt-1"} value={config.allowed_keys.join(", ")} onChange={e => update({ allowed_keys: e.target.value.split(",").map(s => s.trim()) })} /></label>
              <button disabled={!connected || saving} className={button + " w-full text-emerald-300"} onClick={() => void save()}>Save configuration</button>
            </section>
          </>}
        </aside>
        <main><AgentPanels status={status} connected={connected} onAnswer={(id, answer) => command("answer_help", { request_id: id, answer })} /></main>
      </div>
    </div>
    {viewer && <KnowledgeViewer key={viewer} collection={viewer} onClose={closeViewer} />}
  </div>;
}
