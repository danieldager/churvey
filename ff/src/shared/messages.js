// Message types: popup <-> background <-> content driver.
(() => {
  const Probe = (globalThis.Probe ||= {});
  Probe.MSG = Object.freeze({
    // popup -> background (run control)
    START_RUN: "START_RUN", // {runConfig, windowId}
    PAUSE_RUN: "PAUSE_RUN",
    RESUME_RUN: "RESUME_RUN",
    STOP_RUN: "STOP_RUN",
    PAUSE_PROVIDER: "PAUSE_PROVIDER", // {provider} freeze one provider (account swap); the rest keep running
    RESUME_PROVIDER: "RESUME_PROVIDER", // {provider} unfreeze + clear its backoff so it re-asks immediately
    GET_OVERVIEW: "GET_OVERVIEW",
    EXPORT_RUN: "EXPORT_RUN",
    IMPORT_RUN: "IMPORT_RUN", // {manifest} -> restore a .run.json (config + records); Resume fills gaps
    LIST_RUNS: "LIST_RUNS", // -> {runs:[{runId, ok, total, ...}]} run history with progress
    SELECT_RUN: "SELECT_RUN", // {runId} -> make a past run active (Resume continues it)
    CLEAR_RUN: "CLEAR_RUN",
    CLEAR_COOKIES: "CLEAR_COOKIES", // {domains} -> full clear to fix 431 header bloat (re-login after)

    // background -> content driver (two-step so a navigating "new chat" can't
    // break the submit: conductor waits for the tab to be ready in between)
    NEW_CHAT: "NEW_CHAT", // {private} -> start a fresh/private chat (may navigate)
    SUBMIT: "SUBMIT", // {prompt} -> type + submit
    PURGE: "PURGE", // DeepSeek: delete all chats
    PING: "PING", // -> {ok, ready, visibility}
    ISOLATION_STATE: "ISOLATION_STATE", // -> {ok, temporary, newChat, evidence} is the composer in a fresh temporary chat? (checked before every submit)
    MEMORY_STATUS: "MEMORY_STATUS", // -> {ok, status:"on"|"off"|"unknown", detail} | {ok, needs:url} account memory setting, read only
    DELETE_CHATS: "DELETE_CHATS", // {ids} -> {ok, results:{id: "deleted"|"not_found"|"unsupported"|"error .."}} the provider's own delete
    LIST_CHATS: "LIST_CHATS", // -> {ok, ids} every chat in the account's history (purge --everything only)
    CAPTURE_DOM: "CAPTURE_DOM", // -> dump visible buttons/dialogs for selector authoring
    ANSWER_STATE: "ANSWER_STATE", // -> {ok, generating, len} is the visible answer finished? (Gemini flush gate)
    GROK_POLL: "GROK_POLL", // {convId, prompt} -> {ok, state:"pending"|"done"|"mismatch", response} one read of the grok.com conversation (answer arrives over a websocket, not HTTP)
    POLL: "POLL", // {convId, prompt} -> {ok, state:"pending"|"done"|"mismatch", response} same read for any driver with poll() (claude, grok)
    PAGE_STATUS: "PAGE_STATUS", // -> {ok, state:"ok"|"rate_limited"|"logged_out"|"challenge", text} what the page itself says (limit banner, login wall, captcha)
    READ_ANSWER: "READ_ANSWER", // -> {ok, text, links, generating, finished, len} last answer as rendered (DOM fallback when no capture lands)
    SCRAPE_SOURCES: "SCRAPE_SOURCES", // -> {ok, citations:[{title,url}]} scraped from the answer's source UI
    VISIBLE_SOURCES: "VISIBLE_SOURCES", // -> {ok, links:[{url,title,where}], buttons:[text]} what the page shows as sources (audit of capture; run config.auditSources)

    // interaction recorder ("teach me this flow") — popup -> background
    REC_START: "REC_START",
    REC_STOP: "REC_STOP",
    REC_EXPORT: "REC_EXPORT",
    REC_ACTIVE: "REC_ACTIVE", // content/popup asks if recording is on
    // background -> content
    REC_ON: "REC_ON",
    REC_OFF: "REC_OFF",
    // content -> background
    REC_EVENT: "REC_EVENT", // {event:{kind:'click'|'dom', ...}}

    // content -> background
    DRIVER_READY: "DRIVER_READY",
  });
})();
