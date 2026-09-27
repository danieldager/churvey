// Orchestration engine (runs in each provider tab). Work is selected from a
// CLAIM-based queue so multiple tabs of the same provider divide the work without
// duplicating: records use deterministic per-item keys (so a duplicate just
// overwrites), and a best-effort claim avoids two tabs picking the same item.
//
// The owner id is STABLE per tab (sessionStorage) so it survives reloads — a
// reload-based fresh chat (or a crash) resumes the same item instead of skipping.
//
// When auto-cycling, a tab only acts while focused (so we never type into a
// throttled, hidden tab) and yields to the next tab after each item.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("orchestrator");

  const MAX_ATTEMPTS = 3;
  const CLAIM_TTL = 8 * 60 * 1000;

  let mem = { provider: null, adapter: null, paused: false, stopped: false, running: false, ownerId: null };
  let heartbeatTimer = null;
  const attemptsByKey = {};

  const now = () => Date.now();

  function ownerId() {
    if (mem.ownerId) return mem.ownerId;
    try {
      let id = sessionStorage.getItem("probeOwner");
      if (!id) {
        id = "own-" + Math.random().toString(36).slice(2) + "-" + Date.now();
        sessionStorage.setItem("probeOwner", id);
      }
      mem.ownerId = id;
    } catch (_) {
      mem.ownerId = "own-" + Math.random().toString(36).slice(2);
    }
    return mem.ownerId;
  }

  async function persist(provider, patch) {
    const ps = (await Probe.storage.getProvState(provider)) || { provider };
    Object.assign(ps, patch, { updatedAt: now() });
    await Probe.storage.setProvState(provider, ps);
    notify(provider, ps);
    return ps;
  }
  function notify(provider, ps) {
    try {
      chrome.runtime.sendMessage({ type: Probe.MSG.STATUS, provider, provState: ps });
    } catch (_) {}
  }

  function startHeartbeat(provider) {
    stopHeartbeat();
    heartbeatTimer = setInterval(() => {
      Probe.storage.getProvState(provider).then((ps) => {
        if (!ps) return;
        ps.heartbeatAt = now();
        Probe.storage.setProvState(provider, ps).catch(() => {});
      });
    }, 15000);
  }
  function stopHeartbeat() {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }

  class ControlSignal extends Error {}
  class CapacitySignal extends Error {}
  function checkControl() {
    if (mem.stopped) throw new ControlSignal("stopped");
    if (mem.paused) throw new ControlSignal("paused");
  }
  async function controlledSleep(ms) {
    const step = 250;
    let waited = 0;
    while (waited < ms) {
      checkControl();
      await Probe.cadence.sleep(Math.min(step, ms - waited));
      waited += step;
    }
  }

  function waitUntilVisible(maxMs = 120000) {
    if (document.visibilityState === "visible") return Promise.resolve();
    return new Promise((resolve) => {
      let to = null;
      const done = () => {
        document.removeEventListener("visibilitychange", onVis);
        if (to) clearTimeout(to);
        resolve();
      };
      const onVis = () => document.visibilityState === "visible" && done();
      document.addEventListener("visibilitychange", onVis);
      to = setTimeout(done, maxMs);
    });
  }
  const autoCycleOn = () => Probe.storage.get("autoCycle", true);
  function yieldNext() {
    try {
      chrome.runtime.sendMessage({ type: Probe.MSG.YIELD });
    } catch (_) {}
  }

  async function capacityGate(provider) {
    let tries = 0;
    while (Probe.adapterBase.isOverloaded()) {
      checkControl();
      tries++;
      await persist(provider, { currentState: "WAITING_CAPACITY" });
      const wait = Math.min(60000, 15000 + tries * 5000);
      log.warn(`[${provider}] high demand; waiting ${Math.round(wait / 1000)}s (try ${tries})`);
      await controlledSleep(wait);
      if (tries % 3 === 0) {
        log.warn(`[${provider}] refreshing to clear capacity block`);
        location.reload();
        await controlledSleep(60000);
        return;
      }
    }
  }

  // --- claim-based item selection ---
  async function doneItemKeys(runId, provider) {
    return Probe.storage.getProviderRecordItemKeys(runId, provider);
  }
  async function nextClaimable(runId, provider, queue) {
    const done = await doneItemKeys(runId, provider);
    const claims = await Probe.storage.getProviderClaims(runId, provider);
    const t = now();
    const me = ownerId();
    for (let idx = 0; idx < queue.length; idx++) {
      if (done.has(queue[idx].itemKey)) continue;
      const c = claims[String(idx)];
      if (c && c.owner !== me && t - c.at < CLAIM_TTL) continue; // another tab is on it
      return idx;
    }
    return -1;
  }

  function compose(item) {
    return Probe.prompt.compose({
      persona: item.persona || null,
      question: { id: item.questionId, text: item.questionText },
    });
  }

  async function processItem(adapter, provider, runId, item, cfg) {
    if (await Probe.storage.hasRecordForItem(runId, provider, item.itemKey)) return;

    const { promptSent, personaId } = compose(item);

    await capacityGate(provider);
    Probe.adapterBase.dismissConsent();
    Probe.adapterBase.dismissNotice();

    await persist(provider, { currentState: "STARTING_CHAT" });
    await adapter.startFreshChat({ private: !!cfg.private });
    checkControl();

    await persist(provider, { currentState: "TYPING" });
    const input = await adapter.locateInput();
    await adapter.typeQuestion(input, promptSent);
    checkControl();

    await persist(provider, { currentState: "SUBMITTING" });
    const tStart = now();
    await adapter.submit();
    checkControl();
    Probe.adapterBase.dismissNotice();

    await persist(provider, { currentState: "AWAITING_RESPONSE" });
    let { text, status, modelLabel } = await adapter.detectResponseComplete({
      timeoutMs: cfg.responseTimeoutMs,
    });
    const tEnd = now();

    if (Probe.adapterBase.isOverloaded()) throw new CapacitySignal("provider busy after submit");

    const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
    let errorMessage = null;
    let debug = null;
    const echo = norm(text) && (norm(text) === norm(item.questionText) || norm(text) === norm(promptSent));
    if (status === "ok" && (echo || !norm(text))) {
      status = "error";
      errorMessage = echo
        ? "captured prompt echo, not a response (selector wrong / chat not functional)"
        : "empty response captured (selector wrong / no generation)";
      try { debug = Probe.diag.capture(adapter); } catch (_) {}
    }

    await Probe.storage.appendRecord(
      Probe.record.build({
        runId,
        questionId: item.questionId,
        questionText: item.questionText,
        promptSent,
        personaId,
        repIndex: item.repIndex,
        itemKey: item.itemKey,
        provider,
        modelLabel,
        responseText: text,
        status,
        errorMessage,
        timestampStartMs: tStart,
        timestampEndMs: tEnd,
        chatUrl: adapter.chatUrl(),
        debug,
      })
    );
    log.info(`[${provider}] saved ${item.itemKey} (${status}), ${text.length} chars`);
    try { chrome.runtime.sendMessage({ type: Probe.MSG.PROGRESS, provider }); } catch (_) {}
  }

  async function saveErrorRecord(provider, runId, item, err) {
    const { promptSent, personaId } = compose(item);
    let debug = null;
    try { debug = Probe.diag.capture(Probe.registry.forHost(location.hostname)); } catch (_) {}
    await Probe.storage.appendRecord(
      Probe.record.build({
        runId, questionId: item.questionId, questionText: item.questionText,
        promptSent, personaId, repIndex: item.repIndex, itemKey: item.itemKey,
        provider, modelLabel: null, responseText: "", status: "error",
        errorMessage: String(err && err.message ? err.message : err),
        timestampStartMs: null, timestampEndMs: null, chatUrl: location.href, debug,
      })
    );
    log.error(`[${provider}] item ${item.itemKey} failed permanently: ${err && err.message}`);
  }

  // DeepSeek (no private mode) — purge all chats once per run.
  async function maybePurgeOnce(runId, provider, adapter, cfg) {
    if (!cfg.private || typeof adapter.purgeHistory !== "function") return;
    if (await Probe.storage.isPurged(runId, provider)) return;
    try {
      log.info(`[${provider}] purging chat history (privacy)`);
      await adapter.purgeHistory();
    } catch (e) {
      log.warn(`[${provider}] history purge failed (non-fatal): ${e && e.message}`);
    }
    await Probe.storage.markPurged(runId, provider); // mark even on failure to avoid loops
  }

  async function drive() {
    if (mem.running) return;
    const adapter = Probe.registry.forHost(location.hostname);
    if (!adapter) return;
    const provider = adapter.id;

    const runConfig = await Probe.storage.getRunConfig();
    const ps0 = await Probe.storage.getProvState(provider);
    if (!runConfig || !ps0) return;
    if (ps0.status !== "running") return;
    if (!adapter.isReady()) {
      log.warn(`[${provider}] not ready (login/page). Will retry on next focus/nudge.`);
      return;
    }

    mem = { provider, adapter, paused: false, stopped: false, running: true, ownerId: ownerId() };
    const cfg = runConfig.config || {};
    const queue = Probe.runPlan.expand(runConfig);
    await persist(provider, { queueLen: queue.length });
    startHeartbeat(provider);
    log.info(`[${provider}] driving (owner ${mem.ownerId})`);

    try {
      await maybePurgeOnce(runConfig.runId, provider, adapter, cfg);

      while (true) {
        checkControl();
        if (await autoCycleOn()) {
          await waitUntilVisible();
          checkControl();
        }

        const idx = await nextClaimable(runConfig.runId, provider, queue);
        if (idx < 0) {
          const done = (await doneItemKeys(runConfig.runId, provider)).size;
          await persist(provider, { done });
          if (done >= queue.length) {
            await persist(provider, { status: "done", currentState: "DONE" });
            log.info(`[${provider}] complete`);
            break;
          }
          // Other tabs are finishing the rest — let them have focus, then recheck.
          if (await autoCycleOn()) yieldNext();
          await controlledSleep(3000);
          continue;
        }

        await Probe.storage.setClaim(runConfig.runId, provider, idx, mem.ownerId);
        const item = queue[idx];
        try {
          await processItem(adapter, provider, runConfig.runId, item, cfg);
          attemptsByKey[item.itemKey] = 0;
        } catch (err) {
          if (err instanceof ControlSignal) throw err;
          if (err instanceof CapacitySignal) {
            log.warn(`[${provider}] ${err.message}; waiting & retrying`);
            await capacityGate(provider);
            continue;
          }
          const k = item.itemKey;
          attemptsByKey[k] = (attemptsByKey[k] || 0) + 1;
          log.warn(`[${provider}] item ${k} error (attempt ${attemptsByKey[k]}/${MAX_ATTEMPTS}): ${err && err.message}`);
          if (attemptsByKey[k] < MAX_ATTEMPTS) {
            await controlledSleep(4000 * attemptsByKey[k]);
            continue;
          }
          await saveErrorRecord(provider, runConfig.runId, item, err);
          attemptsByKey[k] = 0;
        }

        await persist(provider, { done: (await doneItemKeys(runConfig.runId, provider)).size });
        if (await autoCycleOn()) yieldNext();
        await controlledSleep(Probe.cadence.nextDelay(cfg.cadence || {}));
      }
    } catch (sig) {
      if (sig instanceof ControlSignal) {
        await persist(provider, { status: sig.message === "stopped" ? "stopped" : "paused" });
        log.info(`[${provider}] ${sig.message}`);
      } else {
        await persist(provider, { status: "error" });
        log.error(`[${provider}] driver crashed`, sig);
      }
    } finally {
      mem.running = false;
      stopHeartbeat();
    }
  }

  function pause() { mem.paused = true; }
  function stop() { mem.stopped = true; }
  async function resumeLocal() {
    const adapter = Probe.registry.forHost(location.hostname);
    if (!adapter) return;
    const ps = await Probe.storage.getProvState(adapter.id);
    if (!ps) return;
    ps.status = "running";
    await Probe.storage.setProvState(adapter.id, ps);
    mem.paused = false;
    drive();
  }

  Probe.orchestrator = { drive, pause, stop, resumeLocal };
})();
