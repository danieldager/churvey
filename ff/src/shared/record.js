// Builds one JSONL record. Capture happens at the network layer, so we also keep
// the capture endpoint URL.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const SCHEMA_VERSION = 3; // +citations[]

  const extVersion = () => { try { return ext.runtime.getManifest().version; } catch (_) { return null; } };
  const uuid = () => (globalThis.crypto && crypto.randomUUID ? crypto.randomUUID() : "id-" + Date.now() + "-" + Math.floor(Math.random() * 1e9));

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
      latencyMs: f.latencyMs ?? (start && end ? end - start : null),
      private: f.private ?? null,
      captureUrl: f.captureUrl ?? null,
      citations: Array.isArray(f.citations) ? f.citations : [],
      userAgent: (globalThis.navigator && navigator.userAgent) || null,
      extensionVersion: extVersion(),
    };
  }
  Probe.record = { SCHEMA_VERSION, build, uuid };
})();
