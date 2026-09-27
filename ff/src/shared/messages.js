// Message types: popup <-> background <-> content driver.
(() => {
  const Probe = (globalThis.Probe ||= {});
  Probe.MSG = Object.freeze({
    // popup -> background (run control)
    START_RUN: "START_RUN", // {runConfig, windowId}
    PAUSE_RUN: "PAUSE_RUN",
    RESUME_RUN: "RESUME_RUN",
    STOP_RUN: "STOP_RUN",
    PAUSE_PROVIDER: "PAUSE_PROVIDER", // {provider} freeze one provider (e.g. re-login); the rest keep running
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
    CAPTURE_DOM: "CAPTURE_DOM", // -> dump visible buttons/dialogs for selector authoring
    ANSWER_STATE: "ANSWER_STATE", // -> {ok, generating, len} is the visible answer finished? (Gemini flush gate)
    SCRAPE_SOURCES: "SCRAPE_SOURCES", // -> {ok, citations:[{title,url}]} scraped from the answer's source UI

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
