// Builds one JSONL record. Capture happens at the network layer, so we also keep
// the capture endpoint URL.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const SCHEMA_VERSION = 7; // v7: +isolation {new_chat, temporary, followup, chat_id, evidence}. v6: +capture_method (stream|poll|dom_fallback; null on error records). v5: citations = DISPLAYED only, with anchor_text/offsets/marker (Probe.citations), +fetchedUrls (v4: +followupOf, v3: +citations[])

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
      followupOf: f.followupOf ?? null,
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
      fetchedUrls: Array.isArray(f.fetchedUrls) ? f.fetchedUrls : [],
      capture_method: f.captureMethod ?? null, // how the answer was obtained: stream (network body tee'd) | poll (page read the finished turn back) | dom_fallback (nothing landed; read off the screen, plain text, links only)
      isolation: f.isolation || null, // was this question asked in a brand-new temporary chat, and what showed it (runner.js isolationFor)
      domSources: f.domSources || null, // audit only (run config.auditSources): what the page itself shows as sources
      userAgent: (globalThis.navigator && navigator.userAgent) || null,
      extensionVersion: extVersion(),
    };
  }
  Probe.record = { SCHEMA_VERSION, build, uuid };
})();
