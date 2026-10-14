# The monthly capability probe: `churvey probe`

The chatbot sites change their pages and endpoints without notice; on 13 October 2026 a renamed attribute was enough
for ChatGPT to answer 16 questions in one chat. `churvey probe` tries, on every chatbot, each action churvey depends on,
says which still work, and lists what changed since the previous probe, so a change is found by the probe and not by
a survey.

```
churvey probe [--chatbots a,b] [--visible]
churvey probe --destructive            # also switch account memory off and read it back (asks first)
churvey probe --install-schedule       # write the monthly schedule file and print how to load it (not loaded)
```

## What it does

Two Firefox sessions on the churvey profile, no window by default.

1. **Pages, no message** (`ff/src/background/probe.js`): sign-in state (the driver's account endpoint and what the
   page shows), the selectors on the home page, a new chat and a new temporary chat (what `isolationState` says before
   anything is typed), the endpoints churvey reads, the limit-banner detector (a test banner is put on the page and
   must be detected), the memory setting and the switches on its settings page, the chat history list. A screenshot (JPEG)
   of the home page, the temporary chat and the settings page.
2. **Three messages per signed-in chatbot**, through the ordinary runner (config `probe`): the isolation canary's two
   (« Retiens ce mot de code : girafe-47 », then in a new chat « Quel mot de code t'ai-je donné ? ») and one question
   that needs a web search (« Quelles sont les dernières actualités de la ville de Vierzon ? Donne tes sources avec
   leurs liens. »). After each answer the runner also reads the answer off the page the way the DOM fallback would.
   The chats are deleted at the end. A chatbot that is signed out gets no message.

## The checks

| Check | PASS when |
|---|---|
| `logged_in` | the account endpoint and the page agree (signed in, or signed out) |
| `new_chat` | after « new chat » the page is a new chat (no chat id, no earlier turn) |
| `temporary_chat` | after « new temporary chat » `isolationState` proves it (the evidence is in the report); as in a run, one more « new temporary chat » is allowed, and the evidence then says « on the second try » |
| `submit` | a question was typed, sent and answered |
| `stream_capture` | ChatGPT, Gemini, Le Chat: an answer was captured from the network stream |
| `poll_capture` | Claude, Grok: an answer was read back from the conversation endpoint |
| `dom_fallback` | the page text read by the DOM fallback matches the captured answer (word overlap ≥ 0.6) |
| `citations` | the web-search question's answer has at least one citation with a URL |
| `banner_detection` | a test limit banner put on the page is detected |
| `memory_readable` | the memory setting reads on or off |
| `memory_toggle` | its switches are found on the settings page and agree with the setting (Grok: the setting field is there; the toggle is an API call). With `--destructive`: switched off and read back off |
| `delete_one` | one of the probe's own chats was deleted (N/A where temporary chats cannot be deleted: ChatGPT, Gemini) |
| `delete_all_available` | the whole history can be listed (what `account prepare` deletes from) |
| `canary` | chat 2 knows nothing of the code word, both chats are new temporary chats with different ids |

Status: **PASS**, **FAIL**, **CHANGED** (it works, but something it depends on differs from last time), **SKIP** (could
not be tried: signed out, rate limited, no message sent), **N/A** (not how this chatbot works).

## What « changed » means

Each check keeps a fingerprint of what it depends on:

* the selector of each of the driver's lists that matches the page (`home.composer`, `temp.privateOn`, …), and which
  ones match none;
* the aria-labels of the controls churvey uses (temporary chat, new chat, memory, delete, send);
* the shape of the endpoints it reads: status and the type of each field churvey reads, e.g.
  `200 sunshine:boolean moonshine:boolean`;
* the capture method of the answers, the labels of the memory switches, whether citations were parsed, the sign-in state.

Every value is compared with the previous probe's `report.json`. A check is compared only when both probes observed it,
so a chatbot that was signed out this time does not report everything as gone. A PASS whose fingerprint moved becomes
CHANGED; the report lists each moved value, old → new.

## Output

`~/.churvey/probes/<date>/` (a second probe the same day: `<date>_2`):

* `report.md`: the table (checks × chatbots), what changed since the previous probe, the failures with their
  screenshots, then each chatbot's checks with their detail;
* `report.json`: the same, with the fingerprints (the next probe compares against this file);
* `raw.json`: everything the two sessions observed; `<chatbot>_<check>.jpg`, a screenshot for each failed check;
* the console prints the table, the changes and the report's path.

The Firefox sessions' own files go to `~/.churvey/runs/_probe/<date>/` (so a chat the probe could not delete is a
leftover that the next `doctor` / `run` / `purge --all-churvey` deletes).

