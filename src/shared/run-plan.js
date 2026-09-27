// Deterministic expansion of a run config into a per-provider work queue.
// Because the order is fixed and regenerable, we only need to persist a cursor
// index per provider — resume just re-expands and jumps to the cursor.
(() => {
  const Probe = (globalThis.Probe ||= {});

  function itemKey(personaId, repIndex, questionId) {
    return `${personaId || "neutral"}#r${repIndex}#${questionId}`;
  }

  // Order: persona (outer) -> repetition (middle) -> question (inner).
  // Each repetition is thus a full pass over the question set (a "session").
  function expand(runConfig) {
    const reps = Math.max(1, runConfig.repetitions || 1);
    const personas =
      runConfig.personas && runConfig.personas.length
        ? runConfig.personas
        : [null]; // neutral
    const questions = runConfig.questions || [];
    const items = [];
    let idx = 0;
    for (const persona of personas) {
      const personaId = persona ? persona.id || "persona" : null;
      for (let rep = 0; rep < reps; rep++) {
        for (const q of questions) {
          items.push({
            idx: idx++,
            questionId: q.id,
            questionText: q.text,
            persona, // full object or null
            personaId,
            repIndex: rep,
            itemKey: itemKey(personaId, rep, q.id),
          });
        }
      }
    }
    return items;
  }

  function queueLength(runConfig) {
    const reps = Math.max(1, runConfig.repetitions || 1);
    const nPersonas =
      runConfig.personas && runConfig.personas.length
        ? runConfig.personas.length
        : 1;
    const nQuestions = (runConfig.questions || []).length;
    return reps * nPersonas * nQuestions;
  }

  Probe.runPlan = { expand, queueLength, itemKey };
})();
