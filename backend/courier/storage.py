"""Small, transactional SQLite store. No embeddings, local ML, or external sync."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from backend.courier.state import AgentState, Episode, MemoryWrite


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
 id INTEGER PRIMARY KEY, type TEXT NOT NULL, content TEXT NOT NULL,
 tags TEXT NOT NULL, importance REAL NOT NULL CHECK(importance BETWEEN 0 AND 1),
 confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1), created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, last_used_at TEXT, confirmation_count INTEGER NOT NULL DEFAULT 0,
 failure_count INTEGER NOT NULL DEFAULT 0, fingerprint TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS skills (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 procedure TEXT NOT NULL, preconditions TEXT NOT NULL, success_signals TEXT NOT NULL,
 failure_signals TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 success_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0,
 last_used_at TEXT, fingerprint TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS episodes (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, summary TEXT NOT NULL,
 location_if_known TEXT, goal TEXT NOT NULL, result TEXT NOT NULL, lessons TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_lessons (
 id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL,
 context TEXT NOT NULL, tags TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_state (
 id INTEGER PRIMARY KEY CHECK(id=1), current_goal TEXT NOT NULL, secondary_goals TEXT NOT NULL,
 current_hypotheses TEXT NOT NULL, current_location_description TEXT NOT NULL,
 recent_observations TEXT NOT NULL, active_plan TEXT NOT NULL, snapshot TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS episodes_timestamp ON episodes(timestamp);
CREATE VIRTUAL TABLE IF NOT EXISTS recall USING fts5(collection UNINDEXED, record_id UNINDEXED, text);
CREATE TRIGGER IF NOT EXISTS memories_recall_insert AFTER INSERT ON memories BEGIN
 INSERT INTO recall VALUES('memories',new.id,new.content || ' ' || new.tags);
END;
CREATE TRIGGER IF NOT EXISTS skills_recall_insert AFTER INSERT ON skills BEGIN
 INSERT INTO recall VALUES('skills',new.id,new.name || ' ' || new.description || ' ' || new.preconditions);
END;
CREATE TRIGGER IF NOT EXISTS lessons_recall_insert AFTER INSERT ON human_lessons BEGIN
 INSERT INTO recall VALUES('human_lessons',new.id,new.question || ' ' || new.answer || ' ' || new.context || ' ' || new.tags);
END;
INSERT INTO recall SELECT 'memories',id,content || ' ' || tags FROM memories
 WHERE NOT EXISTS (SELECT 1 FROM recall WHERE collection='memories' AND record_id=memories.id);
INSERT INTO recall SELECT 'skills',id,name || ' ' || description || ' ' || preconditions FROM skills
 WHERE NOT EXISTS (SELECT 1 FROM recall WHERE collection='skills' AND record_id=skills.id);
INSERT INTO recall SELECT 'human_lessons',id,question || ' ' || answer || ' ' || context || ' ' || tags FROM human_lessons
 WHERE NOT EXISTS (SELECT 1 FROM recall WHERE collection='human_lessons' AND record_id=human_lessons.id);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._depth = 0
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            self.db.close()
            raise RuntimeError("This database requires a newer CourierAI version")
        self.db.executescript("BEGIN;" + SCHEMA + "PRAGMA user_version=1; COMMIT;")

    @contextmanager
    def atomic(self):
        with self._lock:
            outer = self._depth == 0
            if outer:
                self.db.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
            except BaseException:
                if outer:
                    self.db.rollback()
                raise
            else:
                if outer:
                    self.db.commit()
            finally:
                self._depth -= 1

    def close(self):
        with self._lock:
            self.db.close()

    def save_state(self, state: AgentState):
        with self.atomic():
            self.db.execute("""INSERT OR REPLACE INTO agent_state VALUES(1,?,?,?,?,?,?,?,?)""", (
                state.current_goal, encode(state.secondary_goals), encode(state.current_hypotheses),
                state.current_location_description, encode(state.recent_observations[-12:]),
                encode(state.active_plan), state.model_dump_json(), now(),
            ))

    def load_state(self) -> AgentState:
        with self._lock:
            row = self.db.execute("SELECT snapshot FROM agent_state WHERE id=1").fetchone()
        state = AgentState.model_validate_json(row[0]) if row else AgentState()
        # Restoring intentions must never restore physical input or replay an uncertain action.
        if state.status == "running":
            state.status = "paused"
        return state

    def save_settings(self, settings: dict):
        safe = {k: v for k, v in settings.items() if k != "gemini_api_key"}
        with self.atomic():
            self.db.execute("INSERT OR REPLACE INTO settings VALUES(1,?)", (encode(safe),))

    def load_settings(self) -> dict:
        with self._lock:
            row = self.db.execute("SELECT value FROM settings WHERE id=1").fetchone()
        return json.loads(row[0]) if row else {}

    def add_memory(self, memory: MemoryWrite) -> int | None:
        if memory.importance < 0.5 or memory.confidence < 0.4:
            return None
        stamp = now()
        key = fingerprint(memory.type + ":" + memory.content.strip())
        with self.atomic():
            self.db.execute("""INSERT OR IGNORE INTO memories
                (type,content,tags,importance,confidence,created_at,updated_at,fingerprint)
                VALUES(?,?,?,?,?,?,?,?)""", (
                memory.type, memory.content.strip(), encode(memory.tags), memory.importance,
                min(memory.confidence, 0.8), stamp, stamp, key,
            ))
            # Repeated model assertions are not independent confirmations.
            return self.db.execute("SELECT id FROM memories WHERE fingerprint=?", (key,)).fetchone()[0]

    def add_episode(self, episode: Episode) -> int:
        with self.atomic():
            cursor = self.db.execute("""INSERT INTO episodes
                (timestamp,summary,location_if_known,goal,result,lessons) VALUES(?,?,?,?,?,?)""", (
                now(), episode.summary, episode.location_if_known, episode.goal, episode.result,
                encode(episode.lessons),
            ))
            return cursor.lastrowid

    def add_human_lesson(self, question: str, answer: str, context: dict, tags: list[str]) -> int:
        with self.atomic():
            cursor = self.db.execute("""INSERT INTO human_lessons
                (question,answer,context,tags,confidence,timestamp) VALUES(?,?,?,?,?,?)""", (
                question, answer, encode(context), encode(tags), 0.95, now(),
            ))
            return cursor.lastrowid

    def recent(self, table: str, limit: int = 20, offset: int = 0) -> list[dict]:
        if table not in {"memories", "skills", "episodes", "human_lessons"}:
            raise ValueError("Unknown collection")
        with self._lock:
            rows = self.db.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ? OFFSET ?",
                                   (max(1, min(limit, 100)), max(0, offset))).fetchall()
        return [self.decode_row(row) for row in rows]

    @staticmethod
    def decode_row(row) -> dict:
        data = dict(row)
        data.pop("fingerprint", None)
        for name in ("tags", "procedure", "preconditions", "success_signals", "failure_signals", "lessons", "context"):
            if name in data:
                data[name] = json.loads(data[name])
        return data

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {t: self.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("memories", "skills", "episodes", "human_lessons")}

    def retrieve(self, query: str, limit: int = 6) -> dict[str, list[dict]]:
        """FTS5 keyword retrieval: bounded candidates and no local model. Low-confidence
        contradictions remain retrievable as cautions rather than disappearing."""
        stop = {"the", "and", "with", "this", "that", "from", "into", "your", "have", "current", "unknown"}
        tokens = list(dict.fromkeys(t.lower() for t in re.findall(r"\w{3,}", query)
                                   if t.lower() not in stop))[:48]
        result = {"memories": [], "skills": [], "human_lessons": []}
        if not tokens:
            return result
        match = " OR ".join('"' + t + '"' for t in tokens)
        limit = max(1, min(limit, 12))
        with self.atomic():
            for collection in result:
                rows = self.db.execute("""SELECT record_id, bm25(recall) AS rank FROM recall
                    WHERE recall MATCH ? AND collection=? ORDER BY rank LIMIT ?""",
                    (match, collection, limit * 3)).fetchall()
                candidates = []
                for row in rows:
                    record = self.db.execute(f"SELECT * FROM {collection} WHERE id=?", (row["record_id"],)).fetchone()
                    if record:
                        item = self.decode_row(record)
                        # Relevance dominates; confidence and importance break similar matches.
                        score = -row["rank"] * (0.5 + item["confidence"]) * (0.5 + item.get("importance", 0.8))
                        candidates.append((score, item))
                chosen = [item for _, item in sorted(candidates, key=lambda x: x[0], reverse=True)[:limit]]
                result[collection] = chosen
                if collection in ("memories", "skills"):
                    for item in chosen:
                        self.db.execute(f"UPDATE {collection} SET last_used_at=? WHERE id=?", (now(), item["id"]))
        return result
