// The only place a prompt string is built (persona preamble + question).
(() => {
  const Probe = (globalThis.Probe ||= {});
  function compose({ persona, question }) {
    if (persona && persona.preamble && persona.preamble.trim()) {
      return { promptSent: `${persona.preamble.trim()}\n\n${question.text}`, personaId: persona.id || "persona" };
    }
    return { promptSent: question.text, personaId: null };
  }
  Probe.prompt = { compose };
})();
