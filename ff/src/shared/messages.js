// Message types: popup <-> background <-> content driver.
(() => {
  const Probe = (globalThis.Probe ||= {});
  Probe.MSG = Object.freeze({
    // popup -> background (run control)
    START_RUN: "START_RUN", // {runConfig, windowId}
    PAUSE_RUN: "PAUSE_RUN",
    RESUME_RUN: "RESUME_RUN",
    STOP_RUN: "STOP_RUN",
    GET_OVERVIEW: "GET_OVERVIEW",
    EXPORT_RUN: "EXPORT_RUN",
    CLEAR_RUN: "CLEAR_RUN",

    // background -> content driver (two-step so a navigating "new chat" can't
    // break the submit: conductor waits for the tab to be ready in between)
    NEW_CHAT: "NEW_CHAT", // {private} -> start a fresh/private chat (may navigate)
    SUBMIT: "SUBMIT", // {prompt} -> type + submit
    PURGE: "PURGE", // DeepSeek: delete all chats
    PING: "PING", // -> {ok, ready, visibility}
    CAPTURE_DOM: "CAPTURE_DOM", // -> dump visible buttons/dialogs for selector authoring

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
