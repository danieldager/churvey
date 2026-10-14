// Account-level checks and chat deletion, outside a run: read each account's memory setting, delete the chats a run
// created (by id, through the provider's own delete), and list an account's whole history (purge --everything).
// Driven by autostart.js when the launcher serves a {task: "maintenance"} plan, and after a run (config.purgeAfter).
// Account settings are changed only by memoryOff / deleteAll (churvey account prepare, after a typed confirmation).
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("isolation");
  const sleep = (ms) => Probe.cadence.sleep(ms);

  async function ready(tabId, timeoutMs = 30000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      try { const r = await ext.tabs.sendMessage(tabId, { type: Probe.MSG.PING }); if (r && r.ok) return true; } catch (_) {}
      await sleep(600);
    }
    return false;
  }

  // The provider's tab (opened in its own window if there is none), optionally navigated to `url`.
  async function tabFor(pid, url) {
    const meta = Probe.providers.byId(pid);
    let [t] = await ext.tabs.query({ url: meta.matchPattern });
    if (!t) { const w = await ext.windows.create({ url: url || meta.homeUrl }); t = w.tabs[0]; await sleep(2500); }
    else if (url) { await ext.tabs.update(t.id, { url }); await sleep(2500); }
    if (!(await ready(t.id))) throw new Error("page never became ready (signed out?)");
    await sleep(1500); // let the app finish its own start-up requests (Claude's org id is read from them)
    return t.id;
  }

  async function ask(tabId, msg, timeoutMs = 120000) {
    return Promise.race([ext.tabs.sendMessage(tabId, msg), new Promise((res) => setTimeout(() => res({ ok: false, error: "no reply" }), timeoutMs))]);
  }

  async function memory(pids) {
    const out = {};
    for (const pid of pids) {
      try {
        let tabId = await tabFor(pid);
        let r = await ask(tabId, { type: Probe.MSG.MEMORY_STATUS });
        if (r && r.ok && r.needs) { tabId = await tabFor(pid, r.needs); r = await ask(tabId, { type: Probe.MSG.MEMORY_STATUS }); }
        out[pid] = r && r.ok ? { status: r.status, detail: r.detail || "" } : { status: "unknown", detail: (r && r.error) || "no reply" };
      } catch (e) { out[pid] = { status: "unknown", detail: String(e?.message || e) }; }
      log.info(`[${pid}] memory ${out[pid].status}: ${out[pid].detail}`);
    }
    return out;
  }

  // byPid: {pid: [chat ids]} -> {pid: {id: "deleted" | "not_found" | "unsupported" | "error ..."}}
  async function purge(byPid) {
    const out = {};
    for (const [pid, ids] of Object.entries(byPid || {})) {
      if (!ids || !ids.length) continue;
      try {
        const tabId = await tabFor(pid);
        const r = await ask(tabId, { type: Probe.MSG.DELETE_CHATS, ids }, 30000 + ids.length * 5000);
        out[pid] = r && r.ok ? r.results : Object.fromEntries(ids.map((id) => [id, "error " + ((r && r.error) || "no reply")]));
      } catch (e) { out[pid] = Object.fromEntries(ids.map((id) => [id, "error " + String(e?.message || e)])); }
      const n = Object.values(out[pid]).filter((v) => v === "deleted" || v === "not_found").length;
      log.info(`[${pid}] purge: ${n}/${ids.length} deleted or not found`);
    }
    return out;
  }

  // pids -> {pid: {ids} | {error}}: the whole history of the account (for purge --everything's count and delete).
  async function list(pids) {
    const out = {};
    for (const pid of pids) {
      try {
        const tabId = await tabFor(pid);
        const r = await ask(tabId, { type: Probe.MSG.LIST_CHATS });
        out[pid] = r && r.ok ? { ids: r.ids } : { error: (r && r.error) || "no reply" };
      } catch (e) { out[pid] = { error: String(e?.message || e) }; }
    }
    return out;
  }

  // One whitelisted driver function in the provider's tab (driver.js PROBE_CALL). A result {needs: url} means "only
  // readable on that page": the tab goes there and the call is made again.
  async function call(pid, tabId, fn, args = [], timeoutMs = 60000) {
    let r = await ask(tabId, { type: Probe.MSG.PROBE_CALL, fn, args }, timeoutMs);
    if (r && r.ok && r.result && r.result.needs) { tabId = await tabFor(pid, r.result.needs); r = await ask(tabId, { type: Probe.MSG.PROBE_CALL, fn, args }, timeoutMs); }
    if (!r || !r.ok) throw new Error((r && r.error) || "no reply");
    return r.result;
  }

  async function listIds(tabId) {
    const r = await ask(tabId, { type: Probe.MSG.LIST_CHATS });
    if (!r || !r.ok) throw new Error("list: " + ((r && r.error) || "no reply"));
    return r.ids;
  }

  // account prepare: who is signed in. {pid: {signedIn, account, how} | {error}}
  async function whoami(pids) {
    const out = {};
    for (const pid of pids) {
      try { out[pid] = await call(pid, await tabFor(pid), "loginState"); } catch (e) { out[pid] = { error: String(e?.message || e) }; }
    }
    return out;
  }

  // account prepare: switch account memory off through the provider's own setting, then read it back.
  // {pid: {before, action, switches, after} | {error}}. A memory already off is left alone.
  async function memoryOff(pids) {
    const out = {};
    for (const pid of pids) {
      try {
        const before = (await memory([pid]))[pid];
        if (before.status === "off") { out[pid] = { before, action: "already off", after: before }; continue; }
        const act = await call(pid, await tabFor(pid), "memoryOff", [], 120000);
        await sleep(1500);
        const after = (await memory([pid]))[pid];
        out[pid] = { before, action: act.detail || "", switches: act.switches || null, after };
      } catch (e) { out[pid] = { error: String(e?.message || e) }; }
      log.info(`[${pid}] memory off: ${JSON.stringify(out[pid]).slice(0, 300)}`);
    }
    return out;
  }

  // account prepare: delete EVERY chat of the account. The driver's own bulk delete where it has one
  // (deleteAllChats), else list + delete each by id until the list is empty. Then the history is listed again.
  // {pid: {method, before, after, results, detail} | {error}}
  async function deleteAll(pids) {
    const out = {};
    for (const pid of pids) {
      try {
        const tabId = await tabFor(pid);
        const before = (await listIds(tabId)).length;
        let method, results = {}, detail = null;
        const r = await ask(tabId, { type: Probe.MSG.PROBE_CALL, fn: "deleteAllChats" }, 30 * 60000);
        if (r && r.ok) { ({ method, results = {}, ...detail } = r.result); }
        else if (r && /no deleteAllChats/.test(r.error || "")) {
          method = "one by one: list, delete each by id, until the list is empty";
          for (let round = 0; round < 20; round++) {
            const ids = await listIds(tabId);
            if (!ids.length) break;
            const d = await ask(tabId, { type: Probe.MSG.DELETE_CHATS, ids }, 30000 + ids.length * 5000);
            if (!d || !d.ok) throw new Error("delete: " + ((d && d.error) || "no reply"));
            Object.assign(results, d.results);
            if (!Object.values(d.results).includes("deleted")) break;   // nothing went: stop instead of looping
          }
        } else throw new Error((r && r.error) || "no reply");
        await sleep(1500);
        const after = (await listIds(await tabFor(pid, Probe.providers.byId(pid).homeUrl))).length;
        out[pid] = { method, before, after, results, detail };
      } catch (e) { out[pid] = { error: String(e?.message || e) }; }
      log.info(`[${pid}] delete all: ${JSON.stringify(out[pid]).slice(0, 300)}`);
    }
    return out;
  }

  // One maintenance plan: {memory: [pids], purge: {pid: ids}, list: [pids], purgeListed: [pids],
  // whoami: [pids], memoryOff: [pids], deleteAll: [pids], probe: {providers, destructive}}.
  // purgeListed = list those accounts and delete every chat listed (purge --everything, after the CLI's confirmation).
  // memoryOff / deleteAll = churvey account prepare, after its typed confirmation; probe = churvey probe (probe.js).
  async function maintain(m) {
    const res = {};
    if (m.whoami && m.whoami.length) res.whoami = await whoami(m.whoami);
    if (m.memory && m.memory.length) res.memory = await memory(m.memory);
    if (m.purge) res.purge = await purge(m.purge);
    if (m.list && m.list.length) res.list = await list(m.list);
    if (m.purgeListed && m.purgeListed.length) {
      const listed = await list(m.purgeListed);
      res.list = listed;
      res.purge = Object.assign(res.purge || {}, await purge(Object.fromEntries(Object.entries(listed).filter(([, v]) => v.ids).map(([p, v]) => [p, v.ids]))));
    }
    if (m.memoryOff && m.memoryOff.length) res.memoryOff = await memoryOff(m.memoryOff);
    if (m.deleteAll && m.deleteAll.length) res.deleteAll = await deleteAll(m.deleteAll);
    if (m.probe) res.probe = await Probe.probe.run(m.probe);
    return res;
  }

  Probe.isolation = { memory, purge, list, maintain, tabFor, ready, ask, call };
})();
