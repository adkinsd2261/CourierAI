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

Automatic approval review initially blocked the corrected live request due to its usage limit.
A subsequent single request **passed**: Gemini returned a locally validated observation of
the captured Fallout pause menu using the corrected JSON Schema transport.

A subsequent live cycle passed capture and observation, but Gemini rejected the larger
Decision schema with HTTP 400. A compact wire schema now keeps types, required fields,
enums and extra-field rejection while retaining all original bounds in local Pydantic
validation. A real Decision request passed after this change; the transport regression
suite also verifies an overlong action is still rejected.

The hidden one-action probe then received a decision exceeding its configured action count;
validation prevented execution. On retry with that error as feedback, Gemini chose one
bounded mouse move. The foreground guard interrupted the cycle before an outcome check.
The foreground window was identified as a Windows Terminal titled with Crowley's separate
Python executable. Its scheduled bridge starts a visible CMD launcher with a repeating
10-second check. CourierAI's ffmpeg subprocesses now explicitly use CREATE_NO_WINDOW.

**A complete live action/evaluation cycle, live skill acquisition, and live recovery remain
unverified.** The agent is saved paused and its test services are stopped. No further
autonomous test should be represented as passed until foreground interference is resolved
and a visual action outcome is recorded. Do not treat scripted fixtures as live acceptance.

## Foreground-interference correction (2026-09-10)

With user approval, Crowley's separate bridge task was switched to a windowless WScript
launcher. Its Python bus and console utilities were also configured to avoid child consoles.
The task was restarted and its local HTTP endpoint returned 200. On the subsequent check,
the task still used WScript, HTTP still returned 200, and no visible Crowley Python consoles
were present. Fallout was closed at that check, so focus retention during gameplay and a
complete action/evaluation cycle remain pending. Crowley changes are in its own repository
at commit `5474f74`; CourierAI changes are in `5ca7fbe`.

The dashboard production build subsequently passed and the app was launched on port 3100
because the user's portfolio owns port 3000. A real WebSocket-driven bounded test reached
capture, then repeatedly received Gemini HTTP 500 responses. Nested retries subsequently
hit the project's free-tier limit of five requests per minute (the error identified
`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, with a 15-second retry delay).
The test paused and received the input-release acknowledgement; no decision or evaluated
action was recorded. Memories, skills, episodes and human lessons were still empty.

CourierAI now spaces model attempts by 13 seconds and disables inner retries so failed
requests are also paced. Twelve targeted transport/baseline tests passed. After cooldown,
the previously working game clip still received HTTP 500. A Gemini 2.5 Flash probe returned
404 and directed the account to Gemini 3.6 Flash; that replacement also returned HTTP 500,
including a basic JSON-mode probe. The configured model was not changed by these probes.
Further API attempts were stopped. The live gameplay acceptance gate remains unpassed.

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
