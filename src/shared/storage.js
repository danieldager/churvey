// Typed wrapper over chrome.storage.local.
//
// Layout:
//   runConfig                                  the whole-run plan
//   provState::<provider>                      per-provider status/progress
//   rec::<runId>::<provider>::<itemKey>        one record per item (DETERMINISTIC
//                                              key → concurrent tabs dedupe, never
//                                              duplicate)
//   claim::<runId>::<provider>::<idx>          best-effort in-progress claim so
//                                              multiple tabs don't redo the same item
//   purged::<runId>::<provider>                guard so history-purge runs once
//   autoCycle, cycleLastTab                    cycler settings/state
(() => {
  const Probe = (globalThis.Probe ||= {});

  const K = Object.freeze({
    RUN_CONFIG: "runConfig",
    PROV_PREFIX: "provState::",
    REC_PREFIX: "rec::",
    CLAIM_PREFIX: "claim::",
    PURGED_PREFIX: "purged::",
  });

  async function get(key, fallback) {
    const v = (await chrome.storage.local.get(key))[key];
    return v === undefined ? fallback : v;
  }
  async function set(key, value) {
    await chrome.storage.local.set({ [key]: value });
  }
  async function scan(prefix) {
    const all = await chrome.storage.local.get(null);
    const out = {};
    for (const [k, v] of Object.entries(all)) if (k.startsWith(prefix)) out[k] = v;
    return out;
  }
  async function removeByPrefix(prefix) {
    const all = await chrome.storage.local.get(null);
    const keys = Object.keys(all).filter((k) => k.startsWith(prefix));
    if (keys.length) await chrome.storage.local.remove(keys);
  }

  const recKey = (runId, provider, itemKey) => `${K.REC_PREFIX}${runId}::${provider}::${itemKey}`;
  const claimKey = (runId, provider, idx) => `${K.CLAIM_PREFIX}${runId}::${provider}::${idx}`;
  const purgedKey = (runId, provider) => `${K.PURGED_PREFIX}${runId}::${provider}`;

  Probe.storage = {
    K,

    // --- run config ---
    async getRunConfig() { return get(K.RUN_CONFIG, null); },
    async setRunConfig(cfg) { await set(K.RUN_CONFIG, cfg); },
    async clearRunConfig() { await chrome.storage.local.remove(K.RUN_CONFIG); },

    // --- per-provider state ---
    async getProvState(provider) { return get(K.PROV_PREFIX + provider, null); },
    async setProvState(provider, state) { await set(K.PROV_PREFIX + provider, state); },
    async getAllProvStates() {
      const m = await scan(K.PROV_PREFIX);
      const out = {};
      for (const [k, v] of Object.entries(m)) out[k.slice(K.PROV_PREFIX.length)] = v;
      return out;
    },
    async clearAllProvStates() { await removeByPrefix(K.PROV_PREFIX); },

    // --- records (deterministic per-item key) ---
    async appendRecord(rec) {
      await set(recKey(rec.runId, rec.provider, rec.itemKey), rec);
    },
    async hasRecordForItem(runId, provider, itemKey) {
      return (await get(recKey(runId, provider, itemKey), null)) !== null;
    },
    async getAllRecords() {
      const m = await scan(K.REC_PREFIX);
      const recs = Object.values(m);
      recs.sort((a, b) =>
        (a.timestampEnd || "").localeCompare(b.timestampEnd || "") ||
        (a.recordId || "").localeCompare(b.recordId || "")
      );
      return recs;
    },
    async getRecordCount() {
      return Object.keys(await scan(K.REC_PREFIX)).length;
    },
    async getProviderRecordItemKeys(runId, provider) {
      const prefix = `${K.REC_PREFIX}${runId}::${provider}::`;
      const all = await chrome.storage.local.get(null);
      const set2 = new Set();
      for (const k of Object.keys(all)) if (k.startsWith(prefix)) set2.add(k.slice(prefix.length));
      return set2;
    },
    async clearRecords() { await removeByPrefix(K.REC_PREFIX); },

    // --- claims (best-effort; correctness comes from deterministic rec keys) ---
    async getClaim(runId, provider, idx) { return get(claimKey(runId, provider, idx), null); },
    async setClaim(runId, provider, idx, owner) {
      await set(claimKey(runId, provider, idx), { owner, at: Date.now() });
    },
    async getProviderClaims(runId, provider) {
      const prefix = `${K.CLAIM_PREFIX}${runId}::${provider}::`;
      const all = await chrome.storage.local.get(null);
      const out = {};
      for (const [k, v] of Object.entries(all)) if (k.startsWith(prefix)) out[k.slice(prefix.length)] = v;
      return out; // { "<idx>": {owner, at} }
    },

    // --- one-time guards (e.g. history purge) ---
    async isPurged(runId, provider) { return (await get(purgedKey(runId, provider), null)) === true; },
    async markPurged(runId, provider) { await set(purgedKey(runId, provider), true); },

    // --- full reset of a run's transient artifacts ---
    async clearRunArtifacts() {
      await removeByPrefix(K.REC_PREFIX);
      await removeByPrefix(K.PROV_PREFIX);
      await removeByPrefix(K.CLAIM_PREFIX);
      await removeByPrefix(K.PURGED_PREFIX);
      await chrome.storage.local.remove("cycleLastTab");
    },

    get, set, scan,
  };
})();
