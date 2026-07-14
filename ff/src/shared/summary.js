// Per-provider run summary: capture rate, latency stats, blocked flag, counts.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const pctile = (s, p) => (s.length ? s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] : null);
  const BLOCK_RE = /login|sign ?up|capacity|high demand|heavy usage|rate.?limit|not ready|composer missing|empty/i;

  function build(records, cfg) {
    const provs = (cfg && cfg.providers) || [...new Set(records.map((r) => r.provider))];
    const expected = cfg ? Probe.runPlan.perProviderCount(cfg) : null;
    const runId = (records[0] && records[0].runId) || (cfg && cfg.runId) || null;
    const scoped = runId ? records.filter((r) => r.runId === runId) : records;
    const expectedKeys = cfg ? Probe.runPlan.expand(cfg).map((it) => it.itemKey) : null;
    const providers = {};
    for (const p of provs) {
      const rs = scoped.filter((r) => r.provider === p);
      const ok = rs.filter((r) => r.status === "ok");
      const err = rs.filter((r) => r.status === "error");
      const okKeys = new Set(ok.map((r) => r.itemKey));
      const missing = expectedKeys ? expectedKeys.filter((k) => !okKeys.has(k)) : [];
      const lat = ok.map((r) => r.latencyMs).filter((x) => typeof x === "number").sort((a, b) => a - b);
      providers[p] = {
        attempted: rs.length, expected,
        completion: expected ? +(rs.length / expected).toFixed(2) : null,
        ok: ok.length, error: err.length, missing,
        captureRate: rs.length ? +(ok.length / rs.length).toFixed(2) : null,
        blocked: err.some((r) => BLOCK_RE.test(r.errorMessage || "")),
        blockReasons: [...new Set(err.map((r) => r.errorMessage).filter(Boolean))],
        models: [...new Set(rs.map((r) => r.modelLabel).filter(Boolean))],
        withCitations: ok.filter((r) => (r.citations || []).length).length,
        citationsTotal: ok.reduce((n, r) => n + (r.citations || []).length, 0),
        latencyMs: lat.length ? { count: lat.length, min: lat[0], median: pctile(lat, 50), p90: pctile(lat, 90), max: lat[lat.length - 1], mean: Math.round(lat.reduce((a, b) => a + b, 0) / lat.length) } : null,
      };
    }
    return {
      runId, generatedAt: new Date().toISOString(),
      config: cfg ? { providers: provs, numQuestions: (cfg.questions || []).length, numPersonas: (cfg.personas || []).length, repetitions: cfg.repetitions || 1, private: !!(cfg.config && cfg.config.private), expectedPerProvider: expected } : null,
      totals: { records: scoped.length, ok: scoped.filter((r) => r.status === "ok").length, error: scoped.filter((r) => r.status === "error").length },
      providers,
    };
  }

  const ms = (x) => (x == null ? "—" : (x / 1000).toFixed(1) + "s");
  function formatText(s) {
    const L = [`Run summary  ${s.runId || ""}`, `Generated ${s.generatedAt}`];
    if (s.config) L.push(`Config: ${s.config.providers.length} providers · ${s.config.numQuestions} questions · ${s.config.numPersonas} personas · ${s.config.repetitions} reps · private=${s.config.private} · expected ${s.config.expectedPerProvider}/provider`);
    L.push(`Totals: ${s.totals.records} records — ok ${s.totals.ok}, error ${s.totals.error}`, "");
    for (const [p, v] of Object.entries(s.providers)) {
      L.push(`${p.padEnd(9)} ${v.attempted}/${v.expected ?? "?"}  ok=${v.ok} err=${v.error}  capture=${v.captureRate == null ? "—" : Math.round(v.captureRate * 100) + "%"}${v.blocked ? "  ⚠ BLOCKED" : ""}`);
      if (v.missing && v.missing.length) L.push(`           MISSING (${v.missing.length}): ${v.missing.slice(0, 8).join(", ")}${v.missing.length > 8 ? " …" : ""}`);
      if (v.latencyMs) L.push(`           latency median ${ms(v.latencyMs.median)} · p90 ${ms(v.latencyMs.p90)} · max ${ms(v.latencyMs.max)}`);
      if (v.models.length) L.push(`           models: ${v.models.join(", ")}`);
      if (v.ok) L.push(`           citations: ${v.citationsTotal} urls across ${v.withCitations}/${v.ok} answers`);
      if (v.blockReasons.length) L.push(`           issues: ${v.blockReasons.slice(0, 3).join(" | ")}`);
    }
    return L.join("\n");
  }

  Probe.summary = { build, formatText };
})();
