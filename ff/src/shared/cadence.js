// Randomized human-like delays.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const rand = (a, b) => a + Math.random() * (b - a);
  Probe.cadence = {
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    nextDelay: ({ baseMs = 9000, jitterMs = 6000 } = {}) =>
      Math.max(1500, Math.round(baseMs + rand(-jitterMs, jitterMs))),
    typingDelay: () => Math.round(rand(18, 55)),
  };
})();
