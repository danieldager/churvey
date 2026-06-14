// Maps the current hostname to a provider adapter. Adapters self-register into
// Probe.registry._list when their files load (before this file, per manifest).
(() => {
  const Probe = (globalThis.Probe ||= {});
  Probe.registry = Probe.registry || { _list: [] };

  Probe.registry.forHost = function forHost(hostname) {
    return Probe.registry._list.find((a) => {
      try {
        return a.hostMatch(hostname);
      } catch (_) {
        return false;
      }
    }) || null;
  };

  Probe.registry.all = function all() {
    return Probe.registry._list.slice();
  };

  Probe.registry.byId = function byId(id) {
    return Probe.registry._list.find((a) => a.id === id) || null;
  };
})();
