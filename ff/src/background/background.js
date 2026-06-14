// Background entry: arm network capture (feed every completion to the runner for
// pairing) and route run-control messages from the popup to the runner.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("bg");

  Probe.capture.start((cap) => {
    try { Probe.runner.onCapture(cap); } catch (e) { log.error("onCapture", e?.message || e); }
  });

  // --- interaction recorder: network (with request bodies) + clicks/DOM from content ---
  let recording = false;
  const recEvents = [];
  function recOnBeforeRequest(details) {
    if (!recording) return {};
    let body = null;
    try {
      const rb = details.requestBody;
      if (rb) {
        if (rb.raw && rb.raw[0] && rb.raw[0].bytes) body = new TextDecoder("utf-8").decode(rb.raw[0].bytes).slice(0, 8000);
        else if (rb.formData) body = JSON.stringify(rb.formData).slice(0, 8000);
      }
    } catch (_) {}
    recEvents.push({ kind: "net", ts: Date.now(), method: details.method, url: details.url, type: details.type, body, tabId: details.tabId });
    while (recEvents.length > 3000) recEvents.shift();
    return {};
  }
  async function recBroadcast(type) {
    const tabs = await ext.tabs.query({ url: Probe.providers.allMatchPatterns() });
    for (const t of tabs) ext.tabs.sendMessage(t.id, { type }).catch(() => {});
  }
  function recOnSendHeaders(details) {
    if (!recording) return {};
    if (!/delete|clear|session|conversation|chat/i.test(details.url)) return {}; // keep it focused
    recEvents.push({ kind: "net-headers", ts: Date.now(), method: details.method, url: details.url, headers: (details.requestHeaders || []).map((h) => ({ name: h.name, value: (h.value || "").slice(0, 400) })) });
    while (recEvents.length > 3000) recEvents.shift();
    return {};
  }
  function recStart() {
    recording = true; recEvents.length = 0;
    try {
      ext.webRequest.onBeforeRequest.addListener(recOnBeforeRequest, { urls: Probe.providers.allMatchPatterns() }, ["requestBody"]);
      ext.webRequest.onBeforeSendHeaders.addListener(recOnSendHeaders, { urls: Probe.providers.allMatchPatterns() }, ["requestHeaders"]);
    } catch (e) { log.error("rec listener", e?.message || e); }
    recBroadcast(Probe.MSG.REC_ON); log.info("recording started");
  }
  function recStop() {
    recording = false;
    try { ext.webRequest.onBeforeRequest.removeListener(recOnBeforeRequest); } catch (_) {}
    try { ext.webRequest.onBeforeSendHeaders.removeListener(recOnSendHeaders); } catch (_) {}
    recBroadcast(Probe.MSG.REC_OFF); log.info("recording stopped");
  }
  function recExport() {
    const events = recEvents.slice().sort((a, b) => a.ts - b.ts);
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const url = URL.createObjectURL(new Blob([JSON.stringify({ generatedAt: new Date().toISOString(), count: events.length, events }, null, 2)], { type: "application/json" }));
    return ext.downloads.download({ url, filename: `chat-probe/recording-${stamp}.json`, saveAs: false })
      .then((id) => { setTimeout(() => URL.revokeObjectURL(url), 5000); return { ok: true, count: events.length }; });
  }

  ext.runtime.onMessage.addListener((msg, sender) => {
    if (!msg) return;
    switch (msg.type) {
      case Probe.MSG.DRIVER_READY:
        return; // informational
      case Probe.MSG.START_RUN:
        return Probe.runner.start(msg.runConfig, msg.windowId).then((r) => ({ ok: true, ...r })).catch((e) => ({ ok: false, error: String(e.message || e) }));
      case Probe.MSG.PAUSE_RUN:
        Probe.runner.pause(); return Promise.resolve({ ok: true });
      case Probe.MSG.RESUME_RUN:
        Probe.runner.resume(); return Promise.resolve({ ok: true });
      case Probe.MSG.STOP_RUN:
        Probe.runner.stop(); return Promise.resolve({ ok: true });
      case Probe.MSG.GET_OVERVIEW:
        return Probe.runner.overview().then((o) => ({ ok: true, ...o }));
      case Probe.MSG.EXPORT_RUN:
        return Probe.runner.exportRun().then((r) => ({ ok: true, ...r })).catch((e) => ({ ok: false, error: String(e.message || e) }));
      case Probe.MSG.CLEAR_RUN:
        return Probe.runner.clear().then(() => ({ ok: true }));
      case Probe.MSG.REC_START:
        recStart(); return Promise.resolve({ ok: true });
      case Probe.MSG.REC_STOP:
        recStop(); return Promise.resolve({ ok: true });
      case Probe.MSG.REC_EVENT:
        if (recording && msg.event) recEvents.push(msg.event);
        return;
      case Probe.MSG.REC_ACTIVE:
        return Promise.resolve({ recording });
      case Probe.MSG.REC_EXPORT:
        return recExport().catch((e) => ({ ok: false, error: String(e.message || e) }));
    }
  });

  log.info("background ready");
})();
