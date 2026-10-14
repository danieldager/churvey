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

## Chat isolation (2026-10-14)
Every question must be asked in a brand-new temporary chat; each record proves it in `isolation`
{new_chat, temporary, chat_id, evidence} and an item that cannot be proven is an error `[not_isolated]`, never a silent
answer. Mechanisms, evidence, account memory and chat deletion: [`../docs/isolation.md`](../docs/isolation.md).

## Per-provider specifics
| Provider | Private mode | Answer endpoint / format |
|---|---|---|
| ChatGPT | fresh load of `/?temporary-chat=true` for every question | `backend-api/f/conversation` — SSE deltas |
| Gemini | new chat, then the "Temporary chat" button only if it is not already on (`temp-chat-on`) | `StreamGenerate` — batchexecute arrays (longest `rc_` snapshot) |
| Grok | Chat (`a[data-testid=new-chat]`) → `a[aria-label="Switch to Private Chat"]` (never by text: the link reads "Private" in both states) | since 2026-10 a websocket gateway, no HTTP stream: after submit the runner polls `conversations/<id>/response-node` (nothing in flight) then POSTs `load-responses`; the assistant message (`<grok:render>` cards) is fed to capture as a synthetic NDJSON `modelResponse` |
| Claude | `/new?incognito=` (URL) | since 2026-10 `/claudeai-rpc/...` (connect+proto), nothing teeable: after submit the runner polls `GET /api/organizations/<org>/chat_conversations/<id>?tree=True&rendering_mode=messages&render_all_tools=true` from the page (id = last segment of `/chat/<id>`, org from the page's own requests or `/api/organizations`). The assistant message only appears when the turn ends; it is taken when `stop_reason` is final, no block is open, it is identical on two polls and the page agrees (no Stop button, `data-is-streaming="false"`). Text blocks -> responseText (thinking never), text-block `citations` -> v5 citations (`claude_poll`), `web_search` results -> `fetchedUrls` |
| DeepSeek | none → **deletes all chats before every question** | `api/v0/chat/completion` — SSE patch-stream (initial fragment + content deltas) |

DeepSeek delete-all = authenticated `POST /api/v0/chat_session/delete_all`
(bearer token read from page storage + `x-app-version`), with the recorded
Settings→Data→"Delete all" UI as fallback.

## Load & run
1. `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** → `ff/manifest.json`.
2. Log into each provider; for clean data, also turn OFF account memory/personalization where applicable.
3. Popup → pick providers / questions / personas / reps / private → **Run**.
4. **Export JSONL + summary** (and `raw-completions.json` for debugging) → `Downloads/chat-probe/`.

### Zero-click load & run (daily pipeline)
`cn_bench/launch_browser.py` does steps 1 and 3 with no clicking: it serves the run
plan on a loopback port, launches Firefox on the `cn-harvest` profile, and installs
this directory as a temporary add-on over Firefox's remote debugging protocol (the
call `web-ext run` makes internally — `web-ext` itself needs node, which this
machine does not have). `src/background/autostart.js` then probes
`http://127.0.0.1:8731-8735/run-plan.json` on load; if a launcher answers it starts
the run immediately and POSTs the export payload back (`/progress` each tick,
`/done` when finished). **If nothing is listening it does nothing** — the
about:debugging + popup path above is unchanged. Details:
[`../cn_bench/DAILY_PIPELINE.md`](../cn_bench/DAILY_PIPELINE.md) § Firefox launch.

### Reloading reliably (important)
Reloading the add-on does **not** update content scripts in already-open tabs.
1. `about:debugging` → **Reload**.
2. **Close provider tabs** (so the run opens fresh ones with new code).
3. Popup header shows **`bg <build> · tab <build>`** — if a tab build differs it
   shows **⚠ reload tab**. Use this to confirm the live build.
4. If a change still won't apply: **Remove + Load Temporary Add-on** again.

## Remote control (ffctl)

`cn_bench/ffctl.py` drives the extension of a run that `cn_bench/launch_browser.py` is serving, with no
popup clicks. It talks to Firefox's debugger server (`--start-debugger-server`, port 8831 for plan port
8731; `--port` to change), finds the add-on's background page and evaluates JS in it. It never launches
Firefox and never installs or reloads the add-on.

