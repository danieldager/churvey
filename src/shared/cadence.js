// Pacing: randomized gaps between items, to keep load on each provider low.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const DEFAULTS = Object.freeze({
    baseMs: 9000, // typical gap between finishing one answer and asking the next
    jitterMs: 6000, // +/- random spread
    longPauseChance: 0.15, // occasionally take a much longer break
    longPauseMs: 45000,
    typingMinMs: 18, // per-chunk delay when typing char-by-char
    typingMaxMs: 55,
  });

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  // Inter-item cooldown in ms.
  function nextDelay(opts = {}) {
    const c = { ...DEFAULTS, ...opts };
    let d = c.baseMs + rand(-c.jitterMs, c.jitterMs);
    if (Math.random() < c.longPauseChance) {
      d += c.longPauseMs * rand(0.5, 1.5);
    }
    return Math.max(1500, Math.round(d));
  }

  // Per-chunk typing delay in ms.
  function typingDelay(opts = {}) {
    const c = { ...DEFAULTS, ...opts };
    return Math.round(rand(c.typingMinMs, c.typingMaxMs));
  }

  function sleep(ms) {
    return new Promise((res) => setTimeout(res, ms));
  }

  Probe.cadence = { DEFAULTS, nextDelay, typingDelay, sleep };
})();
