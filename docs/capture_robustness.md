# Capture robustness

Goal (2026-10-13): nobody has to touch the browser, and an answer that is visible on screen is never lost.
Code: `ff/` (extension) and `churvey/survey/` (launcher, ffctl). Branch `capture-robust`.

## What changed

### 1. Claude capture (poll)

claude.ai no longer calls `chat_conversations/<id>/completion`. It sends the prompt through
`/claudeai-rpc/anthropic.bard.api.v1alpha.ConversationService/PerformAction` and streams the answer on `.../StreamTimeline`
(connect+proto), so the old completion hook matched nothing and every item timed out.

Claude is now a `POLL_PROVIDER` like Grok. After submit, `runner.js pollWatch` asks the content script every 2.5 s
(`POLL`); `drivers.js claude.poll` does `GET /api/organizations/<org>/chat_conversations/<id>?tree=True&rendering_mode=messages&render_all_tools=true`.

- `<id>` is the last segment of the page's `/chat/<id>`. `<org>` is read from the page's own requests
  (`performance.getEntriesByType("resource")`), else from `/api/organizations` (first org with the `chat` capability). Nothing is hardcoded.
- Measured: while the turn streams the endpoint returns the human message only; the assistant message appears whole when the turn ends.
- "Finished" = the leaf of the tree is an assistant message with a final `stop_reason` (not `tool_use` / `pause_turn`), no content
  block without `stop_timestamp`, a text block present, the same signature on **two consecutive polls**, and the page agrees
  (no Stop button, no `[data-is-streaming="true"]`).
- The turn's human message must match the prompt that was sent (first 60 normalised characters) or the poll is ignored.
- `responseText` = the `text` blocks (blank line between blocks); `thinking` and tool blocks never. Offsets of `citations[].start_index/end_index`
  are mapped into that string.
- Citations: text-block `citations` become v5 rows with `via: "claude_poll"`, anchored to the cited span. `web_search` `tool_result`
  results are the retrieval pool (stay in `fetchedUrls`); only when the answer has no inline citation are they emitted as
  answer-level `claude_search_result` rows (the same rule as Gemini's search panel).
- The page-read turn is handed to `capture.js` as a synthetic completion (`__probe_claude_synth__`), so pairing, citation parsing and
  records are the unchanged path. `capture_method` is `poll`.

### 2. DOM fallback (every provider)

`runner.js guardWatch` runs for every in-flight item every 2.5 s next to the stream/poll path. If nothing was captured but the answer is
**finished on screen** (no Stop control, text present, the provider's done marker visible, text unchanged for 12 s; 30 s when the marker selector
finds nothing), the last answer is read from the DOM (`content/page-state.js readAnswer`) and recorded with `capture_method: "dom_fallback"`:
plain `innerText`, citations = the external links inside the answer (`via: "dom"`). The wait is longer than any normal delivery, so the fallback only
fires when stream/poll failed. A claim flag stops a late capture and the fallback from both recording the same turn.

The item timeout also restarts while the answer is visibly still growing (capped at 4x the budget), so a long searched answer is no longer thrown
away at 90 s with half of it on screen.

`capture_method` is now on every record (record schema **v6**): `stream` | `poll` | `dom_fallback`, `null` on error records.

### 3. Failure statuses and auto-pause

`page-state.js pageStatus` reads the page (never clicks) for:

| status | detected by |
|---|---|
| `rate_limited` | a short visible element outside the conversation matching limit/quota phrases, EN + FR (`message limit`, `limite de messages`, `reached your ... limit`, `Upgrade ... to continue`, `try again later`, ...) |
| `logged_out` | login path (`/login`, `/auth`, `/welcome`...), redirect off the provider host, `[data-testid=login-button]`, a visible `Log in` / `Sign in` / `Se connecter` button |
| `challenge` | Cloudflare / captcha interstitial title ("Just a moment", "Un instant"), visible challenge iframe (turnstile, recaptcha, hcaptcha), short page mentioning a captcha |
| `answered_not_captured` | item timeout while an answer was on screen and the DOM fallback could not take it (item error `[answered_not_captured] ...`) |

Two consecutive reads (about 5 s) are needed while an item is in flight; before a submit one read is enough. On `rate_limited` / `logged_out` /
`challenge` the runner **pauses that provider** (`health = {status, text}`), writes an error record `[status] banner text` for the item, and
**retries nothing on a timer**. The provider counts as settled, so the run ends instead of waiting on it. `ffctl resume <provider>` clears it.
A provider-side 429 / "capacity" stream error takes the same path. Shown in `ffctl status`
(`[RATE_LIMITED: Messages limit reached ...]`), in the launcher output and in the `/done` payload.

### 4. No dependence on focus or visibility

- `ff/src/content/visibility.js` (content script, `document_start`): `document.hidden` false, `visibilityState` "visible", `hasFocus()` true, `visibilitychange`
  swallowed in the capture phase, and `requestAnimationFrame` made to fire within 50 ms. It edits the **page's** objects through `wrappedJSObject` +
  `exportFunction`; an injected inline `<script>` would be blocked by the sites' CSP.
- Firefox prefs written into the launcher's managed `user.js` block (names checked against Firefox 157: they are strings compiled into XUL / in
  `browser/defaults/preferences/firefox.js`; the block is refreshed on every launch, so old profiles pick them up):

  | pref | value | default |
  |---|---|---|
  | `dom.min_background_timeout_value` | 4 | 1000 |
  | `dom.min_background_timeout_value_without_budget_throttling` | 4 | 1000 |
  | `dom.timeout.enable_budget_timer_throttling` | false | true |
  | `dom.suspend_inactive.enabled` | false | true |
  | `dom.ipc.processPriorityManager.enabled` | false | true |
  | `layout.throttled_frame_rate` | 60 | 1 |
  | `browser.tabs.unloadOnLowMemory` | false | true |
  | `browser.tabs.min_inactive_duration_before_unload` | 86400000 | 600000 |

