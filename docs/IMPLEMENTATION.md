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

## Planned sequence

2. SQLite persistence and restoration.
3. Autonomous visual decision/action/evaluation loop without skills.
4. Relevant memory retrieval.
5. Evidence-backed skill acquisition and confidence updates.
6. Persistent human escalation and recovery.
7. Dashboard, Windows launch documentation, integration verification.

Keep upstream capture, window management, input implementations, and Gemini
transport. Extend through adapters and optional parameters. No local model
training, shell actions, xNVSE, or telemetry implementation in the MVP.
