// Generic streamed-response completion detector.
// Resolves when BOTH signals agree: (a) quiescence — the response node stops
// mutating for QUIESCENCE_MS, and (b) control-state — generation is not ongoing.
// A hard timeout resolves anyway with status "truncated".
//
// VISIBILITY-AWARE: background tabs are throttled by Chrome and many chat sites
// pause streaming when hidden. So we (1) only accumulate the timeout while the
// tab is visible, and (2) never declare completion while hidden, resetting the
// quiescence window when the tab regains focus. This prevents both false
// "truncated" and false "ok" (early, partial) captures during tab cycling.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("watcher");

  function visible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function waitForComplete(cfg) {
    const quiescenceMs = cfg.quiescenceMs ?? 1200;
    const timeoutMs = cfg.timeoutMs ?? 120000;
    const minWaitMs = cfg.minWaitMs ?? 1500;

    return new Promise((resolve) => {
      let lastMutation = Date.now();
      let visibleMs = 0; // accumulated foreground time (timeout basis)
      let activeMs = 0; // foreground time since start (minWait basis)
      let lastTick = Date.now();
      let wasHidden = false;
      let observer = null;
      let poll = null;
      let done = false;

      const finish = (status) => {
        if (done) return;
        done = true;
        if (observer) observer.disconnect();
        if (poll) clearInterval(poll);
        const text = safe(cfg.extractText);
        log.info(`response complete (${status}), ${text.length} chars`);
        resolve({ text, status });
      };

      const attachObserver = () => {
        const node = cfg.getResponseNode();
        if (!node) return false;
        observer = new MutationObserver(() => {
          lastMutation = Date.now();
        });
        observer.observe(node, { childList: true, subtree: true, characterData: true });
        return true;
      };

      const tryAttach = setInterval(() => {
        if (done) return clearInterval(tryAttach);
        if (attachObserver()) clearInterval(tryAttach);
      }, 150);

      poll = setInterval(() => {
        const t = Date.now();
        const dt = t - lastTick;
        lastTick = t;

        // Paused while hidden: don't time out, don't conclude.
        if (document.visibilityState !== "visible") {
          wasHidden = true;
          return;
        }
        // Just regained focus: give a fresh quiescence window before concluding,
        // since the site may resume streaming now.
        if (wasHidden) {
          wasHidden = false;
          lastMutation = t;
          return;
        }

        visibleMs += dt;
        activeMs += dt;

        if (visibleMs > timeoutMs) return finish("truncated");
        if (activeMs < minWaitMs) return;

        const streaming = safeBool(cfg.isStreaming, true);
        const quiet = t - lastMutation > quiescenceMs;
        if (!streaming && quiet) finish("ok");
      }, 200);
    });
  }

  function safe(fn) {
    try {
      return fn() || "";
    } catch (_) {
      return "";
    }
  }
  function safeBool(fn, fallback) {
    try {
      const v = fn();
      return typeof v === "boolean" ? v : fallback;
    } catch (_) {
      return fallback;
    }
  }

  Probe.watcher = { waitForComplete, visible };
})();
