# Chat isolation

Every question must be answered as if it were the first thing the account ever asked: a brand-new chat, in the site's
temporary / private mode, on an account that remembers nothing. This page says how churvey gets there for each chatbot,
how each record proves it, what was measured on 14 October 2026, and what a person has to switch off by hand.

## Why: the 13 October pilot

In the pilot of 13 October (`llm_bench data/dashboard/runs/2026-10-12_pilot20`), ChatGPT's answer to
`local_vierzon__fp` begins « Il y a donc une inversion importante par rapport à ce que j'avais expliqué précédemment ».
It had read its own answer to `local_vierzon__open`, asked a minute earlier.

It was the chat, not account memory. The raw ChatGPT streams of that run carry the conversation id: the 20 ChatGPT
items went into **two** conversations, 16 into `6ace08db-…` and the last 4 into `6ace0c6b-…` (after the tab reloaded
at 10:48). Each request's `parent_id` chains to the previous turn, and the extension log shows no page load between
items. The driver only opened a new temporary chat if the page was not already on `?temporary-chat=true` *or* showed an
assistant message, found with `[data-message-author-role="assistant"]`. ChatGPT's new markup no longer has that
attribute, so a used temporary chat always looked empty and was reused. Every record still said `private: true`. Gemini
(20 distinct chats out of 20), Grok (20/20) and Le Chat did open a new chat per question.

## How each question gets a new temporary chat

| Chatbot | New temporary chat | Proof before typing (`isolationState`) | Proof after the answer |
|---|---|---|---|
| ChatGPT | a fresh page load of `/?temporary-chat=true` for **every** question | home route (no `/c/<id>`), the `?temporary-chat=true` URL and the « Turn off temporary chat » switch on the page | the request the page sent (`POST backend-api/f/conversation`): `history_and_training_disabled: true`, `parent_message_id: "client-created-root"` and no `conversation_id`. Conversation id from the stream |
| Claude | « Exit incognito » if in it, then « Use incognito » (fallback `/new?incognito`) | `/new?incognito` and the « Exit incognito » button | the conversation read back (`chat_conversations/<id>`): `is_temporary: true`, 1 human turn |
| Gemini | new chat (Shift+Cmd+O or the sidebar), then the temporary-chat button only if it is off | the button's host `<gem-icon-button>` has class `temp-chat-on`; no earlier turn on screen; URL `/app` (no chat id) | conversation id `c_…` from the stream |
| Grok | « Chat », then `a[aria-label="Switch to Private Chat"]` only if private is off | the link reads « Switch to Default Chat » (private on); no `/c/<id>` in the URL | `conversations_v2/<id>` says `temporary: true` (when the answer is read back by poll); conversation id |
| Le Chat | a fresh load of `/work/temporary-chat` | that route and the « Exit temporary chat » link | the chat id in the `/api/chat` request and stream |

The runner checks `isolationState` right before typing. If the composer is not in a new temporary chat it starts one
again once; if it still cannot confirm it, the item fails with `[not_isolated] …` and is retried, instead of being asked
in an ordinary chat (run config `allowNotIsolated: true` turns that off; nothing sets it).

After the answer, `isolationFor` (runner.js) combines the three readings and one more check: the chat id must not have
been seen before in the run for that chatbot. That last check alone would have caught the pilot. Any disagreement makes
the record an error `[not_isolated] …` (the answer text is kept on the error record). Every record now carries:

```
"isolation": {"new_chat": true, "temporary": true, "followup": false, "chat_id": "6acf32a9-…",
              "evidence": "page /?temporary-chat=true, 'Turn off temporary chat' switch; request history_and_training_disabled=true conversation_id=null parent_message_id=client-created-root temporary_chat_requests_personalization=true; chat 6acf32a9-…"}
```

A follow-up question (`followup_of`) is asked in its parent's chat on purpose: `followup: true`, `new_chat: false`.

## Question order

Two questions of the same `group` (an open question and its false-premise twin) are never asked back to back to the same
chatbot: `questions.spaced_order` spreads them, at least 3 other questions apart where the set allows (pilot20: 9 apart).
The order is in `churvey-run.json` (`question_order`, `min_group_gap`). Sets with follow-ups keep their file order.

## Account memory

A temporary chat does not stop the account's memory: ChatGPT's temporary chat says « This chat can reference memory,
plugins, and custom instructions ». In the canary, ChatGPT's second chat answered « Je n'ai pas retrouvé le mot de code
que tu m'avais donné dans nos conversations précédentes »: it looked through past chats. So memory must be off, and that
is an account setting churvey **reads but never changes**.

`churvey doctor` prints on / off / unknown per account and warns loudly when one is on. `churvey run` refuses to start
while any is on, or unknown unless `--allow-memory-unknown`.