- `launch_browser --headless` starts Firefox with `--headless`.

### 5. Live progress

The launcher prints, unbuffered, one line per landed record (the extension POSTs `/event` the moment a record is saved), `HEALTH` lines when a
provider is paused, and `=== HH:MM:SS START ...` / `=== HH:MM:SS END ...` lines:

```
=== 13:25:13 START .../run-plan.json claude,chatgpt,gemini,grok x 2 items
13:25:57 chatgpt neutral#r0#local_nancy__open ok stream 20.8s
13:26:17 claude neutral#r0#local_nancy__open ok poll 47.3s
13:22:46 mistral HEALTH rate_limited Messages limit reached ...   (provider paused, not retried)
=== 13:27:45 END 8/8 ok
```

`END` appends `; blocked: provider=status` and the exit code is 3 when a provider ended blocked (0 = finished clean, 1 = did not finish).

### 6. Preflight

`python -m churvey.survey.launch_browser --preflight [--providers a,b] [--headless] [--out DIR]`: one short question (`Réponds uniquement par le mot : OK`)
to each provider, one attempt each. Prints `PREFLIGHT <provider> ok|logged_out|rate_limited|challenge|capture_failed <detail>` and exits 0 only if all are `ok`.

### 7. ChatGPT citations

See "ChatGPT citations check" below.

## ChatGPT citations check (pilot20, 2026-10-12)

ChatGPT **did** show sources; the parser missed them. Its stream now writes the citation markers into the answer text as JSX,
`<Cite refs={["turn671446search6","turn671446news3"]}/>`, instead of the private-use `U+E200 cite U+E202 turn... U+E201` form that `citations.js` matched. The
sources themselves (`search_result_groups`) were in the stream all along. Re-parsing the 20 raw streams with the fixed parser:

| | before | after |
|---|---|---|
| displayed citation rows over 20 answers | 4 (all `text_link`) | 222 (`chatgpt_marker`), 1 with no resolved url |
| distinct URLs | ~4 | 91 |
| `<Cite>` markers in the recorded text | 155 | 155 |

Fix: `MARKER_RE` in `ff/src/background/citations.js` accepts both marker forms. Existing runs are re-parsed with `dashboard/ingest/reparse_raw.py` (not run here).

Side findings, **not fixed**:
- 6 of the 20 recorded ChatGPT answers contain one duplicated, spliced tail (`... <Cite refs={["turn120556search` followed by the sentence again): a text-reconstruction
  problem in `capture.js parseChatgpt` with the new delta stream. The citation parser works on its own reconstruction and is unaffected.
