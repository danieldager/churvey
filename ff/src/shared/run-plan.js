// Deterministic expansion of a run config into the per-provider work list.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const itemKey = (personaId, rep, qid) => `${personaId || "neutral"}#r${rep}#${qid}`;

  // persona (outer) -> repetition (middle) -> question (inner)
  function expand(cfg) {
    const reps = Math.max(1, cfg.repetitions || 1);
    const personas = cfg.personas && cfg.personas.length ? cfg.personas : [null];
    const questions = cfg.questions || [];
    const items = [];
    let idx = 0;
    for (const persona of personas) {
      const personaId = persona ? persona.id || "persona" : null;
      for (let rep = 0; rep < reps; rep++) {
        for (const q of questions) {
          items.push({ idx: idx++, questionId: q.id, questionText: q.text, persona, personaId, repIndex: rep, itemKey: itemKey(personaId, rep, q.id) });
        }
      }
    }
    return items;
  }
  const perProviderCount = (cfg) => {
    const reps = Math.max(1, cfg.repetitions || 1);
    const nP = (cfg.personas || []).length || 1;
    return reps * nP * (cfg.questions || []).length;
  };

  Probe.runPlan = { expand, perProviderCount, itemKey };
})();
