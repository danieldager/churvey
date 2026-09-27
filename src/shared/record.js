// Builds a single data record (one JSONL line) with a stable schema.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const SCHEMA_VERSION = 1;

  function extensionVersion() {
    try {
      return chrome.runtime.getManifest().version;
    } catch (_) {
      return null;
    }
  }

  function uuid() {
    if (globalThis.crypto && crypto.randomUUID) return crypto.randomUUID();
    // Fallback for older runtimes.
    return "id-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
  }

  /**
   * @param {object} f
   * @param {string} f.runId
   * @param {string} f.questionId
   * @param {string} f.questionText   raw question body
   * @param {string} f.promptSent     full text injected (persona preamble + body)
   * @param {string|null} f.personaId
   * @param {number|null} f.repIndex
   * @param {string|null} f.itemKey      stable id: persona#rep#question
   * @param {string} f.provider
   * @param {string|null} f.modelLabel
   * @param {string} f.responseText
   * @param {"ok"|"error"|"truncated"} f.status
   * @param {string|null} f.errorMessage
   * @param {number} f.timestampStartMs  epoch ms when submit fired
   * @param {number} f.timestampEndMs    epoch ms when response detected complete
   * @param {string|null} f.chatUrl
   */
  function build(f) {
    const start = f.timestampStartMs ?? null;
    const end = f.timestampEndMs ?? null;
    return {
      schemaVersion: SCHEMA_VERSION,
      runId: f.runId,
      recordId: uuid(),
      questionId: f.questionId,
      questionText: f.questionText,
      promptSent: f.promptSent,
      personaId: f.personaId ?? null,
      repIndex: f.repIndex ?? null,
      itemKey: f.itemKey ?? null,
      provider: f.provider,
      modelLabel: f.modelLabel ?? null,
      responseText: f.responseText ?? "",
      status: f.status,
      errorMessage: f.errorMessage ?? null,
      timestampStart: start ? new Date(start).toISOString() : null,
      timestampEnd: end ? new Date(end).toISOString() : null,
      latencyMs: start && end ? end - start : null,
      chatUrl: f.chatUrl ?? null,
      userAgent: (globalThis.navigator && navigator.userAgent) || null,
      extensionVersion: extensionVersion(),
      debug: f.debug ?? null,
    };
  }

  Probe.record = { SCHEMA_VERSION, build, uuid };
})();
