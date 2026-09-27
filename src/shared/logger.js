// Namespaced console logging + a small ring buffer persisted to storage so the
// popup can show recent activity even after the page reloads.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const RING_KEY = "logRing";
  const RING_MAX = 200;

  // True only while this context can still reach the extension APIs. After an
  // extension reload, already-open tabs keep running the OLD content script whose
  // context is invalidated — `chrome.runtime.id` becomes undefined and any
  // chrome.* call throws "Extension context invalidated". Guard up front so we
  // skip silently instead of generating console noise.
  function alive() {
    try {
      return !!(chrome && chrome.runtime && chrome.runtime.id);
    } catch (_) {
      return false;
    }
  }

  async function pushRing(line) {
    if (!alive()) return;
    try {
      const cur = (await chrome.storage.local.get(RING_KEY))[RING_KEY] || [];
      cur.push(line);
      while (cur.length > RING_MAX) cur.shift();
      await chrome.storage.local.set({ [RING_KEY]: cur });
    } catch (_) {
      // storage may be unavailable in some contexts; logging must never throw.
    }
  }

  function fmt(ns, level, args) {
    const ts = new Date().toISOString();
    const msg = args
      .map((a) => (typeof a === "string" ? a : safeStringify(a)))
      .join(" ");
    return `${ts} [${ns}] ${level}: ${msg}`;
  }

  function safeStringify(v) {
    try {
      return JSON.stringify(v);
    } catch (_) {
      return String(v);
    }
  }

  Probe.log = {
    RING_KEY,
    make(ns) {
      const tag = `Probe:${ns}`;
      return {
        info: (...a) => {
          console.log(`[${tag}]`, ...a);
          pushRing(fmt(ns, "INFO", a));
        },
        warn: (...a) => {
          console.warn(`[${tag}]`, ...a);
          pushRing(fmt(ns, "WARN", a));
        },
        error: (...a) => {
          console.error(`[${tag}]`, ...a);
          pushRing(fmt(ns, "ERROR", a));
        },
      };
    },
    async getRing() {
      if (!alive()) return [];
      return (await chrome.storage.local.get(RING_KEY))[RING_KEY] || [];
    },
    async clearRing() {
      if (!alive()) return;
      await chrome.storage.local.set({ [RING_KEY]: [] });
    },
  };
})();
