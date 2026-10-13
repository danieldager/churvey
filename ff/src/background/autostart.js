// Zero-click startup. `cn_bench/launch_browser.py` serves the day's run plan on a
// loopback port and installs this add-on; on load we look for that server, and if
// it answers we boot the run and stream the export back to it. If nothing is
// listening (the normal about:debugging load) this does nothing at all and the
// popup path is exactly as before.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("autostart");
  const PORTS = [8731, 8732, 8733, 8734, 8735]; // must match launch_browser.py
  const POLL_MS = 8000;

  let base = null;

  // A refused connection rejects immediately, so probing the whole range is fast.
  async function findPlan() {
    for (const port of PORTS) {
      const b = `http://127.0.0.1:${port}`;
      try {
        const r = await fetch(`${b}/run-plan.json`, { cache: "no-store" });
        if (!r.ok) continue;
        const plan = await r.json();
        if (plan && Array.isArray(plan.providers) && Array.isArray(plan.questions) && plan.questions.length) {
          return { base: b, plan };
        }
      } catch (_) { /* nothing there */ }
    }
    return null;
  }

  const post = (path, body) =>
    fetch(base + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .catch((e) => log.warn(`POST ${path} failed: ${e?.message || e}`));

  // Poll instead of hooking the runner: `overview()` already reports run status and
  // `buildExport()` already builds the payload, so the launcher gets partial results
  // on every tick and a final one when the run finishes (or is stopped by hand).
  function watch() {
    const timer = setInterval(async () => {
      let ov, payload;
      try {
        ov = await Probe.runner.overview();
        payload = await Probe.runner.buildExport();
      } catch (e) { log.error("poll", e?.message || e); return; }
      const finished = ov.status === "done" || ov.status === "stopped";
      // The raw completion bodies (parser input) go once, with the final post: they are megabytes.
      await post(finished ? "/done" : "/progress", { status: ov.status, manifest: payload.manifest, summaryText: payload.summaryText, ...(finished ? { rawCompletions: payload.rawCompletions } : {}) });
      if (finished) { clearInterval(timer); log.info(`run ${ov.status} — results posted to ${base}`); }
    }, POLL_MS);
  }

  async function boot() {
    const found = await findPlan();
    if (!found) { log.info("no launcher on 127.0.0.1 — manual (popup) mode"); return; }
    base = found.base;
    const { plan } = found;
    log.info(`launcher at ${base}: ${plan.providers.join(",")} x ${plan.questions.length} questions`);
    try {
      await Probe.runner.start(plan);
    } catch (e) {
      log.error("start", e?.message || e);
      await post("/done", { status: "error", error: String(e?.message || e) });
      return;
    }
    watch();
  }

  // Let the other background modules finish wiring up first.
  setTimeout(() => boot().catch((e) => log.error("boot", e?.message || e)), 1500);
})();
