# Preparing the accounts: `churvey account prepare`

A temporary chat does not stop account memory (see [isolation.md](isolation.md)): ChatGPT's temporary chat still
« can reference memory », and in the canary it looked through earlier chats. So before a survey each account should
remember nothing and hold no chats. `churvey account prepare` does that for every chatbot, through the provider's own
settings and delete:

```
churvey account prepare --dry-run                 # read each account, print what would be done, change nothing
churvey account prepare [--chatbots chatgpt,mistral] [--visible]
```

1. **Read** (no change): who is signed in, the memory setting, the chat history. One Firefox session, no window.
2. **Print the plan**, per account: memory on / off and how it will be switched off; how many chats and how they will
   be deleted.
3. **Ask**: type `prepare`. Anything else, or no terminal, stops here. `--dry-run` stops before asking.
4. **Do it, then check it**: switch memory off and read the setting back; delete every chat and list the history again.
   A chatbot is « verified » only if memory now reads off and the history lists no chat.
5. **Log**: `~/.churvey/account/prepare_<date>_<time>/prepare.json` (the reading, the plan, the results, the
   confirmation time) and `prepare.log` (what was printed). The Firefox sessions' files are in `read/` and `do/`.

`churvey run` never does any of this. It still refuses to start while an account's memory is on, and now says
`churvey account prepare --chatbots <those>`.

## Per chatbot

| Chatbot | Memory off (then read back) | Delete all chats (then list again) |
|---|---|---|
| ChatGPT | `PATCH /backend-api/settings/account_user_setting?feature=sunshine&value=false`, same for `moonshine` (the « Enable memory » switch drives both); read back from `/backend-api/settings/user` | bulk: `PATCH /backend-api/conversations {is_visible:false}` (Settings > Data controls > Delete all chats) |
| Claude | the switches « Search and reference chats » and « Generate memory from chats » on claude.ai/settings/memory; read back from `/api/account` (`enabled_saffron*`) | one by one: `DELETE /api/organizations/<org>/chat_conversations/<id>` |
| Gemini | the « Memory » switch on gemini.google.com/saved-info; read back from that switch. Gemini Apps Activity is **not** changed | one by one through each sidebar conversation's menu > Delete (Gemini has no list or delete API we know of) |
| Grok | `POST /rest/user-settings {enableMemory:false}` (grok.com's own settings call); read back from `/rest/user-settings` | one by one: `DELETE /rest/app-chat/conversations/<id>` (a hard delete), then the same for every chat in the trash (`/rest/app-chat/conversations/deleted`): grok.com's « delete all », `DELETE /rest/app-chat/conversations`, only moves chats to the trash |
| Le Chat | tRPC `user.setKnowledgeEnabled {enabled:false}` (what the « Knowledge » switch in Settings > Privacy calls); read back from tRPC `user.getKnowledgeToggleState` | bulk: tRPC `chat.deleteAll` (Settings > danger zone) |

A memory already off is left alone, and an empty history is not touched. Temporary chats cannot be deleted on ChatGPT
(kept by OpenAI up to 30 days, out of the history) or Gemini (never in the history); the plan says so.

The code: `memoryOff`, `deleteAllChats` and `loginState` in `ff/src/content/drivers.js`; `whoami`, `memoryOff`,
`deleteAll` in `ff/src/background/isolation.js`; `churvey/account.py`.

## What has been verified

`churvey account prepare --dry-run` on the cn-harvest accounts, 14 October 2026 13:18 (read only):

| Account | Memory | Chats | Would do |
|---|---|---|---|
| ChatGPT misinfodashboard@gmail.com | off (sunshine, moonshine false) | 0 | nothing |
| Claude misinfodashboard@gmail.com | off | 9 | delete 9, one by one |
| Gemini (Daniel Dager, misinfodashboard@gmail.com) | off, no saved info | 12 in the sidebar | delete them through the sidebar menu |
| Le Chat | off (Knowledge false) | 0 | nothing |
| Grok | off (enableMemory false) | 1 | delete it, and the trash |

Memory was ON for ChatGPT and Le Chat at 09:40 the same morning and off at 13:18 (switched off by hand in between).

Never run for real yet, so these are **not verified**: ChatGPT's `account_user_setting` and bulk `PATCH
/backend-api/conversations` (logged-out chatgpt.com serves a different app, so its bundle could not be checked; they
are the calls the settings page is known to make); Claude's claude.ai/settings/memory page and switch labels; Gemini's
sidebar menu selectors; Le Chat's `user.setKnowledgeEnabled` and `chat.deleteAll` (seen in its bundle, never called);
Grok's `POST /rest/user-settings` (seen in its bundle, never called). Grok's delete by id and Claude's and Le Chat's
`chat.delete` were verified on 14 October (docs/isolation.md).