- ChatGPT's `responseText` carries its UI markup (`<Cite .../>`, `<AsyncImage ...>`, `<AsyncImageGroup ...>`, `<Chart>`), 155 `<Cite>` tags in 20 answers. Strip downstream if a clean text is needed.

## Acceptance tests

Live, Firefox 157, profile `cn-harvest`, logged in. Outputs (logs, `run_*.jsonl`, raw completions) under
`llm_bench/data/dashboard/runs/2026-10-13_capture_tests/`.

| test | what | result |
|---|---|---|
| (a) preflight, visible, 5 providers (`a_preflight_final`) | 1 short question x chatgpt, claude, gemini, grok, mistral | chatgpt ok (stream), claude ok (poll), gemini ok (stream), grok ok (poll), mistral `rate_limited` ("Messages limit reached You have reached your message limit. Your limit will reset in 2 hours..."); exit 1 as designed, ~50 s |
| (b) headless, 2 pilot20 items x claude, chatgpt, gemini, grok (`b_headless`) | `--headless`, real questions | **8/8 ok**: claude 2/2 via **poll** (12 and 9 citations, `claude_poll`), chatgpt 2/2 stream, gemini 2/2 stream, grok 2/2 poll; 2.5 min total |
| (c) visible, windows minimised (`c_covered`) | chatgpt, gemini, claude windows minimised ~20 s into the run; probe of `document.hidden` as the content script (real) vs the page world | **8/8 ok**, no stall (same timings as (b)). While minimised: real `hidden=true, visibilityState=hidden`; page world `hidden=false, visibilityState=visible`. The runner's own `focusTab` restored the Gemini window at its next submit; chatgpt and claude stayed minimised through their second item |
| (d) Le Chat limit detection (`d_lechat_limit`, also in a, e) | live: Le Chat is limited until ~15:20 | `rate_limited` with the banner text, provider paused, record `[rate_limited] ...`, no retry. PASS (live, not a unit check) |
| (e) headless blocked by Cloudflare / login? (`e_headless_preflight`) | preflight `--headless` x 5 providers | **no provider blocked**: chatgpt, claude, gemini ok; grok showed its own "High Demand / heavy usage" banner in that run (detected as `rate_limited`; it answered headless in (b) and visible in (a) a minute later); mistral loads headless and shows the limit banner (so no challenge/login wall), no answer could be tested |
| DOM fallback (`f_dom_fallback`) | headless, `config.debugDropCaptures` drops every stream/poll capture | 4/4 `dom_fallback` (gemini 3782 c, chatgpt 9746 c, grok 4501 c, claude 5357 c); citations = answer links (gemini chips re-added by the chip scrape after this run) |
| status unit (`g_status_unit`) | fake elements injected into a live claude.ai tab, `PAGE_STATUS` read back | login button -> `logged_out`; 4 limit wordings (EN x2, FR x2) -> `rate_limited`; turnstile iframe and "Just a moment..." title -> `challenge`; a limit sentence **inside** an answer -> `ok` (no false positive); baseline ok |

### Headless verdict

| provider | headless | note |
|---|---|---|
| ChatGPT | works | stream capture identical to visible |
| Claude | works | poll |
| Gemini | works | stream; its 120 s held-open stream is still flushed by the DOM gate |
| Grok | works | poll; one preflight saw a capacity banner (provider-side, not headless-specific as far as can be told) |
| Le Chat | page loads, no Cloudflare / login wall | answer path **untested** (account limited); `readAnswer` selectors for Le Chat unverified |

Headless has no OS focus at all, and every submit worked: the runner's `focusTab` calls are best-effort. Visible mode + `visibility.js` remains the fallback.

## Known gaps

- `readAnswer` selectors are verified live for ChatGPT (new DIL markup), Gemini, Grok and Claude. DeepSeek and Le Chat are best guesses; Le Chat could not be verified while rate limited.
- Limit/login/captcha detection is phrase- and selector-based (EN/FR). A new wording or language is a miss until added to `LIMIT_RE` / `LOGIN_BTN_RE` in `page-state.js`; the fallback is the old timeout path.
- The DOM fallback records plain text (no markdown) and only the links visible in the answer, not the provider's citation structure.
- The visibility override cannot change what the OS does to a minimised window's GPU/compositor; it fixes what the page can observe. See test (c).
- The ChatGPT parser text-splice bug above.
