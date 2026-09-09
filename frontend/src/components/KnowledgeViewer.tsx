"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { MemoryRows, SkillRows } from "@/components/AgentPanels";
import { Memory, Skill } from "@/lib/courier";

export function KnowledgeViewer({ collection, onClose }: { collection: "memories" | "skills"; onClose: () => void }) {
  const [tab, setTab] = useState<string>(collection);
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/agent/${tab}?limit=20&offset=${offset}&q=${encodeURIComponent(query)}`, { signal });
      if (!response.ok) throw new Error("Could not load saved knowledge");
      const data = await response.json();
      if (!signal.aborted) { setItems(data.items); setTotal(data.total ?? data.items.length); setError(""); }
    } catch { if (!signal.aborted) setError("Could not load saved knowledge. Check the backend connection."); }
    finally { if (!signal.aborted) setLoading(false); }
  }, [tab, offset, query]);
  useEffect(() => { const controller = new AbortController(); const timer = setTimeout(() => { void load(controller.signal); }, 200); return () => { clearTimeout(timer); controller.abort(); }; }, [load]);
  useEffect(() => { const dialog = dialogRef.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  return <dialog ref={dialogRef} onCancel={onClose} className="fixed inset-0 z-50 m-auto w-full max-w-4xl max-h-[95vh] bg-transparent text-zinc-100 backdrop:bg-black/80 p-4 overflow-y-auto" aria-label="Saved knowledge">
    <div className="max-w-3xl mx-auto rounded-xl bg-zinc-950 border border-zinc-700 p-6 space-y-5">
      <div className="flex justify-between"><h2 className="text-xl font-semibold">Saved knowledge</h2><button onClick={onClose} autoFocus className="text-emerald-300">Close</button></div>
      <div className="flex gap-3 flex-wrap">{["memories", "skills", "human_lessons", "episodes"].map(name => <button key={name} onClick={() => { setTab(name); setItems([]); setLoading(true); setOffset(0); }} className={tab === name ? "text-emerald-300 underline" : "text-zinc-400"}>{name.replaceAll("_", " ")}</button>)}</div>
      {tab !== "episodes" && <label className="block text-sm">Search (up to 12 relevant results)<input value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }} className="block mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-900 p-2" /></label>}
      {error && <p role="alert" className="text-red-300">{error}</p>}
      {loading && <p role="status" className="text-zinc-400">Loading saved knowledge…</p>}
      {!loading && !items.length && !error && <p className="text-zinc-400">No saved records match this view yet.</p>}
      {tab === "memories" ? <MemoryRows items={items as unknown as Memory[]} /> : tab === "skills" ? <SkillRows items={items as unknown as Skill[]} /> : <ul className="space-y-4">{items.map(row => <li key={String(row.id)} className="border-b border-zinc-800 pb-3">
        <p>{String(row.question ?? row.summary)}</p><p className="text-emerald-300">{String(row.answer ?? row.result)}</p>
        <p className="text-xs text-zinc-500">{String(row.timestamp)} · #{String(row.id)}</p>
      </li>)}</ul>}
      {!query && <div className="flex gap-4 text-sm"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))} className="disabled:opacity-30">Previous</button><span>{offset + items.length} of {total}</span><button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)} className="disabled:opacity-30">Next</button></div>}
    </div>
  </dialog>;
}