```
uv run python cn_bench/ffctl.py status                 # per provider: ok/total, errors, paused, current item + fails
uv run python cn_bench/ffctl.py log -n 300 --grep claude   # extension log ring (lossy: concurrent writes drop lines)
uv run python cn_bench/ffctl.py pause mistral          # also: resume <pid> (resume clears backoff and fails)
uv run python cn_bench/ffctl.py reload claude          # reload every open tab on that provider's host
uv run python cn_bench/ffctl.py stop --yes             # ends the whole run (needs --yes)
uv run python cn_bench/ffctl.py eval --unsafe 'return await Probe.runner.overview()'
```

`status` and `log` are read-only. `eval` runs as an async function body (use `return`), needs `--unsafe`.
`reload` finds tabs by host (`Probe.providers`), because the runner keeps its tab ids private.
A provider that keeps failing "no response (timeout)" is retried by the runner (MAX_ATTEMPTS 3).

## Capture robustness (2026-10-13)
The goal: nobody has to touch the browser, and an answer that is on screen is never lost. Details, test table and
known gaps: [`../docs/capture_robustness.md`](../docs/capture_robustness.md). In short:
- **Failure statuses.** `page-state.js` reads the page for a message-limit / quota banner, a login wall and a captcha /
  Cloudflare challenge (two reads in a row). The provider is then **paused** with status `rate_limited` / `logged_out` /
  `challenge` and the banner text, the item gets an error record `[status] banner`, and nothing is retried on a timer
  (`ffctl resume <provider>` clears it). A blocked provider counts as settled, so the run still ends. An answer that was on
  screen but could not be captured is `[answered_not_captured]`. Shown in `ffctl status` and the launcher output.
