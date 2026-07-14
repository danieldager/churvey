// The conductor (runs in the persistent background page = single source of truth).
// Model: focus a provider tab only long enough to SUBMIT, then move on; the
// answer streams in the background and is captured at the network layer and paired
// by tabId. Each provider runs one question at a time; providers run concurrently.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("runner");
  const REC_PREFIX = "rec::";
  const RUNS_PREFIX = "runs::"; // registry: one stored runConfig per runId (run history)
  const recKey = (runId, prov, itemKey) => `${REC_PREFIX}${runId}::${prov}::${itemKey}`;

  let RUN = null;
  let tickTimer = null;
  let ticking = false;
  const debugRaw = []; // raw completion bodies for parser authoring (export debug)

  // Citation harvesting. Source URLs live in the raw stream for most providers; for
  // providers whose UI hides them behind chips (Gemini) we DOM-scrape the tab.
  const SCRAPE_PROVIDERS = new Set(["gemini"]);
  const ASSET_RE = /gstatic\.com|googleusercontent|googleapis\.com|schema\.org|w3\.org|images\.openai\.com|oaistatic|oaiusercontent|static-rsc|\/s2\/favicons|deepseek\.com\/site-icons|sentry|fonts\.|\.(?:js|css|woff2?|png|jpe?g|svg|webp|gif|ico)(?:$|\?)/i;
  function harvestUrls(raw) {
    if (!raw) return [];
    const out = new Set();
    for (const m of raw.matchAll(/https?:\/\/[^\s"'\\)<>]+/g)) {
      const u = m[0].replace(/[.,;'")]+$/, "");
      if (u.length > 400 || ASSET_RE.test(u)) continue;
      out.add(u); if (out.size >= 60) break;
    }
    return [...out];
  }
  function dedupeCites(list) {
    const seen = new Set(), out = [];
    for (const c of list) { if (!c || !c.url || seen.has(c.url)) continue; seen.add(c.url); out.push(c); }
    return out.slice(0, 80);
  }
  async function scrapeCitations(tabId) {
    try {
      const r = await Promise.race([
        ext.tabs.sendMessage(tabId, { type: Probe.MSG.SCRAPE_SOURCES }),
        new Promise((res) => setTimeout(() => res(null), 6000)),
      ]);
      return r && r.ok && Array.isArray(r.citations) ? r.citations : [];
    } catch (_) { return []; }
  }

  // Trim ONLY known third-party analytics cookies mid-run to slow header bloat.
  // Deliberately conservative: never touches OpenAI (oai-*), Cloudflare, or auth
  // cookies — deleting ChatGPT's own cookies (e.g. oai-did) every request can make
  // it treat each turn as a new device and abort the answer stream.
  const COOKIE_DROP_RE = /^(_ga|_gid|_gat|_gac|_gcl|__utm|ajs_|_hj|intercom|_dd_?|_uet|_fbp|_scid|_rdt|_pin_|_clck|_clsk|mp_|amplitude|_mkto|_vwo|_pk_)/i;
  async function trimCookies(domains) {
    let removed = 0;
    for (const domain of domains) {
      let all = [];
      try { all = await ext.cookies.getAll({ domain }); } catch (_) {}
      for (const c of all) {
        if (!COOKIE_DROP_RE.test(c.name)) continue; // remove ONLY known analytics
        const host = c.domain.replace(/^\./, "");
        try { await ext.cookies.remove({ url: `http${c.secure ? "s" : ""}://${host}${c.path || "/"}`, name: c.name, storeId: c.storeId }); removed++; } catch (_) {}
      }
    }
    if (removed) log.info(`trimmed ${removed} analytics cookies (${domains.join(",")})`);
    return removed;
  }

  const compose = (item) => Probe.prompt.compose({ persona: item.persona || null, question: { id: item.questionId, text: item.questionText } });

  // One WINDOW per provider. A tab that isn't the active tab of its window is
  // `hidden` and several providers (ChatGPT, Gemini) abort their stream on that —
  // but the active tab of an UNFOCUSED window stays `visible`. So each provider
  // gets its own window and all streams flow in parallel; only the submit itself
  // (typing needs OS focus) is serialized.
  async function ensureTab(pid) {
    const prov = RUN.providers[pid];
    if (prov.tabId) { try { await ext.tabs.get(prov.tabId); return prov.tabId; } catch (_) { prov.tabId = null; } }
    const meta = Probe.providers.byId(pid);
    const existing = await ext.tabs.query({ url: meta.matchPattern });
    if (existing.length) {
      const tab = existing[0];
      const siblings = await ext.tabs.query({ windowId: tab.windowId });
      if (siblings.length > 1) await ext.windows.create({ tabId: tab.id }); // move into its own window
      prov.tabId = tab.id;
    } else {
      const w = await ext.windows.create({ url: meta.homeUrl });
      prov.tabId = (w.tabs && w.tabs[0] && w.tabs[0].id) || (await ext.tabs.query({ windowId: w.id }))[0].id;
      await Probe.cadence.sleep(2500);
    }
    RUN.tabToProvider[prov.tabId] = pid;
    return prov.tabId;
  }

  async function focusTab(tabId) {
    try { await ext.tabs.update(tabId, { active: true }); const t = await ext.tabs.get(tabId); await ext.windows.update(t.windowId, { focused: true }); } catch (_) {}
    await Probe.cadence.sleep(300);
  }

  // COMPLETION = an OK record. Error records do NOT count as done — the item stays
  // in the queue and is re-asked (with backoff) until it succeeds or the run is
  // stopped. This is the "no silent gaps" guarantee: a failed question can never
  // be skipped, only retried or explicitly abandoned by the user.
  async function doneSetFor(pid) {
    const all = await ext.storage.local.get(null);
    const pre = `${REC_PREFIX}${RUN.runId}::${pid}::`;
    const done = new Set();
    for (const [k, v] of Object.entries(all)) {
      if (k.startsWith(pre) && v && v.status === "ok") done.add(k.slice(pre.length));
    }
    return done;
  }

  // One failure path for everything (stall, capacity, submit error): count the
  // failure, save/refresh the error record (so an export mid-run shows it), and
  // schedule the re-ask with exponential backoff, 15s -> 5min cap. Never gives up.
  function failBackoff(pid, item, err, { minDelay = 0, record = true } = {}) {
    const key = pid + "|" + item.itemKey;
    RUN.fails[key] = (RUN.fails[key] || 0) + 1;
    const delay = Math.max(minDelay, Math.min(300000, 15000 * Math.pow(2, RUN.fails[key] - 1)));
    RUN.retryAt[key] = Date.now() + delay;
    log.warn(`[${pid}] ${item.itemKey} failed (attempt ${RUN.fails[key]}): ${err} — re-asking in ${Math.round(delay / 1000)}s`);
    if (record) saveRecord(pid, item, { status: "error", error: `${err} (attempt ${RUN.fails[key]}, retrying)` }).catch(() => {});
    scheduleTick();
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
    // Parser-drift tripwire: a real answer never starts mid-sentence. This is how
    // the ChatGPT delta_encoding bug (missing heads) would have been caught live.
    if (f.status === "ok" && /^[\sa-z,;:)\]]/.test(f.answer || "")) {
      log.warn(`[${pid}] ${item.itemKey}: answer starts mid-sentence — possible parser drift, check raw export`);
    }
    const rec = Probe.record.build({
      runId: RUN.runId, questionId: item.questionId, questionText: item.questionText,
      promptSent, personaId, repIndex: item.repIndex, itemKey: item.itemKey, provider: pid,
      modelLabel: f.model || null, responseText: f.answer || "", status: f.status, errorMessage: f.error || null,
      latencyMs: f.latencyMs ?? null, timestampStartMs: f.startMs ?? null, timestampEndMs: f.endMs ?? null,
      private: RUN.cfg.config && RUN.cfg.config.private, captureUrl: f.url || null, citations: f.citations || [],
    });
    await ext.storage.local.set({ [recKey(RUN.runId, pid, item.itemKey)]: rec });
  }

  // Pairing: called for every completion capture.
  function onCapture(cap) {
    if (!cap.completion) return false;
    // Debug: keep raw completion bodies so we can author/verify parsers (esp.
    // Grok, whose successful stream format we haven't seen yet).
    debugRaw.push({ provider: cap.provider, url: cap.url, contentType: cap.contentType, answerLen: cap.answerLen, error: cap.error, sample: cap.sample, raw: cap.raw, ts: cap.ts });
    // Ring by count AND total bytes: 400 entries ≈ a full run incl. retries, and
    // the byte budget keeps memory sane now that per-capture raws can be ~1MB
    // (Grok/Gemini streams overflowed the old 300KB slice, holing the safety net).
    let rawBytes = debugRaw.reduce((n, e) => n + ((e.raw && e.raw.length) || 0), 0);
    while (debugRaw.length > 400 || (rawBytes > 120e6 && debugRaw.length > 40)) {
      rawBytes -= ((debugRaw[0].raw && debugRaw[0].raw.length) || 0);
      debugRaw.shift();
    }

    if (!RUN || RUN.status !== "running") return false;
    const pid = RUN.tabToProvider[cap.tabId];
    if (!pid) return false;
    const prov = RUN.providers[pid];
    if (!prov || !prov.inflight) return false;
    const hasAnswer = !!(cap.answer && cap.answerLen);
    const isError = !!cap.error;
    if (!hasAnswer && !isError) { if (prov.inflight) prov.inflight.emptyAt = Date.now(); return true; } // empty response = stream aborted after preamble; retry soon (see tick)
    const inf = prov.inflight;
    const latency = Date.parse(cap.ts) - inf.submittedAt;
    if (isError && /capacity|high demand|heavy usage|rate.?limit|too many request|again later|overload|429/i.test(cap.error)) {
      // Capacity/rate-limit: back off at least 60s so we don't hammer a limited
      // provider, but keep the item queued — it retries until it lands.
      const item = inf.item;
      prov.inflight = null;
      failBackoff(pid, item, cap.error, { minDelay: 60000 });
      return true;
    }
    // Harvest citations before recording: URLs from the raw stream (all providers)
    // + DOM-scraped source links for providers that hide them (Gemini). Kept inside
    // inflight so the conductor holds the tab until the scrape finishes.
    (async () => {
      let citations = [];
      if (!isError) {
        try {
          const stream = harvestUrls(cap.raw).map((url) => ({ url, title: null, via: "stream" }));
          let dom = [];
          if (SCRAPE_PROVIDERS.has(pid)) dom = (await scrapeCitations(inf.tabId)).map((c) => ({ url: c.url, title: c.title || null, via: "dom" }));
          citations = dedupeCites([...dom, ...stream]);
        } catch (e) { log.warn(`[${pid}] citation harvest failed: ${e?.message || e}`); }
      }
      await saveRecord(pid, inf.item, { answer: cap.answer, status: isError ? "error" : "ok", error: cap.error, latencyMs: latency, startMs: inf.submittedAt, endMs: Date.parse(cap.ts), url: cap.url, model: cap.model, citations });
      log.info(`[${pid}] recorded ${inf.item.itemKey} ${isError ? "ERR" : "ok"} ${cap.answerLen}c ${citations.length}cites ${latency}ms`);
      // Keep ChatGPT's Cookie header from growing into a 431 over a long run.
      if (pid === "chatgpt" && !isError) trimCookies(["chatgpt.com", "openai.com"]).catch(() => {});
      prov.inflight = null;
      // An error record is not done — schedule its re-ask (record already saved).
      if (isError) failBackoff(pid, inf.item, cap.error, { record: false });
      scheduleTick();
    })();
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
    // Transient: retry soon without burning the backoff budget.
    if (/establish connection|receiving end|message port|not ready/i.test(err || "")) {
      RUN.connRetries[key] = (RUN.connRetries[key] || 0) + 1;
      if (RUN.connRetries[key] < 8) { RUN.retryAt[key] = Date.now() + 3000; return; }
    }
    failBackoff(pid, item, "submit failed: " + err);
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
      // Self-heal a stalled item instead of freezing the serial queue: an empty
      // response means the stream aborted after its preamble; full silence means
      // submit/capture never landed (hard timeout). Either way the item goes back
      // in the queue — first stall re-asks fast (3s), repeats back off via
      // failBackoff. The queue is never blocked and the item is never abandoned.
      const timeoutMs = (RUN.cfg.config && RUN.cfg.config.responseTimeoutMs) || 90000;
      for (const pid of RUN.cfg.providers) {
        const prov = RUN.providers[pid];
        const inf = prov.inflight;
        if (!inf) continue;
        const aborted = inf.emptyAt && Date.now() - inf.emptyAt > 20000;
        const hardTimeout = Date.now() - inf.submittedAt > timeoutMs;
        if (!aborted && !hardTimeout) continue;
        const key = pid + "|" + inf.item.itemKey;
        prov.inflight = null;
        const firstStall = !RUN.fails[key];
        failBackoff(pid, inf.item, aborted ? "stream aborted after preamble" : "no response (timeout)");
        if (firstStall && aborted) RUN.retryAt[key] = Date.now() + 3000; // fast first re-ask
      }
      // Providers stream in PARALLEL, each in its own window (see ensureTab).
      // Only the submit is serialized — typing needs OS focus — so we start at
      // most one submit per tick: submits stagger a few seconds apart, streams
      // overlap. Paused providers (account swap etc.) are skipped entirely.
      if (RUN.status === "running") {
        // Pick the eligible provider with the fewest completed (balanced rotation).
        let pick = null, pickItem = null, fewest = Infinity;
        for (const pid of RUN.cfg.providers) {
          const prov = RUN.providers[pid];
          if (prov.paused || prov.inflight) continue;
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

  async function boot(cfg, _windowId, label) { // windowId unused since one-window-per-provider
    const items = Probe.runPlan.expand(cfg);
    RUN = { runId: cfg.runId, cfg, status: "running", startedAt: Date.now(), providers: {}, tabToProvider: {}, retryAt: {}, fails: {}, connRetries: {} };
    for (const pid of cfg.providers) RUN.providers[pid] = { items: items.map((x) => ({ ...x })), tabId: null, inflight: null, paused: false };
    for (const pid of cfg.providers) await ensureTab(pid);
    // DeepSeek deletes all chats before EVERY question (done inside its
    // startChat, since it has no private mode) — no once-per-run purge here.
    startTick(); scheduleTick();
    log.info(`${label} ${cfg.runId}: ${cfg.providers.join(",")} x ${items.length} items each, private=${!!(cfg.config && cfg.config.private)}`);
    return { runId: cfg.runId, perProvider: items.length };
  }

  async function start(runConfig, windowId) {
    const runId = `run_${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const cfg = { ...runConfig, runId };
    await Probe.storage.set("runConfig", cfg);
    await ext.storage.local.set({ [RUNS_PREFIX + runId]: cfg }); // run history
    return boot(cfg, windowId, "run");
  }

  // Run history: every started/imported run keeps its config; progress comes from
  // whatever records exist. Selecting a run makes it active so Resume continues it.
  async function listRuns() {
    const all = await ext.storage.local.get(null);
    const active = await Probe.storage.get("runConfig", null);
    const cfgs = {};
    for (const [k, v] of Object.entries(all)) if (k.startsWith(RUNS_PREFIX) && v && v.runId) cfgs[v.runId] = v;
    if (active && active.runId && !cfgs[active.runId]) cfgs[active.runId] = active; // legacy
    const runs = [];
    for (const cfg of Object.values(cfgs)) {
      const expected = Probe.runPlan.perProviderCount(cfg);
      const per = {};
      for (const pid of cfg.providers) {
        const pre = `${REC_PREFIX}${cfg.runId}::${pid}::`;
        let ok = 0;
        for (const [k, v] of Object.entries(all)) if (k.startsWith(pre) && v && v.status === "ok") ok++;
        per[pid] = ok;
      }
      runs.push({ runId: cfg.runId, providers: cfg.providers, repetitions: cfg.repetitions,
                  questions: (cfg.questions || []).length, expected, perProviderOk: per,
                  ok: Object.values(per).reduce((a, b) => a + b, 0), total: expected * cfg.providers.length,
                  active: !!(active && active.runId === cfg.runId),
                  running: !!(RUN && RUN.runId === cfg.runId && RUN.status === "running") });
    }
    runs.sort((a, b) => b.runId.localeCompare(a.runId));
    return runs;
  }

  async function selectRun(runId) {
    if (RUN && RUN.status === "running") throw new Error("stop the current run first");
    const all = await ext.storage.local.get(RUNS_PREFIX + runId);
    const cfg = all[RUNS_PREFIX + runId];
    if (!cfg) throw new Error("unknown run " + runId);
    await Probe.storage.set("runConfig", cfg);
    RUN = null;
    return { runConfig: cfg };
  }

  // Resume the stored run under its ORIGINAL runId: items that already have an OK
  // record are skipped, everything missing is (re)asked. This is the gap-fill path
  // after a stop, a browser restart, or an add-on reload.
  async function resumeFromStorage(windowId) {
    const cfg = await Probe.storage.get("runConfig", null);
    if (!cfg || !cfg.runId) throw new Error("no stored run to resume");
    return boot(cfg, windowId, "resume");
  }

  const pause = () => { if (RUN) { RUN.status = "paused"; stopTick(); } };
  const resume = () => { if (RUN) { RUN.status = "running"; startTick(); scheduleTick(); } };
  const stop = () => { if (RUN) { RUN.status = "stopped"; stopTick(); } };

  // Per-provider pause: freeze ONE provider (e.g. to swap a rate-limited grok
  // account) while the others keep running. An inflight answer still lands; the
  // provider just gets no new submits. Resuming clears its backoff/fail counters
  // so the fresh account is asked immediately instead of waiting out a 5min cap.
  const pauseProvider = (pid) => { if (RUN && RUN.providers[pid]) { RUN.providers[pid].paused = true; log.info(`[${pid}] paused by user`); } };
  function resumeProvider(pid) {
    if (!RUN || !RUN.providers[pid]) return;
    RUN.providers[pid].paused = false;
    for (const k of Object.keys(RUN.retryAt)) if (k.startsWith(pid + "|")) delete RUN.retryAt[k];
    for (const k of Object.keys(RUN.fails)) if (k.startsWith(pid + "|")) delete RUN.fails[k];
    log.info(`[${pid}] resumed by user (backoff cleared)`);
    scheduleTick();
  }

  async function overview() {
    const cfg = RUN ? RUN.cfg : await Probe.storage.get("runConfig", null);
    const all = await ext.storage.local.get(null);
    const recs = Object.entries(all).filter(([k]) => k.startsWith(REC_PREFIX)).map(([, v]) => v);
    const runId = cfg && cfg.runId;
    const total = cfg ? Probe.runPlan.perProviderCount(cfg) : 0;
    const plan = cfg ? Probe.runPlan.expand(cfg) : [];
    const now = Date.now();
    const perProvider = {};
    for (const pid of (cfg && cfg.providers) || []) {
      const rs = recs.filter((r) => r.provider === pid && (!runId || r.runId === runId));
      const byKey = {};
      for (const r of rs) byKey[r.itemKey] = r;
      const inflightKey = RUN && RUN.providers[pid] && RUN.providers[pid].inflight
        ? RUN.providers[pid].inflight.item.itemKey : null;
      // Per-item state for the popup grid: exactly what's done / missing / retrying.
      const items = plan.map((it) => {
        const rec = byKey[it.itemKey];
        const key = pid + "|" + it.itemKey;
        const fails = (RUN && RUN.fails[key]) || 0;
        const retryIn = RUN && RUN.retryAt[key] > now ? Math.round((RUN.retryAt[key] - now) / 1000) : 0;
        let s = "idle";
        if (rec && rec.status === "ok") s = "ok";
        else if (it.itemKey === inflightKey) s = "run";
        else if ((rec && rec.status === "error") || fails) s = "err";
        return { k: it.itemKey, q: it.questionId, r: it.repIndex, s, n: fails, in: retryIn,
                 e: rec && rec.status === "error" ? (rec.errorMessage || "").slice(0, 120) : null };
      });
      const ok = items.filter((x) => x.s === "ok").length;
      perProvider[pid] = {
        total, ok,
        error: items.filter((x) => x.s === "err").length,
        missing: items.filter((x) => x.s !== "ok").map((x) => x.k),
        inflight: !!inflightKey, items,
        paused: !!(RUN && RUN.providers[pid] && RUN.providers[pid].paused),
      };
    }
    return { status: RUN ? RUN.status : "idle", runConfig: cfg, perProvider, recordCount: recs.length,
             canResume: !RUN && !!(cfg && cfg.runId) };
  }

  async function exportRun() {
    const all = await ext.storage.local.get(null);
    const recs = Object.entries(all).filter(([k]) => k.startsWith(REC_PREFIX)).map(([, v]) => v)
      .sort((a, b) => (a.timestampEnd || "").localeCompare(b.timestampEnd || ""));
    const cfg = await Probe.storage.get("runConfig", null);
    const summary = Probe.summary.build(recs, cfg);
    const runId = (cfg && cfg.runId) || "run";
    // Self-contained run manifest: config (objectives) + records (progress).
    // Drop this file back into the popup's Import to restore the run anywhere —
    // the tool then knows the providers, questions, reps, and exactly what's
    // missing, and "Resume missing" fills only the gaps.
    const manifest = { format: "chat-probe-run", version: 1, exportedAt: new Date().toISOString(),
                       runConfig: cfg, records: recs.filter((r) => !cfg || r.runId === cfg.runId) };
    const files = [
      [`chat-probe/${runId}.run.json`, JSON.stringify(manifest), "application/json"],
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
    await Probe.storage.removeByPrefix(RUNS_PREFIX);
    await ext.storage.local.remove("runConfig");
    RUN = null;
  }

  // Import a .run.json manifest: restores the run config + all its records into
  // storage, so the grid shows exact progress and Resume missing fills the gaps.
  async function importRun(manifest) {
    if (!manifest || manifest.format !== "chat-probe-run" || !manifest.runConfig || !Array.isArray(manifest.records)) {
      throw new Error("not a chat-probe .run.json manifest");
    }
    if (RUN && RUN.status === "running") throw new Error("stop the current run before importing");
    const cfg = manifest.runConfig;
    if (!cfg.runId || !Array.isArray(cfg.providers) || !Array.isArray(cfg.questions)) throw new Error("manifest runConfig incomplete");
    await Probe.storage.set("runConfig", cfg);
    await ext.storage.local.set({ [RUNS_PREFIX + cfg.runId]: cfg }); // run history
    const batch = {};
    for (const r of manifest.records) {
      if (r && r.runId === cfg.runId && r.provider && r.itemKey) batch[recKey(r.runId, r.provider, r.itemKey)] = r;
    }
    await ext.storage.local.set(batch);
    RUN = null; // idle; the popup shows the grid + Resume missing via overview()
    log.info(`imported run ${cfg.runId}: ${Object.keys(batch).length} records`);
    return { runId: cfg.runId, records: Object.keys(batch).length, runConfig: cfg };
  }

  Probe.runner = { start, pause, resume, resumeFromStorage, stop, pauseProvider, resumeProvider, onCapture, overview, exportRun, importRun, listRuns, selectRun, clear };
})();
