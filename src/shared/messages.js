// Message-type constants shared across popup <-> service worker <-> content script.
(() => {
  const Probe = (globalThis.Probe ||= {});

  Probe.MSG = Object.freeze({
    // popup -> service worker (run control; SW opens tabs + writes config/state)
    START_RUN: "START_RUN", // {runConfig}
    RESUME_RUN: "RESUME_RUN", // reopen tabs for in-progress providers
    PAUSE_ALL: "PAUSE_ALL",
    STOP_ALL: "STOP_ALL",
    GET_OVERVIEW: "GET_OVERVIEW", // aggregate run + per-provider progress + counts

    // popup -> service worker (data)
    EXPORT: "EXPORT",
    CLEAR_RECORDS: "CLEAR_RECORDS",
    GET_RECORD_COUNT: "GET_RECORD_COUNT",

    // service worker -> content (per tab)
    DRIVE: "DRIVE", // (re)check storage and run this provider's queue
    PAUSE: "PAUSE",
    STOP: "STOP",
    GET_STATUS: "GET_STATUS", // readiness + this provider's provState
    DIAGNOSE: "DIAGNOSE", // capture page diagnostics on demand

    // content -> SW: this tab finished an item; focus the next provider tab
    YIELD: "YIELD",

    // content -> popup/SW (broadcast)
    STATUS: "STATUS", // a provState snapshot changed
    PROGRESS: "PROGRESS", // an item finished (record attached)
  });
})();