- **DOM fallback** for every provider (`guardWatch` in `runner.js`): finished on screen (no Stop control, text present, the
  provider's done marker, text unchanged for 12 s) and nothing captured -> record it with `capture_method: "dom_fallback"`.
  The item timeout also restarts while the answer is visibly still growing.
- **No dependence on focus or visibility.** `src/content/visibility.js` (document_start, through `wrappedJSObject`, so page
  CSP is irrelevant) makes `document.hidden` false, `visibilityState` "visible", `hasFocus()` true, swallows
  `visibilitychange`, and makes `requestAnimationFrame` fire within 50 ms. The launcher's managed `user.js` block disables
  background timer throttling and tab unloading (prefs listed in the docs). `--headless` runs with no window at all.
- **Launcher.** Unbuffered one line per landed record (`HH:MM:SS provider item status capture_method latency`), `=== HH:MM:SS
  START/END` lines, `--preflight` (1 short question x each provider, ok / logged_out / rate_limited / challenge /
  capture_failed, exit non-zero unless all ok), `--providers a,b`.

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
Records carry `followupOf`. Example: `analysis/cn_feed_panel_2026-09-10.json`
(`CNFn-insist` follows `CNFn-assumed`).

## Pictures in the prompt (`attachments`, Claude only, 2026-09-15)
A question may carry `"attachments": ["https://pbs.twimg.com/media/….jpg"]`. The
**background** fetches each URL (it holds the host permission; the content script
does not) and passes it to the tab as a data URL on the SUBMIT message. The content
driver puts the picture in the composer **before** typing the text, trying three
ways in order and stopping at the first that makes a preview appear:

1. **the hidden `<input type="file">`** — build a `DataTransfer`, assign `input.files`,
   fire `change`;
2. **a synthetic paste** — a `ClipboardEvent` carrying the `File`;
3. **a synthetic drop** — `dragenter` / `dragover` / `drop` on the composer.

Only providers in the runner's `ATTACH_PROVIDERS` act on the field (today: `claude`);
for anyone else the runner logs a warning and sends the text alone. A failure to
attach is **never** fatal — the prompt still goes, and the record's `attached` field
says what happened, so the answer itself shows whether the picture arrived.

**Measured 2026-09-15, Firefox 155, incognito Claude chat:** path 1 works first time.
Fetch → attach → submit took 0.5 s; the answer came back in 4.0 s and described the
photo. Paths 2 and 3 have never been exercised.

## Data format (JSONL, one object per line)
`runId, provider, questionId, questionText, promptSent, personaId, repIndex,
itemKey, followupOf, modelLabel, responseText, status (ok|error), errorMessage, timestampStart/End,
latencyMs, private, captureUrl, capture_method, isolation` (schema v7). `capture_method` says how the answer was
obtained: `stream` (network body tee'd by capture.js), `poll` (the page read the finished turn back:
grok, claude) or `dom_fallback` (no stream or poll capture landed but the answer was finished on screen;
read off the DOM: plain `innerText`, citations = the external links inside the answer, `via: "dom"`).
It is `null` on error records. The summary reports per-provider capture rate,
latency stats, models, and blocked flags.

## Known limitations
See [`../FUTURE_WORK.md`](../FUTURE_WORK.md). Headlines: serial (no cross-provider
parallelism yet), Grok free-tier limits, DeepSeek token key may change between
deploys, model labels only captured for some providers.

## Displayed citations (record schema v5)
`record.citations` = what the chat UI shows as a citation, parsed from the raw completion
stream by `src/background/citations.js`: Gemini per-segment grounding, Claude inline citation
chips, ChatGPT `cite` markers resolved through `search_result_groups` plus its Sources list.
Each row: url, title, domain, site_name, cited_text (source snippet), anchor_text /
anchor_start / anchor_end (answer segment it supports, offsets into responseText), marker,
ref_id, via. `record.fetchedUrls` = every URL found in the stream (the retrieval pool, not the
cited subset). Raw completion bodies are not in the records: the autostart path posts them
once, on `/done`, and the launcher writes `<runId>.raw-completions.json` for offline re-parsing.
Parsers: Gemini grounding (`gemini_grounding`, sentence-linked) or, when the stream carries none, the
"Searched the web" panel (`gemini_search_panel`, answer-level); Grok `<grok:render card_id>` tags resolved
through `cardAttachmentsJson` (`grok_inline`); Le Chat inline links plus the rest of its Sources list
(`mistral_source`). URLs are normalised in one place per side: `canon` in `citations.js` (fragment incl.
`#:~:text=`, utm_* and other tracking params) and `dashboard/ingest/url_canon.py`. Old runs are re-parsed from
their raw streams with `dashboard/ingest/reparse_raw.py` (writes `responses.clean.v2.jsonl`).
Capture audit: run config `"auditSources": true` makes the runner also store `record.domSources` (the external
links the page itself shows as sources, after opening a Sources button) next to the captured citations.
Gotcha: Firefox keeps a temporary add-on's script list in the profile's `startupCache` and serves the stale one after
`manifest.json` changes (a new background script silently does not load). The launcher (`launch_browser.start_firefox`,
used by every churvey command) deletes it before each launch: `~/Library/Caches/Firefox/Profiles/<profile>/startupCache`
on macOS, `~/.cache/mozilla/firefox/<profile>/startupCache` on Linux, `<profile>/startupCache` for a profile outside
Firefox's root. Loading by hand through about:debugging: delete it yourself. The first start after a clear is slow
(Firefox rebuilds its caches): the add-on install then waits longer (180 s to connect, 90 s per reply instead of 60 / 30)
and retries once, and a Firefox that never answers ends with a one-line message, not a traceback.
