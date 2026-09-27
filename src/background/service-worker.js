// Service worker: run coordinator + data export. Opens N tabs per provider,
// writes run config + per-provider state, then each content script self-drives
// and claims work. Cycles focus across ALL run tabs so each gets unthrottled
// foreground time. NO long-running orchestration here (MV3 kills idle SWs).
importScripts(
  "../shared/namespace.js",
  "../shared/messages.js",
  "../shared/logger.js",
  "../shared/providers.js",
  "../shared/run-plan.js",
  "../shared/storage.js",
  "../shared/summary.js"
);

const Probe = globalThis.Probe;
const log = Probe.log.make("sw");

const WATCHDOG_ALARM = "watchdog";
const CYCLE_ALARM = "cycle";
const STALE_MS = 70000;

function setupAlarms() {
  chrome.alarms.create(WATCHDOG_ALARM, { periodInMinutes: 1 });
  chrome.alarms.create(CYCLE_ALARM, { periodInMinutes: 0.5 }); // 30s platform min
}
chrome.runtime.onInstalled.addListener(setupAlarms);
chrome.runtime.onStartup.addListener(setupAlarms);

// --- tab cycler: rotate focus across every tab participating in the run ---
async function runTabs() {
  const states = await Probe.storage.getAllProvStates();
  const running = Object.keys(states).filter((p) => states[p].status === "running");
  const out = [];
  for (const p of running) {
    const meta = Probe.providers.byId(p);
    if (!meta) continue;
    const tabs = await chrome.tabs.query({ url: meta.matchPattern });
    tabs.sort((a, b) => a.id - b.id);
    for (const t of tabs) out.push({ id: t.id, windowId: t.windowId, provider: p });
  }
  return out;
}
async function focusTab(t) {
  try {
    await chrome.tabs.update(t.id, { active: true });
    await chrome.windows.update(t.windowId, { focused: true });
  } catch (_) {}
  await Probe.storage.set("cycleLastTab", t.id);
}
async function focusNextTab(currentId) {
  if (!(await Probe.storage.get("autoCycle", true))) return;
  const tabs = await runTabs();
  if (tabs.length < 2) return; // nothing to cycle
  let i = tabs.findIndex((t) => t.id === currentId);
  if (i < 0) {
    const last = await Probe.storage.get("cycleLastTab", -1);
    i = tabs.findIndex((t) => t.id === last);
  }
  const next = tabs[(i + 1) % tabs.length];
  await focusTab(next);
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === CYCLE_ALARM) {
    return void focusNextTab(await Probe.storage.get("cycleLastTab", -1)).catch(() => {});
  }
  if (alarm.name !== WATCHDOG_ALARM) return;
  try {
    const states = await Probe.storage.getAllProvStates();
    for (const [provider, ps] of Object.entries(states)) {
      if (ps.status !== "running") continue;
      if (Date.now() - (ps.heartbeatAt || 0) < STALE_MS) continue;
      log.warn(`[${provider}] stalled; nudging`);
      await nudgeProvider(provider);
    }
  } catch (e) {
    log.error("watchdog error", e?.message || e);
  }
});

async function nudgeProvider(provider) {
  const meta = Probe.providers.byId(provider);
  if (!meta) return;
  const tabs = await chrome.tabs.query({ url: meta.matchPattern });
  for (const t of tabs) chrome.tabs.sendMessage(t.id, { type: Probe.MSG.DRIVE }).catch(() => {});
}

// Open up to n tabs for a provider in the target window (reuse existing).
async function openProviderTabs(provider, n, windowId) {
  const meta = Probe.providers.byId(provider);
  if (!meta) throw new Error("unknown provider " + provider);
  const q = { url: meta.matchPattern };
  if (windowId) q.windowId = windowId;
  const existing = await chrome.tabs.query(q);
  for (let i = existing.length; i < n; i++) {
    const props = { url: meta.homeUrl, active: false };
    if (windowId) props.windowId = windowId;
    await chrome.tabs.create(props);
  }
  if (existing.length) setTimeout(() => nudgeProvider(provider), 1500);
  return Math.max(existing.length, n);
}

function freshProvState(runId, provider, queueLen) {
  const t = Date.now();
  return { runId, provider, status: "running", queueLen, done: 0, startedAt: t, updatedAt: t, heartbeatAt: t };
}

async function startRun(runConfig, windowId) {
  const runId = `run_${new Date().toISOString().replace(/[:.]/g, "-")}`;
  const cfg = { ...runConfig, runId };
  const queueLen = Probe.runPlan.queueLength(cfg);
  const n = Math.max(1, cfg.tabsPerProvider || 1);
  await Probe.storage.setRunConfig(cfg);
  await Probe.storage.clearAllProvStates(); // reset progress; records are kept (new runId)
  for (const provider of cfg.providers) {
    await Probe.storage.setProvState(provider, freshProvState(runId, provider, queueLen));
    await openProviderTabs(provider, n, windowId);
  }
  log.info(`started ${runId}: ${cfg.providers.join(", ")} x ${queueLen} items, ${n} tab(s)/provider`);
  return { runId, queueLen, tabsPerProvider: n };
}

