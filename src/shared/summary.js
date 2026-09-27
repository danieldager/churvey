// Builds a run summary from captured records: per-provider capture rate, latency
// stats, blocked detection, and counts. Used by the SW (export) and popup.
(() => {
  const Probe = (globalThis.Probe ||= {});

  function pctile(sorted, p) {
    if (!sorted.length) return null;
    const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
    return sorted[idx];
  }

  const BLOCK_RE = /login|sign ?up|capacity|high demand|rate.?limit|echo|empty|consent|not ready|composer missing/i;

  function build(records, runConfig) {
    const provs =
      (runConfig && runConfig.providers) || [...new Set(records.map((r) => r.provider))];
    const expected = runConfig ? expectedPerProvider(runConfig) : null;
    const runId = (records[0] && records[0].runId) || (runConfig && runConfig.runId) || null;
    const scoped = runId ? records.filter((r) => r.runId === runId) : records;

    const providers = {};
    for (const p of provs) {
      const rs = scoped.filter((r) => r.provider === p);
      const ok = rs.filter((r) => r.status === "ok");
      const truncated = rs.filter((r) => r.status === "truncated");
      const errors = rs.filter((r) => r.status === "error");
      const lat = ok.map((r) => r.latencyMs).filter((x) => typeof x === "number").sort((a, b) => a - b);
      const reasons = [...new Set(errors.map((r) => r.errorMessage).filter(Boolean))];
      const blocked = errors.some((r) => BLOCK_RE.test(r.errorMessage || ""));
      const times = rs.map((r) => r.timestampEnd).filter(Boolean).sort();
      providers[p] = {
        attempted: rs.length,
        expected,
        completion: expected ? +(rs.length / expected).toFixed(2) : null,
        ok: ok.length,
        truncated: truncated.length,
        error: errors.length,
        captureRate: rs.length ? +(ok.length / rs.length).toFixed(2) : null,
        blocked,
        blockReasons: reasons,
        models: [...new Set(rs.map((r) => r.modelLabel).filter(Boolean))],
        latencyMs: lat.length
          ? {
              count: lat.length,
              min: lat[0],
              median: pctile(lat, 50),
              p90: pctile(lat, 90),
              max: lat[lat.length - 1],
              mean: Math.round(lat.reduce((a, b) => a + b, 0) / lat.length),
            }
          : null,
        firstAt: times[0] || null,
        lastAt: times[times.length - 1] || null,
      };
    }

    return {
      runId,
      generatedAt: new Date().toISOString(),
      config: runConfig
        ? {
            providers: provs,
            numQuestions: (runConfig.questions || []).length,
            numPersonas: (runConfig.personas || []).length,
            repetitions: runConfig.repetitions || 1,
            tabsPerProvider: runConfig.tabsPerProvider || 1,
            private: !!(runConfig.config && runConfig.config.private),
            expectedPerProvider: expected,
          }
        : null,
      totals: {
        records: scoped.length,
        ok: scoped.filter((r) => r.status === "ok").length,
        truncated: scoped.filter((r) => r.status === "truncated").length,
        error: scoped.filter((r) => r.status === "error").length,
      },
      providers,
    };
  }

  function expectedPerProvider(runConfig) {
    const reps = Math.max(1, runConfig.repetitions || 1);
    const nP = (runConfig.personas || []).length || 1;
    const nQ = (runConfig.questions || []).length;
    return reps * nP * nQ;
  }

  function ms(x) {
    return x == null ? "—" : (x / 1000).toFixed(1) + "s";
  }

  function formatText(s) {
    const L = [];
    L.push(`Run summary  ${s.runId || ""}`);
    L.push(`Generated ${s.generatedAt}`);
    if (s.config) {
      L.push(
        `Config: ${s.config.providers.length} providers · ${s.config.numQuestions} questions · ` +
          `${s.config.numPersonas || 0} personas · ${s.config.repetitions} reps · ` +
          `${s.config.tabsPerProvider} tab(s)/prov · private=${s.config.private} · ` +
          `expected ${s.config.expectedPerProvider}/provider`
      );
    }
    L.push(`Totals: ${s.totals.records} records — ok ${s.totals.ok}, truncated ${s.totals.truncated}, error ${s.totals.error}`);
    L.push("");
    for (const [p, v] of Object.entries(s.providers)) {
      const lat = v.latencyMs;
      L.push(
        `${p.padEnd(9)} ${v.attempted}/${v.expected ?? "?"} done` +
          `  ok=${v.ok} trunc=${v.truncated} err=${v.error}` +
          `  capture=${v.captureRate == null ? "—" : Math.round(v.captureRate * 100) + "%"}` +
          (v.blocked ? "  ⚠ BLOCKED" : "")
      );
      if (lat) L.push(`           latency: median ${ms(lat.median)} · p90 ${ms(lat.p90)} · max ${ms(lat.max)} (n=${lat.count})`);
      if (v.models.length) L.push(`           models: ${v.models.join(", ")}`);
      if (v.blockReasons.length) L.push(`           issues: ${v.blockReasons.slice(0, 4).join(" | ")}`);
    }
    return L.join("\n");
  }

  Probe.summary = { build, formatText };
})();
