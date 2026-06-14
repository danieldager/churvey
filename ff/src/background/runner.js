// The conductor (runs in the persistent background page = single source of truth).
// Model: focus a provider tab only long enough to SUBMIT, then move on; the
// answer streams in the background and is captured at the network layer and paired
// by tabId. Each provider runs one question at a time; providers run concurrently.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("runner");
  const REC_PREFIX = "rec::";
  const recKey = (runId, prov, itemKey) => `${REC_PREFIX}${runId}::${prov}::${itemKey}`;

  let RUN = null;
  let tickTimer = null;
  let ticking = false;
  const debugRaw = []; // raw completion bodies for parser authoring (export debug)

  const compose = (item) => Probe.prompt.compose({ persona: item.persona || null, question: { id: item.questionId, text: item.questionText } });

  async function ensureTab(pid) {
    const prov = RUN.providers[pid];
    if (prov.tabId) { try { await ext.tabs.get(prov.tabId); return prov.tabId; } catch (_) { prov.tabId = null; } }
    const meta = Probe.providers.byId(pid);
    const q = { url: meta.matchPattern };
    if (RUN.windowId) q.windowId = RUN.windowId;
    const existing = await ext.tabs.query(q);
    let tabId;
    if (existing.length) tabId = existing[0].id;
    else {
      const props = { url: meta.homeUrl, active: false };
      if (RUN.windowId) props.windowId = RUN.windowId;
      tabId = (await ext.tabs.create(props)).id;
      await Probe.cadence.sleep(2500);
    }
    prov.tabId = tabId;
    RUN.tabToProvider[tabId] = pid;
    return tabId;
  }

  async function focusTab(tabId) {
    try { await ext.tabs.update(tabId, { active: true }); const t = await ext.tabs.get(tabId); await ext.windows.update(t.windowId, { focused: true }); } catch (_) {}
    await Probe.cadence.sleep(300);
  }

  async function doneSetFor(pid) {
    const all = await ext.storage.local.get(null);
    const pre = `${REC_PREFIX}${RUN.runId}::${pid}::`;
    const done = new Set();
    for (const k of Object.keys(all)) if (k.startsWith(pre)) done.add(k.slice(pre.length));
    return done;
  }

  function nextItem(pid, doneSet) {
    const now = Date.now();
    for (const item of RUN.providers[pid].items) {
      if (doneSet.has(item.itemKey)) continue;
      const r = RUN.retryAt[pid + "|" + item.itemKey];
      if (r && r > now) continue;
      return item;
    }
    return null;
  }

  async function saveRecord(pid, item, f) {
    const { promptSent, personaId } = compose(item);
    const rec = Probe.record.build({
      runId: RUN.runId, questionId: item.questionId, questionText: item.questionText,
      promptSent, personaId, repIndex: item.repIndex, itemKey: item.itemKey, provider: pid,
      modelLabel: f.model || null, responseText: f.answer || "", status: f.status, errorMessage: f.error || null,
      latencyMs: f.latencyMs ?? null, timestampStartMs: f.startMs ?? null, timestampEndMs: f.endMs ?? null,
      private: RUN.cfg.config && RUN.cfg.config.private, captureUrl: f.url || null,
    });
    await ext.storage.local.set({ [recKey(RUN.runId, pid, item.itemKey)]: rec });
  }

  // Pairing: called for every completion capture.
  function onCapture(cap) {
    if (!cap.completion) return false;
    // Debug: keep raw completion bodies so we can author/verify parsers (esp.
    // Grok, whose successful stream format we haven't seen yet).
    debugRaw.push({ provider: cap.provider, url: cap.url, contentType: cap.contentType, answerLen: cap.answerLen, error: cap.error, sample: cap.sample, raw: cap.raw, ts: cap.ts });
    while (debugRaw.length > 60) debugRaw.shift();

    if (!RUN || RUN.status !== "running") return false;
    const pid = RUN.tabToProvider[cap.tabId];
    if (!pid) return false;
    const prov = RUN.providers[pid];
    if (!prov || !prov.inflight) return false;
    const hasAnswer = !!(cap.answer && cap.answerLen);
    const isError = !!cap.error;
    if (!hasAnswer && !isError) return true; // prep/keepalive on the same endpoint — wait
    const inf = prov.inflight;
    const latency = Date.parse(cap.ts) - inf.submittedAt;
    if (isError && /capacity|high demand|heavy usage|rate.?limit|again later|overload/i.test(cap.error)) {
      const key = pid + "|" + inf.item.itemKey;
      RUN.capRetries[key] = (RUN.capRetries[key] || 0) + 1;
      prov.inflight = null;
      if (RUN.capRetries[key] >= 4) {
        // Give up and SURFACE it (so it shows as BLOCKED, not a silent 0).
        saveRecord(pid, inf.item, { status: "error", error: cap.error, latencyMs: latency, startMs: inf.submittedAt, endMs: Date.parse(cap.ts), url: cap.url })
          .then(() => scheduleTick());
        log.warn(`[${pid}] capacity-blocked after ${RUN.capRetries[key]} tries; recorded BLOCKED`);
      } else {
        RUN.retryAt[key] = Date.now() + 60000;
        log.warn(`[${pid}] capacity; retry ${inf.item.itemKey} in 60s (try ${RUN.capRetries[key]})`);
        scheduleTick();
      }
      return true;
    }
    saveRecord(pid, inf.item, { answer: cap.answer, status: isError ? "error" : "ok", error: cap.error, latencyMs: latency, startMs: inf.submittedAt, endMs: Date.parse(cap.ts), url: cap.url, model: cap.model })
      .then(() => { log.info(`[${pid}] recorded ${inf.item.itemKey} ${isError ? "ERR" : "ok"} ${cap.answerLen}c ${latency}ms`); scheduleTick(); });
    prov.inflight = null;
    return true;
  }

  async function waitForReady(tabId, timeoutMs = 25000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      try { const r = await ext.tabs.sendMessage(tabId, { type: Probe.MSG.PING }); if (r && r.ok && r.ready) return true; } catch (_) {}
      await Probe.cadence.sleep(600);
    }
    return false;
  }

  function bumpAttempt(pid, item, err) {
    const key = pid + "|" + item.itemKey;
    // Connection errors = the tab was mid-reload (e.g. fresh-chat navigation).
    // Transient: retry soon without burning the permanent attempt budget.
    if (/establish connection|receiving end|message port|not ready/i.test(err || "")) {
      RUN.connRetries[key] = (RUN.connRetries[key] || 0) + 1;
      if (RUN.connRetries[key] < 8) { RUN.retryAt[key] = Date.now() + 3000; return; }
    }
    RUN.attempts[key] = (RUN.attempts[key] || 0) + 1;
    log.warn(`[${pid}] ${item.itemKey} failed (attempt ${RUN.attempts[key]}): ${err}`);
    if (RUN.attempts[key] >= 3) saveRecord(pid, item, { status: "error", error: "submit failed: " + err });
    else RUN.retryAt[key] = Date.now() + 8000;
  }

  async function submitItem(pid, item) {
    const prov = RUN.providers[pid];
    const tabId = await ensureTab(pid);
    const priv = !!(RUN.cfg.config && RUN.cfg.config.private);
    const { promptSent } = compose(item);

    // 1) Start a fresh/private chat (may navigate; response may be lost on reload).
    await focusTab(tabId);
    try { await ext.tabs.sendMessage(tabId, { type: Probe.MSG.NEW_CHAT, private: priv }); } catch (_) { /* navigated */ }

    // 2) Wait for the (possibly reloaded) content script + composer to be ready.
    if (!(await waitForReady(tabId))) { bumpAttempt(pid, item, "not ready (login/page/loading)"); return; }

    // 3) Type + submit (needs focus). Capture happens afterwards, focus-independent.
    await focusTab(tabId);
    let resp;
    try { resp = await ext.tabs.sendMessage(tabId, { type: Probe.MSG.SUBMIT, prompt: promptSent }); }
    catch (e) { resp = { ok: false, error: String(e?.message || e) }; }
    if (!resp || !resp.ok) { bumpAttempt(pid, item, resp && resp.error); return; }

    prov.inflight = { item, submittedAt: resp.submittedAt || Date.now(), tabId };
    log.info(`[${pid}] submitted ${item.itemKey} (vis=${resp.visibility})`);
  }

  async function tick() {
    if (!RUN || RUN.status !== "running" || ticking) return;
    ticking = true;
    try {
      // Inflight timeout: if a submitted item's answer never gets captured (wrong
      // endpoint/parser), don't get stuck — record an error and move on.
      const timeoutMs = (RUN.cfg.config && RUN.cfg.config.responseTimeoutMs) || 180000;
      for (const pid of RUN.cfg.providers) {
        const prov = RUN.providers[pid];
        if (prov.inflight && Date.now() - prov.inflight.submittedAt > timeoutMs) {
          await saveRecord(pid, prov.inflight.item, { status: "error", error: "no response captured within timeout (endpoint/parser?)", startMs: prov.inflight.submittedAt, endMs: Date.now() });
          log.warn(`[${pid}] inflight timeout on ${prov.inflight.item.itemKey}; recorded error & moving on`);
          prov.inflight = null;
        }
      }
      // ONE provider in flight at a time, and we keep its tab focused until its
      // response is fully captured — several providers (ChatGPT, Gemini) abort
      // their own stream when their tab is backgrounded, which truncated answers.
      // Trades cross-provider parallelism for complete, reliable captures.
      const anyInflight = RUN.cfg.providers.some((pid) => RUN.providers[pid].inflight);
      if (!anyInflight && RUN.status === "running") {
        // Pick the eligible provider with the fewest completed (balanced rotation).
        let pick = null, pickItem = null, fewest = Infinity;
        for (const pid of RUN.cfg.providers) {
          const done = await doneSetFor(pid);
          const item = nextItem(pid, done);
          if (item && done.size < fewest) { fewest = done.size; pick = pid; pickItem = item; }
        }
        if (pick) await submitItem(pick, pickItem);
      }
      let allDone = true;
      for (const pid of RUN.cfg.providers) {
        const done = await doneSetFor(pid);
        if (RUN.providers[pid].inflight || done.size < RUN.providers[pid].items.length) { allDone = false; break; }
      }
      if (allDone) { RUN.status = "done"; stopTick(); log.info("run complete"); }
    } catch (e) {
      log.error("tick", e?.message || e);
    } finally {
      ticking = false;
    }
  }
  const scheduleTick = () => setTimeout(() => tick().catch(() => {}), 250);
  function startTick() { stopTick(); tickTimer = setInterval(() => tick().catch(() => {}), 4000); }
  function stopTick() { if (tickTimer) clearInterval(tickTimer); tickTimer = null; }

  async function start(runConfig, windowId) {
    const runId = `run_${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const cfg = { ...runConfig, runId };
    const items = Probe.runPlan.expand(cfg);
    RUN = { runId, cfg, windowId, status: "running", startedAt: Date.now(), providers: {}, tabToProvider: {}, retryAt: {}, attempts: {}, connRetries: {}, capRetries: {} };
    for (const pid of cfg.providers) RUN.providers[pid] = { items: items.map((x) => ({ ...x })), tabId: null, inflight: null };
    await Probe.storage.set("runConfig", cfg);
    for (const pid of cfg.providers) await ensureTab(pid);
    // DeepSeek deletes all chats before EVERY question (done inside its
    // startChat, since it has no private mode) — no once-per-run purge here.
    startTick(); scheduleTick();
    log.info(`run ${runId}: ${cfg.providers.join(",")} x ${items.length} items each, private=${!!(cfg.config && cfg.config.private)}`);
    return { runId, perProvider: items.length };
  }

  const pause = () => { if (RUN) { RUN.status = "paused"; stopTick(); } };
  const resume = () => { if (RUN) { RUN.status = "running"; startTick(); scheduleTick(); } };
  const stop = () => { if (RUN) { RUN.status = "stopped"; stopTick(); } };

  async function overview() {
    const cfg = RUN ? RUN.cfg : await Probe.storage.get("runConfig", null);
    const all = await ext.storage.local.get(null);
    const recs = Object.entries(all).filter(([k]) => k.startsWith(REC_PREFIX)).map(([, v]) => v);
    const runId = cfg && cfg.runId;
    const total = cfg ? Probe.runPlan.perProviderCount(cfg) : 0;
    const perProvider = {};
    for (const pid of (cfg && cfg.providers) || []) {
      const rs = recs.filter((r) => r.provider === pid && (!runId || r.runId === runId));
      perProvider[pid] = { done: rs.length, total, ok: rs.filter((r) => r.status === "ok").length, error: rs.filter((r) => r.status === "error").length, inflight: !!(RUN && RUN.providers[pid] && RUN.providers[pid].inflight) };
    }
    return { status: RUN ? RUN.status : "idle", runConfig: cfg, perProvider, recordCount: recs.length };
  }

  async function exportRun() {
    const all = await ext.storage.local.get(null);
    const recs = Object.entries(all).filter(([k]) => k.startsWith(REC_PREFIX)).map(([, v]) => v)
      .sort((a, b) => (a.timestampEnd || "").localeCompare(b.timestampEnd || ""));
    const cfg = await Probe.storage.get("runConfig", null);
    const summary = Probe.summary.build(recs, cfg);
    const runId = (cfg && cfg.runId) || "run";
    const files = [
      [`chat-probe/${runId}.jsonl`, recs.map((r) => JSON.stringify(r)).join("\n"), "application/x-ndjson"],
      [`chat-probe/${runId}.summary.json`, JSON.stringify(summary, null, 2), "application/json"],
      [`chat-probe/${runId}.summary.txt`, Probe.summary.formatText(summary), "text/plain"],
      [`chat-probe/${runId}.raw-completions.json`, JSON.stringify(debugRaw, null, 2), "application/json"],
    ];
    for (const [name, content, type] of files) {
      const url = URL.createObjectURL(new Blob([content], { type }));
      await ext.downloads.download({ url, filename: name, saveAs: false });
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
    return { count: recs.length, summaryText: Probe.summary.formatText(summary) };
  }

  async function clear() {
    stop();
    await Probe.storage.removeByPrefix(REC_PREFIX);
    await ext.storage.local.remove("runConfig");
    RUN = null;
  }

  Probe.runner = { start, pause, resume, stop, onCapture, overview, exportRun, clear };
})();
