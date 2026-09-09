# CourierAI milestone ledger

Upstream: https://github.com/yumozi/gamini, commit
`93e10eb68e21cdaaea6063841c1892c340d9155a`.

## 1. Unchanged application baseline

Backend dependencies installed in an isolated Python 3.12 environment on Windows.
Four baseline contract tests pass: FastAPI startup/read routes, coordinate mapping,
ffmpeg arguments, and ordered input delegation. Original application source is
unchanged at this milestone. These tests do not send physical inputs or call Gemini.

FalloutNV was not running during baseline inspection. Live gameplay acceptance
requires a running game and a user-configured Gemini key; it is not established by
mock tests. No game footage or private credentials belong in Git.

The unchanged Next.js 16.1.6 frontend production build and TypeScript compilation
passed. The WindowsInputBackend instantiated successfully without sending input.

## Completed implementation milestones

2. SQLite persistence and restoration: seven tests passed at this checkpoint.
3. Autonomous visual decision/action/evaluation loop without skills: 22 tests passed.
4. Relevant memory retrieval using FTS5: 24 tests passed.
5. Evidence-backed skill acquisition, reflection and confidence updates: 26 tests passed.
6. Persistent human escalation and recovery: 32 tests passed.
7. Shared dashboard controller, viewers, Windows launch documentation and local integration
   verification. The expanded suite has 42 passing tests. Live gameplay acceptance remains
   pending as recorded in `ACCEPTANCE.md`.

Keep upstream capture, window management, input implementations, and Gemini
transport. Extend through adapters and optional parameters. No local model
training, shell actions, xNVSE, or telemetry implementation in the MVP.

## Necessary changes to upstream infrastructure

- Capture: optional width and no-desktop-fallback flag, plus two encoding threads.
  CourierAI uses short fixed captures around actions instead of background video
  encoding throughout cloud latency. Upstream's original pipeline remains available in code.
- Gemini: custom response models and text phases use the existing client/retry/video
  transport. Custom schemas use the documented JSON Schema field because a live request
  proved the legacy field incompatible with strict Pydantic output models.
- Windows input: release events bypass the pointer-corner failsafe briefly, because
  a stop condition must not prevent key-up/mouse-up. The adapter drains in-flight
  native events on cancellation and releases every held input.
- Window management: unchanged. A foreground guard and initial activation grace period
  wrap the existing helpers. No desktop shortcut is injected to force focus.
- F12: original registration retained with a key-state fallback, because actual Windows
  registration returned failure on the target machine. Physical F12 interruption during
  live gameplay still needs verification.
