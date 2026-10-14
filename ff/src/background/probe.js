// `churvey probe`, the part that sends no message: for each chatbot, what the page and the account endpoints look
// like today. Only raw observations are collected here; churvey/probe.py turns them into PASS / FAIL / CHANGED.
// Nothing is changed on the account unless `destructive` (then: memory switched off and read back).
// Reached through a maintenance plan {probe: {providers, destructive}} (isolation.js maintain).
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("probe");
  const sleep = (ms) => Probe.cadence.sleep(ms);
  const err = (e) => ({ error: String(e?.message || e) });

  // A PNG of the provider's tab (data: URL), kept by probe.py only for checks that FAIL.
  async function shot(tabId) {
    try {
      const t = await ext.tabs.get(tabId);
      await ext.tabs.update(tabId, { active: true });
      await sleep(400);
      return await ext.tabs.captureVisibleTab(t.windowId, { format: "png" });
    } catch (e) { return "error " + String(e?.message || e); }
  }

  async function one(pid, destructive) {
    const I = Probe.isolation;
    const raw = { shots: {} };
    let tabId;
    try { tabId = await I.tabFor(pid); } catch (e) { raw.open = err(e); return raw; }
    const call = async (fn, args, t) => { try { return await I.call(pid, tabId, fn, args, t); } catch (e) { return err(e); } };
    const send = async (msg, t = 20000) => { try { return await I.ask(tabId, msg, t); } catch (e) { return err(e); } };
    const where = async () => { try { return (await ext.tabs.get(tabId)).url; } catch (_) { return null; } };

    // The home page: who is signed in, what the page says, the selectors, the endpoints, the banner detector.
    raw.login = { state: await call("loginState"), page: await send({ type: Probe.MSG.PAGE_STATUS }) };
    raw.home = { url: await where(), fingerprint: await call("fingerprint") };
    raw.shapes = await call("endpointShapes");
    raw.banner = await call("bannerTest");
    raw.memory = (await I.memory([pid]))[pid];
    tabId = await I.tabFor(pid, Probe.providers.byId(pid).homeUrl);   // memory() may have moved the tab (Gemini)
    const ids = await send({ type: Probe.MSG.LIST_CHATS }, 60000);
    raw.list = ids && ids.ok ? { count: ids.ids.length } : { error: (ids && ids.error) || "no reply" };
    raw.shots.home = await shot(tabId);

    // A new ordinary chat, then a new temporary one: what isolationState says before anything is typed.
    for (const [key, priv] of [["new_chat", false], ["temporary", true]]) {
      await send({ type: Probe.MSG.NEW_CHAT, private: priv }, 15000);   // may navigate: the reply is then lost
      await sleep(1500);
      if (!(await I.ready(tabId))) { raw[key] = { error: "page never became ready after starting the chat" }; continue; }
      await sleep(1500);
      raw[key] = { url: await where(), state: await send({ type: Probe.MSG.ISOLATION_STATE }), fingerprint: await call("fingerprint") };
    }
    raw.shots.temporary = await shot(tabId);

    // The memory switches on the settings page; with destructive, switched off and read back.
    raw.controls = await call("memoryControls", [], 60000);
    if (destructive) raw.memoryOff = (await I.maintain({ memoryOff: [pid] })).memoryOff[pid];
    raw.shots.settings = await shot(tabId);
    return raw;
  }

  async function run({ providers, destructive }) {
    const out = {};
    for (const pid of providers || []) {
      try { out[pid] = await one(pid, !!destructive); } catch (e) { out[pid] = { open: err(e), shots: {} }; }
      log.info(`[${pid}] probed: signed in ${JSON.stringify(out[pid].login && out[pid].login.state)}`);
    }
    return out;
  }

  Probe.probe = { run };
})();
