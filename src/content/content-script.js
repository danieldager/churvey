// Content-script entry. Resolves this tab's provider adapter, exposes status to
// the popup/SW, reacts to DRIVE/PAUSE/STOP, and auto-resumes its provider's run
// on load (after a reload / browser restart).
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("content");

  const adapter = Probe.registry.forHost(location.hostname);
  if (!adapter) {
    log.warn("no adapter for", location.hostname);
  } else {
    log.info("adapter:", adapter.id);
  }

  function safe(fn, fb) {
    try {
      return fn();
    } catch (_) {
      return fb;
    }
  }

  async function snapshot() {
    const provider = adapter ? adapter.id : null;
    return {
      host: location.hostname,
      provider,
      ready: adapter ? safe(() => adapter.isReady(), false) : false,
      modelLabel: adapter ? safe(() => adapter.modelLabel(), null) : null,
      provState: provider ? await Probe.storage.getProvState(provider) : null,
    };
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    (async () => {
      try {
        switch (msg && msg.type) {
          case Probe.MSG.GET_STATUS:
            sendResponse({ ok: true, ...(await snapshot()) });
            break;
          case Probe.MSG.DIAGNOSE:
            sendResponse({ ok: true, diagnostics: Probe.diag.capture(adapter) });
            break;
          case Probe.MSG.DRIVE:
            await Probe.orchestrator.drive();
            sendResponse({ ok: true });
            break;
          case Probe.MSG.PAUSE:
            Probe.orchestrator.pause();
            sendResponse({ ok: true });
            break;
          case Probe.MSG.STOP:
            Probe.orchestrator.stop();
            sendResponse({ ok: true });
            break;
          default:
            sendResponse({ ok: false, error: "unknown message" });
        }
      } catch (e) {
        log.error("handler error", e?.message || e);
        sendResponse({ ok: false, error: String(e?.message || e) });
      }
    })();
    return true;
  });

  // When this tab regains focus (the cycler activated it), make sure the driver
  // is running — it's a no-op if already going.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && adapter) {
      Probe.orchestrator.drive();
    }
  });

  // Auto-resume this provider's run on load. Retry a few times while the SPA
  // finishes hydrating / the login gate clears.
  (async () => {
    if (!adapter) return;
    for (let i = 0; i < 20; i++) {
      const ps = await Probe.storage.getProvState(adapter.id);
      if (ps && ps.status === "running") {
        if (adapter.isReady()) {
          Probe.orchestrator.drive();
          break;
        }
      } else if (ps && ps.status !== "running") {
        break; // not our job right now
      }
      await Probe.cadence.sleep(1000);
    }
  })();

  log.info("content ready on", location.hostname);
})();
