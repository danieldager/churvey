# Chat UI Research Probe — Firefox build (active)

Captures AI chat responses at the **network layer** inside a real logged-in Firefox
session, with automated asking. Network capture (`webRequest.filterResponseData`,
which Chrome MV3 lacks) means we record the exact response stream the web app
receives — no DOM-scraping, no "did it finish?" guessing, no selector drift on the
*response* side.

## Architecture
- **Persistent background page = the conductor** (`src/background/`). Single source
  of truth: owns the run config + per-item state. Stable (no MV3 service-worker
  death). Files: `runner.js` (the run loop), `capture.js` (network capture +
  per-provider parsers), `background.js` (message routing + interaction recorder).
- **Content driver = "hands" only** (`src/content/`). `driver.js` handles
  `NEW_CHAT` / `SUBMIT` / `PING` / `CAPTURE_DOM` / `PURGE`; `drivers.js` holds the
  per-provider input logic + selectors; `injector.js` types into React editors.
- **Capture is at the network layer**, paired to the asked question by `tabId`.
- **Shared** (`src/shared/`): `providers.js` (hosts + completion-endpoint hints),
  `run-plan.js` (question×persona×rep expansion), `prompt-template.js`,
  `record.js`, `summary.js`, `storage.js`, `messages.js`, `cadence.js`,
  `namespace.js` (holds the **BUILD** stamp).

### How a run works
The conductor processes **one provider at a time, keeping its tab focused until the
full response is captured**, then moves to the next (balanced rotation). This is
deliberately serial: ChatGPT and Gemini **abort their own streaming request when
their tab is backgrounded**, which truncates answers — holding focus guarantees
complete captures. Each item: focus tab → `NEW_CHAT` (fresh/private chat, may
navigate) → wait until ready → `SUBMIT` (type+send) → the streamed response is
captured & parsed → record. Inflight timeout, capacity-retry, and connection-retry
keep it from getting stuck.

**Two things about the timing of that capture** (both found 2026-09-15, when Gemini
answered in seconds yet every item timed out at 90 s):

- The runner arms `inflight` **before** it sends SUBMIT, not after. The content script
  does not reply until its driver's `submit()` resolves, and Gemini's holds focus for
  4.5 s on purpose — a fast answer's whole stream can open, deliver and close inside
  that window, and a completion capture with nothing inflight is thrown away.
- Gemini can hold its `StreamGenerate` connection open **long after** the answer is
  finished and on screen (measured: 120.4 s for a 4 s answer), and capture normally only
  yields a body at `filter.onstop`. So for Gemini only, the background polls the tab
  (`ANSWER_STATE` → the driver's `answerState()`) and calls `Probe.capture.flush()` once
  the page has stopped generating, the answer text has held still for ~3.6 s, and the
  stream itself has sent nothing for 2 s. The network stream is still the source of the
  text; the DOM only says *when*. Other providers close promptly and are untouched.

The run export (`<runId>.run.json`) carries the extension's 300-line **log ring** under
`log` — that is where all of the above is visible after the fact.

## Per-provider specifics
| Provider | Private mode | Answer endpoint / format |
|---|---|---|
| ChatGPT | `?temporary-chat=true` (URL) | `backend-api/f/conversation` — SSE deltas |
| Gemini | "Temporary chat" button (single plain click) | `StreamGenerate` — batchexecute arrays (longest `rc_` snapshot) |
| Grok | new chat → ⌘⇧J / private button | `rest/app-chat/conversations/new` — NDJSON (`modelResponse.message`) |
| Claude | `/new?incognito=` (URL) | `chat_conversations/…/completion` — SSE `text_delta` (skips thinking) |
| DeepSeek | none → **deletes all chats before every question** | `api/v0/chat/completion` — SSE patch-stream (initial fragment + content deltas) |

DeepSeek delete-all = authenticated `POST /api/v0/chat_session/delete_all`
(bearer token read from page storage + `x-app-version`), with the recorded
Settings→Data→"Delete all" UI as fallback.

## Load & run
1. `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** → `ff/manifest.json`.
2. Log into each provider; for clean data, also turn OFF account memory/personalization where applicable.
3. Popup → pick providers / questions / personas / reps / private → **Run**.
4. **Export JSONL + summary** (and `raw-completions.json` for debugging) → `Downloads/chat-probe/`.

### Reloading reliably (important)
Reloading the add-on does **not** update content scripts in already-open tabs.
1. `about:debugging` → **Reload**.
2. **Close provider tabs** (so the run opens fresh ones with new code).
3. Popup header shows **`bg <build> · tab <build>`** — if a tab build differs it
   shows **⚠ reload tab**. Use this to confirm the live build.
4. If a change still won't apply: **Remove + Load Temporary Add-on** again.

## Tools for maintenance
- **Capture DOM** (popup): dumps the active tab's buttons/dialogs/top-right region
  → for pinning selectors when a provider's UI changes.
- **⏺ Record interaction** (popup): records clicks + DOM changes + **network
  requests (with bodies and headers)** while you perform a flow manually → exports
  `recording-*.json`. This is how we reverse-engineered DeepSeek's delete API. ⚠️
  recordings contain auth tokens — keep them out of git.

## Follow-up questions (same chat)
A question with `"followup_of": "<id>"` is asked in the **same chat** as that
question, right after it (same persona and rep), with no persona preamble. The
parent must come earlier in the list. The runner only asks the follow-up once the
parent is recorded and the tab is still on the parent's chat; if that chat was
lost (tab closed, run resumed) it drops the parent's record and re-asks both.
Records carry `followupOf`.

## Data format (JSONL, one object per line)
`runId, provider, questionId, questionText, promptSent, personaId, repIndex,
itemKey, followupOf, modelLabel, responseText, status (ok|error), errorMessage, timestampStart/End,
latencyMs, private, captureUrl`. The summary reports per-provider capture rate,
latency stats, models, and blocked flags.

## Known limitations
See [`../FUTURE_WORK.md`](../FUTURE_WORK.md). Headlines: serial (no cross-provider
parallelism yet), Grok free-tier limits, DeepSeek token key may change between
deploys, model labels only captured for some providers.
