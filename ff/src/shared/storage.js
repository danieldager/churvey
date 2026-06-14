// Minimal promise-based storage wrapper (Firefox browser.storage.local).
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;

  async function get(key, fallback) {
    const v = (await ext.storage.local.get(key))[key];
    return v === undefined ? fallback : v;
  }
  async function set(key, value) {
    await ext.storage.local.set({ [key]: value });
  }
  async function scan(prefix) {
    const all = await ext.storage.local.get(null);
    const out = {};
    for (const [k, v] of Object.entries(all)) if (k.startsWith(prefix)) out[k] = v;
    return out;
  }
  async function removeByPrefix(prefix) {
    const all = await ext.storage.local.get(null);
    const keys = Object.keys(all).filter((k) => k.startsWith(prefix));
    if (keys.length) await ext.storage.local.remove(keys);
  }

  Probe.storage = { get, set, scan, removeByPrefix };
})();
