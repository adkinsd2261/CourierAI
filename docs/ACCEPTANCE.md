# Acceptance evidence and remaining live gate

## Verified locally

- Original upstream backend contracts and frontend production build passed before agent changes.
- Tests exercise disk persistence, restoration without action replay, FTS recall, distinct
  skill evidence, negative confidence updates, escalation boundaries, saved human answers,
  cancellation, emergency-stop priority, local API isolation, and JSON Schema transport.
- Scripted integration exercises successful skill acquisition, subsequent failures, reflection,
  NEED_HELP, a saved answer, and retrieval after restart. It sends no physical game inputs.
- Real Windows dashboard loaded, displayed the controls/state panels, and opened memory/skill
  viewers. Browser error collection was empty at that checkpoint.
- A real selected Fallout: New Vegas window was captured at 640 pixels / 2 FPS. The captured
  pause menu was visually inspected. No desktop fallback was used.

## Live test status (2026-09-09)

The user confirmed a fresh save and configured the Gemini key locally. The first run paused
before input because Windows denied foreground activation to the background backend. The
adapter now waits for activation and gives the user time to click the game after Start/Resume.
Changing foreground during play still pauses actions.

Once Fallout had focus, Gemini rejected the first observation request with HTTP 400 because
the legacy `response_schema` transport emitted an unsupported `additional_properties` field.
CourierAI custom models now use `response_json_schema` with local Pydantic validation. The
unchanged Gamini response continues using its original transport. Regression tests pass.
Google documents this JSON Schema path in its
[structured-output guide](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

Automatic approval review blocked the corrected live request because the review service hit
its usage limit. Thus **no autonomous game action, live successful skill acquisition, or live
recovery has yet been verified**. The test instance reached NEED_HELP before input;
its backend and frontend were then stopped.
The corrected backend requires a restart before another live test. Do not report acceptance
as passed from the scripted fixtures.

## Resume the live acceptance test

1. Stop the old backend/frontend. Run `start-courier.ps1 -Rebuild` from a normal Windows session.
2. Select the fresh-save game window. Confirm only the permanent root instruction and control
   mapping. Do not provide a series of immediate objectives.
3. If a persisted setup help request remains, explain that setup has been corrected and retry
   through the dashboard. Otherwise press Start, then click the game during its focus grace period.
4. Verify an observation, a chosen goal, a bounded action, and a separate visual outcome check.
5. Inspect memory/skill viewers after meaningful successes. Verify procedures match executed
   actions and that confidence changes after later failures. Never manufacture success records.
6. Verify autonomous alternate attempts before help. When naturally stuck, answer the question
   in the dashboard; confirm the lesson is stored and reused where relevant.
7. Press F12 during a held movement; verify release and emergency_stopped. Resume explicitly.
8. Pause, restart the application, and confirm goals, skills and lessons restore, with no
   automatic input or replay of a pending action.
9. Record evidence in this document, keeping raw footage, API keys and session databases out of Git.

Passing this gate demonstrates the MVP interaction loop, not completion of Fallout: New Vegas.