Exit code: 0 only if no check is FAIL or CHANGED.

## Cost

At most 3 messages per signed-in chatbot, once a month. The rest reads pages and endpoints.

## Monthly schedule

`churvey probe --install-schedule` writes, without loading it:

* macOS: `~/.churvey/schedule/com.churvey.probe.plist`, a launchd agent that runs `churvey probe` at 09:00 on the 1st of
  every month (log: `~/.churvey/probes/scheduled.log`). To load it:
  `cp ~/.churvey/schedule/com.churvey.probe.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.churvey.probe.plist`
* Linux: `~/.churvey/schedule/churvey-probe.cron`, one crontab line. To load it:
  `(crontab -l 2>/dev/null; cat ~/.churvey/schedule/churvey-probe.cron) | crontab -`

A probe that starts while a run holds the profile stops at once (« Firefox is already running on profile »).

## Measured

14 October 2026, on a fresh Firefox profile signed in to nothing (so every check that needs an account is SKIP):

| check | ChatGPT | Claude | Gemini | Le Chat | Grok |
|---|---|---|---|---|---|
| logged_in (signed out, detected) | PASS | PASS | PASS | PASS (sent to the sign-in host) | PASS |
| new_chat | PASS | SKIP | PASS | SKIP | PASS |
| banner_detection | PASS | PASS | PASS | SKIP (page never opened) | PASS |
| everything else | SKIP | SKIP | SKIP | SKIP | SKIP |

The first runs found three real faults, fixed in `page-state.js` / `probe.js`:

* Gemini's root element `<chat-app>` has class `enable-lr26-markdown-styling` and grok.com's app box `print:prose`; both
  matched the « this is answer text » selector, so **every login button and limit banner on Gemini and Grok was
  ignored**. A box that holds the composer is now the app shell, not a message.
* claude.ai/login carries an invisible Cloudflare widget and was read as « challenge » instead of signed out.
* `tabs.captureVisibleTab` does not exist without the `<all_urls>` permission, and hangs in headless Firefox: the
  probe now has the permission, small JPEGs and a 10 s bound.

Not yet run: the signed-in checks (the cn-harvest accounts, at most 3 messages each). The first signed-in probe is the
baseline the monthly ones compare with.

## Baseline 2026-10-14

The first signed-in probe (cn-harvest accounts, 13:52–14:07, run with `--visible`): 56 PASS, 6 FAIL, 8 N/A. Report:
`~/.churvey/probes/2026-10-14_3/` of that home. The six FAILs, what caused them and what changed (branch `probe-fixes`):

