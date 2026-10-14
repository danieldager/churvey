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
| `temporary_chat` | after « new temporary chat » `isolationState` proves it (the evidence is in the report) |
| `submit` | a question was typed, sent and answered |
| `stream_capture` | ChatGPT, Gemini, Le Chat: an answer was captured from the network stream |
| `poll_capture` | Claude: an answer was read back from the conversation endpoint |
| `dom_fallback` | the page text read by the DOM fallback matches the captured answer (word overlap ≥ 0.6); Grok: its private-chat answers came through it (they are not stored on the server) |
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

<!-- PROBE_RESULTS -->
