// Namespaced console logging + a ring buffer in storage for the popup.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const RING_KEY = "logRing";
  const RING_MAX = 300;

  function alive() {
    try {
      return !!(ext && ext.runtime && ext.runtime.id);
    } catch (_) {
      return false;
    }
  }

  async function pushRing(line) {
    if (!alive()) return;
    try {
      const cur = (await ext.storage.local.get(RING_KEY))[RING_KEY] || [];
      cur.push(line);
      while (cur.length > RING_MAX) cur.shift();
      await ext.storage.local.set({ [RING_KEY]: cur });
    } catch (_) {}
  }

  function line(ns, level, args) {
    const msg = args.map((a) => (typeof a === "string" ? a : safe(a))).join(" ");
    return `${new Date().toISOString()} [${ns}] ${level}: ${msg}`;
  }
  function safe(v) {
    try { return JSON.stringify(v); } catch (_) { return String(v); }
  }

  Probe.log = {
    RING_KEY,
    make(ns) {
      const tag = `Probe:${ns}`;
      return {
        info: (...a) => { console.log(`[${tag}]`, ...a); pushRing(line(ns, "INFO", a)); },
        warn: (...a) => { console.warn(`[${tag}]`, ...a); pushRing(line(ns, "WARN", a)); },
        error: (...a) => { console.error(`[${tag}]`, ...a); pushRing(line(ns, "ERROR", a)); },
      };
    },
    async getRing() {
      if (!alive()) return [];
      return (await ext.storage.local.get(RING_KEY))[RING_KEY] || [];
    },
    async clearRing() {
      if (alive()) await ext.storage.local.set({ [RING_KEY]: [] });
    },
  };
})();
