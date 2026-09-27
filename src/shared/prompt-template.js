// The ONLY place a prompt string is built. Keeping composition isolated here
// means the future persona-priming phase is a drop-in: pass a persona object
// and the orchestrator/adapters need no changes.
(() => {
  const Probe = (globalThis.Probe ||= {});

  /**
   * @param {object} args
   * @param {{id:string, preamble:string}|null} args.persona
   * @param {{id:string, text:string}} args.question
   * @returns {{promptSent:string, personaId:string|null}}
   */
  function compose({ persona, question }) {
    if (persona && persona.preamble && persona.preamble.trim()) {
      return {
        promptSent: `${persona.preamble.trim()}\n\n${question.text}`,
        personaId: persona.id || "persona",
      };
    }
    return { promptSent: question.text, personaId: null };
  }

  Probe.prompt = { compose };
})();