async function resumeRun(windowId) {
  const cfg = await Probe.storage.getRunConfig();
  if (!cfg) throw new Error("no run to resume");
  const n = Math.max(1, cfg.tabsPerProvider || 1);
  const states = await Probe.storage.getAllProvStates();
  const resumed = [];
  for (const [provider, ps] of Object.entries(states)) {
    if (ps.status !== "running" && ps.status !== "paused") continue;
    ps.status = "running";
    await Probe.storage.setProvState(provider, ps);
    await openProviderTabs(provider, n, windowId);
    setTimeout(() => nudgeProvider(provider), 2000);
    resumed.push(provider);
  }
  log.info(`resumed: ${resumed.join(", ") || "(none)"}`);
  return { resumed };
}

async function broadcastControl(type, newStatus) {
  const states = await Probe.storage.getAllProvStates();
  for (const [provider, ps] of Object.entries(states)) {
    const meta = Probe.providers.byId(provider);
    let delivered = false;
    if (meta) {
      const tabs = await chrome.tabs.query({ url: meta.matchPattern });
      for (const t of tabs) {
        try { await chrome.tabs.sendMessage(t.id, { type }); delivered = true; } catch (_) {}
      }
    }
    if (!delivered && (ps.status === "running" || ps.status === "paused")) {
      ps.status = newStatus;
      await Probe.storage.setProvState(provider, ps);
    }
  }
}

async function overview() {
  const runConfig = await Probe.storage.getRunConfig();
  const provStates = await Probe.storage.getAllProvStates();
  const records = await Probe.storage.getAllRecords();
  const runId = runConfig && runConfig.runId;
  const queueLen = runConfig ? Probe.runPlan.queueLength(runConfig) : 0;
  const perProvider = {};
  const provs = (runConfig && runConfig.providers) || Object.keys(provStates);
  for (const p of provs) {
    const rs = records.filter((r) => r.provider === p && (!runId || r.runId === runId));
    perProvider[p] = {
      done: rs.length,
      total: queueLen,
      ok: rs.filter((r) => r.status === "ok").length,
      error: rs.filter((r) => r.status === "error").length,
      truncated: rs.filter((r) => r.status === "truncated").length,
      status: (provStates[p] && provStates[p].status) || "—",
    };
  }
  return { runConfig, provStates, recordCount: records.length, perProvider };
}

async function exportJsonl() {
  const records = await Probe.storage.getAllRecords();
  const cfg = await Probe.storage.getRunConfig();
  const jsonl = records.map((r) => JSON.stringify(r)).join("\n");
  const runId = (cfg && cfg.runId) || "run";
  const filename = `chat-probe/${runId}.jsonl`;
  const dataUrl = "data:application/x-ndjson;charset=utf-8," + encodeURIComponent(jsonl);
  const downloadId = await chrome.downloads.download({ url: dataUrl, filename, saveAs: true });
  const summary = Probe.summary.build(records, cfg);
  log.info(`exported ${records.length} -> ${filename}`);
  return { count: records.length, downloadId, filename, summary, summaryText: Probe.summary.formatText(summary) };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg && msg.type) {
        case Probe.MSG.START_RUN:
          sendResponse({ ok: true, ...(await startRun(msg.runConfig, msg.windowId)) });
          break;
        case Probe.MSG.RESUME_RUN:
          sendResponse({ ok: true, ...(await resumeRun(msg.windowId)) });
          break;
        case Probe.MSG.PAUSE_ALL:
          await broadcastControl(Probe.MSG.PAUSE, "paused");
          sendResponse({ ok: true });
          break;
        case Probe.MSG.STOP_ALL:
          await broadcastControl(Probe.MSG.STOP, "stopped");
          sendResponse({ ok: true });
          break;
        case Probe.MSG.YIELD:
          await focusNextTab(sender && sender.tab && sender.tab.id);
          sendResponse({ ok: true });
          break;
        case Probe.MSG.GET_OVERVIEW:
          sendResponse({ ok: true, ...(await overview()) });
          break;
        case Probe.MSG.EXPORT:
          sendResponse({ ok: true, ...(await exportJsonl()) });
          break;
        case Probe.MSG.GET_RECORD_COUNT:
          sendResponse({ ok: true, count: await Probe.storage.getRecordCount() });
          break;
        case Probe.MSG.CLEAR_RECORDS:
          await broadcastControl(Probe.MSG.STOP, "stopped");
          await Probe.storage.clearRunArtifacts();
          await Probe.storage.clearRunConfig();
          sendResponse({ ok: true });
          break;
        default:
          sendResponse({ ok: false, error: "unhandled by sw" });
      }
    } catch (e) {
      log.error("sw message error", e?.message || e);
      sendResponse({ ok: false, error: String(e?.message || e) });
    }
  })();
  return true;
});