| chatbot · check | cause | fix |
|---|---|---|
| ChatGPT · citations | the answer now writes its sources into the DIL markup as `<Link url=".." title=".."/>` (no `<Cite>` marker at all, no `content_references` items); `dilClean` dropped the tag, so the text read « Source : . » and no citation was parsed. Names written as `<Entity value=".."/>` vanished the same way | `citations.js`: `<Link>` is shown as its title and becomes a citation (`via: "chatgpt_link"`, anchored on the text before it), `<Entity>` is shown as its value. The probe's own stream now parses to 11 citations. Test: `tests/test_citations_js.py` (QuickJS, dev dependency) |
| Grok · dom_fallback | the check was wrong: `probe.py` expected Grok's answers to come by the DOM fallback; they come by poll (3/3), as `runner.js` does since 13 October | Grok is a poll chatbot in `probe.py`; `dom_fallback` compares the page text with the polled answer, as for the others. Test: `test_grok_is_polled_and_its_page_text_compared` |
| Gemini · temporary_chat | the UI did not change (the same selectors matched; every message of the run went into a temporary chat, `temp-chat-on`). The probe took a different path from the runner: no window focus, the next step after a fixed 1.5 s, no second try; with the machine overloaded (below) the click did not take | the probe now does what the runner does (`runner.js submitItem`): focus the window, wait for the composer, start the chat, and start it once more if `isolationState` does not prove a new temporary chat; the evidence then says « on the second try » |
| Le Chat · temporary_chat | same: the route `/work/temporary-chat` still works (every message of the run went there, « Exit temporary chat » link). The probe's NEW_CHAT reached a page whose composer was not there yet, and the driver refuses a NEW_CHAT then (« not ready ») | same fix: the probe waits for the composer (`ready(tab, t, composer=true)`) before and after NEW_CHAT |
| Gemini · memory_toggle | `tabFor` navigated to `/saved-info`, slept 2.5 s and asked the content script; on the loaded machine the OLD page was still there, answered the PING, then unloaded under the next message (« Receiving end does not exist »; the screenshot is a blank page) | `isolation.js tabFor` waits until the tab has left the old page and the new one is `complete`; `call()` asks once more when the page was replaced under it |
| Claude · memory_toggle | the selector was a guess: `/settings/memory` now opens the settings dialog on General; « Memory » is an entry of the dialog's menu | `memoryControls` clicks a settings-menu entry (`memoryNav: /^memory$/i` for Claude; exact text, never a switch) when the switches are not on screen. Read-only: the switches are only clicked with `--destructive` / `account prepare`. Not yet verified live |

**Isolation was never at risk.** Both temporary-chat FAILs are the probe's page session (no message sent). The three
messages per chatbot went through the runner, which proves the temporary chat before typing and asks again if not:
every Gemini record says `temp-chat button on (temp-chat-on)` and every Le Chat record `page /work/temporary-chat,
'Exit temporary chat' link`, with the canary passing on all five chatbots.

### The stalls

Two dead spells in the run log, 11:57:03 → 12:00:49 and 12:01:40 → 12:05:35: not a line, not even the runner's 25 s
`waitForReady` timeout, until Daniel brought a window forward. The machine's load average was 160–245 on 10 cores.

Cause: Firefox lowers the main-thread priority of its processes when their windows are not on screen (another Space,
covered, the app hidden) and the app is inactive (`threads.lower_mainthread_priority_in_background.enabled`, default
true; on macOS the threads get a background QoS). On a loaded machine those threads then do not run for minutes
(Mozilla bug 1960741: « deprioritized processes may not run at all for over a minute »). `dom.ipc.processPriorityManager`,
which we already turned off, is a different mechanism. Firefox's WebDriver profile turns this pref off for the same reason.
App Nap is not the cause: the content processes switch it off themselves (`NSAppSleepDisabled` in XUL), and the pref
alone brings a hidden window to headless speed (below); no `defaults write` is needed.

Fix: the pref is off in the launcher's `user.js` block (every launch, every profile). Headless stays the default for
`probe`, `doctor`, `run`, `account prepare` and `purge`; `--visible` is for watching, with the window kept on screen.

Measured: the probe's page session (no message) on a fresh scratch profile, signed out of ChatGPT, Gemini, Grok, Claude;
« hidden » = visible Firefox with its app re-hidden every 1.5 s (System Events), the nearest thing to another Space that
can be scripted; same code on both sides, only the pref differs. Wall time:

| condition | load avg | pref on (before) | pref off (after) |
|---|---|---|---|
| hidden window | 7–20 | 196 s, 164 s, 155 s | 101 s, 101 s |
| hidden window, + 12 busy loops | 18–34 | 245 s | 198 s |
| hidden window, the load of the baseline | 150–240 | > 600 s, never finished | not reproducible (the load fell) |
| headless | 20 | 100 s, 108 s | 104 s |
| headless, + 12 busy loops | 25–33 | 124 s | 119 s, 136 s |

A hidden window now runs as fast as headless at ordinary load; under heavy load it is still slower than headless, so
unattended work stays headless. (Under the busy loops, two headless launches failed to install the add-on in time;
the install-timeout retry is on branch `popup-handling`.)