| Chatbot | Read from | 14 Oct 2026 | Where to switch it off |
|---|---|---|---|
| ChatGPT (misinfodashboard@gmail.com, free) | `GET /backend-api/settings/user`: `sunshine` (saved memories), `moonshine` (chat history); same as the « Enable memory » switch | **ON** (both true) | chatgpt.com → Settings → Personalization → « Enable memory » off (https://chatgpt.com/settings/personalization) |
| Claude (misinfodashboard@gmail.com, Pro) | `GET /api/account` settings `enabled_saffron` (generate memory), `enabled_saffron_search` (search past chats) | off (both null; both switches show off) | claude.ai → Settings → Memory |
| Gemini | the « Memory » switch on gemini.google.com/saved-info (no API found; read from the page) | off; no saved info. « Your instructions » is on but empty | Settings → Personal context → « Memory » |
| Grok | `GET /rest/user-settings`: `enableMemory` (and `allowXPersonalization`) | off (both false) | grok.com → Settings (menu path not re-checked) |
| Le Chat (misinfodashboard) | tRPC `user.getKnowledgeToggleState` | **ON** (« Knowledge ») | profile menu → Settings → Privacy → Personalization → « Knowledge » off |

ChatGPT also offers a per-chat « Unpersonalized » option on the temporary-chat page (the request then says
`temporary_chat_requests_personalization: false`). churvey does not click it: it is not known whether the choice
persists as an account setting. The request flag is in every ChatGPT record's evidence.

## Canary

`churvey doctor`, and the preflight of every `churvey run`: chat 1 « Retiens ce mot de code : girafe-47. Réponds juste
OK. », then a new chat 2 « Quel mot de code t'ai-je donné ? ». PASS if chat 2 contains neither « girafe » nor « 47 »,
both records prove a new temporary chat, and the two chat ids differ. Both chats are deleted afterwards. A chatbot that
fails is left out of the run with a message.

| Chatbot | Temporary mode | Verified per record | Memory | Canary 14 Oct | Chat 2 said |
|---|---|---|---|---|---|
| ChatGPT | Temporary chat | yes (page + request + new chat id) | ON | PASS (09:44, 09:48) | « Je n'ai pas retrouvé le mot de code … dans nos conversations précédentes » |
| Claude | Incognito | yes (page + `is_temporary` + 1 turn) | off | PASS (3 times) | « Vous ne m'avez donné aucun mot de code … c'est le premier message » |
| Gemini | Temporary chat | yes (page + new chat id) | off | PASS (3 times) | « Ce que vous demandez va au-delà de ce que permet ma programmation » |
| Grok | Private chat | yes (page + `temporary: true` + 1 turn) | off | **not completed**: chat 1 isolated (10:25), chat 2 hit the free-plan limit (« 2 hours 8 minutes before limit is gone ») | — |
| Le Chat | Temporary chat | yes (page + chat id in request) | ON | PASS (09:46) | « Vous ne m'avez donné aucun mot de code dans cette conversation — c'est notre premier échange » |

## Deleting chats

These are real accounts with other chats in them, so deletion is by id, of chats churvey itself created:

* The extension records every chat a run creates (`manifest.chats`); the launcher writes them to the run folder's
  `chats.jsonl`. Each delete attempt goes to `purged.jsonl`.
* `churvey run` deletes its chats when it ends (config `purgeAfter`), unless `--keep-chats`. Before a run, and in
  `churvey doctor`, leftover churvey chats from any earlier run folder are deleted first.
* `churvey purge --run <run>` / `--all-churvey` deletes only chats listed in `chats.jsonl`.
* `churvey purge --everything --chatbot <c>` empties one whole account: it lists and counts the chats, asks you to type
  the chatbot's name, then deletes them. It is never run by a run, a check or the preflight.

| Chatbot | Delete used | Temporary chats |
|---|---|---|
| ChatGPT | `PATCH /backend-api/conversation/<id> {is_visible:false}` | **cannot be deleted**: the PATCH answers 404 and DELETE 405, while GET still returns the chat with `is_temporary_chat: true`. OpenAI keeps temporary chats up to 30 days, out of the history. Recorded as `unsupported` |
| Claude | `DELETE /api/organizations/<org>/chat_conversations/<id>` | deleted |
| Gemini | none found | temporary chats never enter the history and have no delete by id: `unsupported` |
| Grok | `DELETE /rest/app-chat/conversations/<id>` | deleted (afterwards `response-node` answers 404) |
| Le Chat | tRPC `chat.delete {id}` | deleted (200) |

Measured: the canary chats of every check were deleted this way (Claude, Grok, Le Chat) or marked `unsupported`
(ChatGPT, Gemini); `churvey purge --run isotest_2026-10-14_094829` deleted Claude's 3 chats, marked Gemini's 3
`unsupported`, and a second call found nothing left.

## Seen along the way

* Grok, rate limited (« 26 minutes before limit is gone »), was recorded through the DOM fallback with the **prompt** as
  its answer: the fallback read the user's own bubble. `page-state.js` now skips the right-aligned user turn
  (`.items-end`) and treats « before limit is gone » / « much higher limits » as a limit banner.
  The two earlier Grok canaries of the morning (09:39, 09:44) were therefore not real passes: both « answers » were
  the prompts. Rerun `churvey doctor --chatbots grok` once the limit has reset.
* A Firefox killed during startup counts as a failed start; after several, Firefox restarted itself into safe mode
  without our arguments (no debugger port, so the add-on never installed: « Firefox never opened its debugger server »).
  The launcher's `user.js` block now sets `toolkit.startup.max_resumed_crashes = -1`. To unstick the cn-harvest profile
  once, `toolkit.startup.recent_crashes` was reset to 0 and `InvalidateCaches=1` removed from `compatibility.ini`.
