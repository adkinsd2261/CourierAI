# CourierAI

A Windows-first autonomous game-playing agent built as a fork of
[Gamini](https://github.com/yumozi/gamini). Gamini supplies video capture, window
management, Gemini inference transport and native keyboard/mouse input. CourierAI
adds persistent goals, memory, procedural skills, outcome checks and human help.

**MVP implementation; live Fallout acceptance is still pending.** See
[the acceptance evidence](docs/ACCEPTANCE.md) for what passed. The corrected Gemini
request now works; a live action test still requires Fallout to retain foreground focus.

## Windows setup

Use Python 3.11+ (tested with 3.12), Node.js 20.9+ and pnpm 11.19.0. No CUDA,
local LLM, xNVSE or model training is required. In PowerShell:

```powershell
git clone https://github.com/adkinsd2261/CourierAI.git
cd CourierAI
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock-windows.txt
Copy-Item .env.example .env
```

The Windows lock file records the tested runtime and test dependencies. For another
platform or a deliberate dependency refresh use `requirements-dev.txt` instead.
The `imageio-ffmpeg` wheel includes ffmpeg; the launcher prepares a local executable
if one is not on PATH. A separate system ffmpeg installation is also supported.

Edit `.env` locally. Put your Gemini key after the equals sign, then save:

```dotenv
GEMINI_API_KEY=your_actual_key_here
```

Do not commit the key. `.env`, the SQLite database, logs and debug videos are ignored.
You can also supply a key in dashboard Settings; that value is kept in process
memory and is **not** saved to SQLite. The first key saved in `.env` can be picked
up on Start/Resume without restarting; restart to rotate an existing file-based key.

Install the frontend once (install pnpm with `npm install -g pnpm@11.19.0` if needed):

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ..
.\start-courier.ps1
```

Double-clicking `start.bat` runs the same launcher. Open **http://localhost:3000**.
If PowerShell blocks local scripts, use
`powershell -NoProfile -ExecutionPolicy Bypass -File .\start-courier.ps1` for this
launch; no machine-wide policy change is needed. Keep the launcher terminal open.
After changing frontend code, run `start-courier.ps1 -Rebuild`.

If using the Codex bundled runtime on this machine, it already provides Node and
pnpm under the user's `.cache/codex-runtimes` directory; the launcher detects its
Node path when a global Node installation is absent.

## Start playing

1. Open Fallout: New Vegas on a fresh save in windowed or borderless mode.
2. Select its exact title in Capture Target. Full-desktop capture is not enabled
   for CourierAI. Confirm the **permanent root instruction** and **game control
   mapping** against your bindings. The initial mapping is a starting template.
3. Save configuration, then press **Start**. Click the game window within the
   short focus grace period if Windows blocks background activation. Keep the
   game in the foreground. Switching away pauses input.
4. Watch the dashboard's observation, goal, concise rationale, expected result,
   confidence and separate evaluation. No repeated objectives are required.
5. When **NEED_HELP** appears, read the goal, attempts and uncertainty. Answer in
   the dashboard. The answer becomes a persistent lesson and the agent resumes.
   If you previously pressed Stop or Emergency Stop, an answer does not override it.

**F12 is the global emergency stop.** The backend preserves Gamini's hotkey and
uses a small global key-state polling fallback if Windows refuses registration.
The dashboard Emergency Stop has the same stop-and-release behavior. Pause and
Stop also release input. Resume captures afresh; it never blindly replays a
partially executed action. Stop the agent before closing the launcher.
These controls stop the agent's inputs; Fallout's simulation can continue running.

The app runs one agent shared by all dashboard tabs. Losing the last dashboard
connection pauses input. Restarting restores intentions and knowledge but requires
explicit Start/Resume. The SQLite state describes the agent's knowledge, not a
Fallout save file; it cannot restore the game's world state.

## Performance and configuration

The default capture is **640 pixels wide, 2 FPS, one second**, with a two-second
interval between cycles. Clips are encoded with two CPU threads. No encoding runs
during cloud inference. Increase capture width if small game text is unreadable.
Actual loop time also includes network/model latency; capture FPS is not actions/sec.

Each ordinary cycle makes three cloud calls: visual observation, a decision using
retrieved context, and visual outcome evaluation. Reflection adds one text call
every six decisions. API usage is billed by your provider. The model ID is editable;
Gamini's `gemini-3-flash-preview` is retained as the initial value, and must be
available to your key. `GEMINI_MODEL` can set the initial model before configuration
has been saved. No claim is made that every Gemini model supports the same video,
thinking or structured-output options.

Settings include capture width/FPS/duration, loop interval, maximum action and
sequence durations, allowed keys, reflection frequency and escalation thresholds.
Saving settings pauses a running agent. Default escalation is three consecutive
decisions below 0.35 confidence, four failures without progress, or 180 active
seconds without progress. Confidence below 0.1 and a major irreversible choice
with multiple plausible interpretations can trigger immediate help. A model's
`needs_human` flag or an unfamiliar action alone does not trigger escalation.

## Memory and learning

`data/courier.sqlite3` stores memories, skills, episodes, human lessons and the
current agent state. SQLite WAL transactions checkpoint action intentions before
input and learned outcomes afterward. `COURIER_DATA_DIR` may select another local
data directory. Non-secret configuration persists with the session.

- FTS5 retrieves relevant memories, skills and human lessons without embeddings.
  Recent human answers are also included so newly answered questions are reused.
- Low-importance or weakly supported proposed memories are discarded. Exact
  normalized duplicates do not increase confidence merely by being restated.
- A skill must match an actual executed, successful action sequence. Reflection
  can propose a skill only by citing such an episode. Re-reading the same episode
  does not count as another success.
- Skill confidence is `(successes + 1) / (successes + failures + 3)`. Memory
  confirmations add 0.05; contradictions subtract 0.15, bounded to 0.05–0.95.
  Low-confidence counterevidence remains retrievable as a caution.
- Model evaluation is fallible visual evidence, not ground-truth telemetry.
  Memory and skill viewers show confidence and outcome counts for inspection.

Learning means persistent retrieval and procedural knowledge. There are no
model-weight changes or local ML training. `backend/courier/ports.py` keeps the
perception/action/model interfaces replaceable for future game telemetry.

## Debugging and verification

```powershell
.\.venv\Scripts\python.exe scripts\doctor.py
.\.venv\Scripts\python.exe scripts\check_model.py
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
pnpm lint
pnpm build
```

The doctor prints readiness booleans without printing your key or making model
calls. `check_model.py` makes exactly one cloud request, validates its structured
response, and sends no game inputs. Add `--video temp\acceptance-before.mp4` to test
the locally captured game clip when available. Structured, rotating logs are in `logs/courier.jsonl`; launcher output is
in `logs/backend.stderr.log` and `logs/frontend.stderr.log`. Logs include decision
rationales, actions, expected results, evaluations, help requests and redacted
provider diagnostics, never private model chain-of-thought.

Troubleshooting:

- **Missing game window:** run the launcher from your normal interactive Windows
  session; a sandbox desktop cannot see the real game's windows. Refresh the list.
- **Lost foreground focus:** Resume, then click Fallout. The agent will not inject
  desktop shortcuts to force focus. Run the game and backend at the same Windows
  privilege level; prefer running both without administrator elevation.
- **Empty/stale capture:** use windowed/borderless mode and confirm the window
  remains visible. CourierAI pauses instead of falling back to the full desktop.
- **API error:** inspect the redacted provider error, verify the key/model, and
  correct the settings. Repeated setup failures also enter NEED_HELP.
- **Occupied ports:** the launcher refuses to stop another program. Close the
  existing CourierAI instance or resolve the conflict yourself.

The [acceptance checklist](docs/ACCEPTANCE.md) is the remaining live gate. Scripted
tests do not prove that the agent can play Fallout successfully.

## Architecture and upstream

`backend/courier/` contains the autonomous engine, SQLite store, validated schemas,
retrieval, escalation policy and adapters. `backend/main.py` hosts the singleton
agent and dashboard protocol. The existing `backend/game_loop.py` remains for
upstream contract coverage, but the dashboard runs CourierAI's agent.

Upstream changes are narrow: configurable capture width and no-fallback option,
limited encoding threads, custom structured Gemini responses, and reliable native
key/button release. Window-manager logic is preserved. Model output can only
request validated game key presses, mouse movement/clicks or waits. It cannot run
shell commands, hold an input indefinitely, press F12 itself, or use the game console.

See [the milestone ledger](docs/IMPLEMENTATION.md) and
[the original Gamini README](README_UPSTREAM.md). Upstream authorship and Git
history are preserved; this fork does not assert a new license grant over upstream code.
