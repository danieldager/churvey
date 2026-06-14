// Network capture: tee streamed response bodies for provider chat endpoints via
// Firefox's webRequest.filterResponseData (the capability Chrome MV3 lacks).
// In discovery mode we record every POST JSON/SSE response on provider hosts so
// we can identify the real completion endpoint + format and write exact parsers.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("capture");

  let onCapture = () => {};

  function headerVal(headers, name) {
    const h = (headers || []).find((x) => x.name.toLowerCase() === name);
    return h ? h.value : "";
  }
  function concat(chunks) {
    let len = 0; for (const c of chunks) len += c.byteLength;
    const out = new Uint8Array(len); let o = 0;
    for (const c of chunks) { out.set(new Uint8Array(c), o); o += c.byteLength; }
    return out;
  }
  function isCompletion(provider, url) {
    try { return new RegExp(provider.completionHint, "i").test(url); } catch (_) { return false; }
  }

  function onHeaders(details) {
    try {
      if (details.method !== "POST") return {};
      const ct = headerVal(details.responseHeaders, "content-type");
      if (!/event-stream|application\/json|text\/plain|ndjson/i.test(ct)) return {};
      const provider = Probe.providers.forUrl(details.url);
      if (!provider) return {};

      const filter = ext.webRequest.filterResponseData(details.requestId);
      const chunks = []; let bytes = 0;
      filter.ondata = (e) => { chunks.push(e.data); bytes += e.data.byteLength; filter.write(e.data); };
      filter.onerror = () => { log.warn("filter error", filter.error, details.url); };
      filter.onstop = () => {
        try { filter.disconnect(); } catch (_) {}
        let text = ""; try { text = new TextDecoder("utf-8").decode(concat(chunks)); } catch (_) {}
        handle(details, provider, ct, text, bytes);
      };
      return {};
    } catch (e) {
      log.error("onHeaders", e?.message || e);
      return {};
    }
  }

  function handle(details, provider, ct, text, bytes) {
    const completion = isCompletion(provider, details.url);
    const parsed = completion ? parseAnswer(provider.id, ct, text) : { text: "" };
    onCapture({
      provider: provider.id,
      tabId: details.tabId,
      url: details.url,
      method: details.method,
      status: details.statusCode,
      contentType: ct,
      bytes,
      ts: new Date().toISOString(),
      completion,
      answer: parsed.text || null,
      answerLen: (parsed.text || "").length,
      error: parsed.error || null,
      model: completion ? sniffModel(provider.id, text) : null,
      sample: text.slice(0, 1500), // for discovery
      raw: completion ? text.slice(0, 300000) : undefined, // full-ish for matched endpoints
    });
  }

  function sniffModel(pid, text) {
    let m;
    if (pid === "claude") { m = text.match(/"model":"(claude[^"]+)"/); if (m) return m[1]; }
    if (pid === "chatgpt") { m = text.match(/"model_slug":"([^"]+)"/) || text.match(/"model":"(gpt[^"]+)"/i); if (m) return m[1]; }
    if (pid === "deepseek") { m = text.match(/"model":"([^"]+)"/); if (m) return m[1]; }
    return null;
  }

  // Provider-aware extraction (formats confirmed from discovery).
  function parseAnswer(providerId, ct, text) {
    if (providerId === "gemini") {
      return { text: parseGemini(text) };
    }
    if (providerId === "grok") {
      return parseGrok(text); // {text, error}
    }
    if (providerId === "deepseek") {
      return { text: parseDeepseek(text) };
    }

    // SSE providers (ChatGPT, Claude, DeepSeek, and Grok when it streams).
    if (/event-stream/i.test(ct) || /^data:/m.test(text)) {
      const out = [];
      for (const ln of text.split(/\r?\n/)) {
        const m = ln.match(/^data:\s?(.*)$/);
        if (!m) continue;
        const p = m[1].trim();
        if (!p || p === "[DONE]") continue;
        let j;
        try { j = JSON.parse(p); } catch (_) { continue; }
        let piece = "";
        if (j.delta) {
          // Claude: only the "text" block (skip "thinking").
          if (j.delta.type === "text_delta" && typeof j.delta.text === "string") piece = j.delta.text;
          else if (typeof j.delta.content === "string") piece = j.delta.content;
        }
        if (!piece && typeof j.completion === "string") piece = j.completion;
        if (!piece && typeof j.v === "string") piece = j.v; // ChatGPT delta op
        if (!piece && j.message && j.message.content && Array.isArray(j.message.content.parts)) {
          piece = j.message.content.parts.join(""); // ChatGPT full message
        }
        if (!piece && j.choices && j.choices[0] && j.choices[0].delta && typeof j.choices[0].delta.content === "string") {
          piece = j.choices[0].delta.content;
        }
        if (piece) out.push(piece);
      }
      if (out.length) return { text: out.join("") };
    }

    // Plain JSON (errors / non-streamed answers).
    try {
      const j = JSON.parse(text);
      if (j && j.error && j.error.message) return { text: "", error: j.error.message };
      const t = j.text || j.completion || (j.message && j.message.content) ||
        (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content);
      if (typeof t === "string") return { text: t };
    } catch (_) {}
    return { text: "" };
  }

  // DeepSeek: SSE incremental-patch stream. The opening text is in the initial
  // response object's RESPONSE fragment(s); the rest arrives as string `v` APPEND
  // deltas. The generic parser only saw the deltas (dropping the first fragment).
  function parseDeepseek(text) {
    let out = "", gotInit = false, curPath = "";
    for (const ln of text.split(/\r?\n/)) {
      const m = ln.match(/^data:\s?(.*)$/); if (!m) continue;
      const p = m[1].trim(); if (!p || p === "[DONE]") continue;
      let j; try { j = JSON.parse(p); } catch (_) { continue; }
      if (typeof j.p === "string") curPath = j.p; // patches set the active path
      if (typeof j.v === "string") {
        // Only the answer text — content deltas (and their path-less continuations).
        // Skips control deltas like response/status = "FINISHED".
        if (curPath.includes("content")) out += j.v;
      } else if (!gotInit && j.v && j.v.response && Array.isArray(j.v.response.fragments)) {
        gotInit = true;
        for (const f of j.v.response.fragments) if (f && f.type === "RESPONSE" && typeof f.content === "string") out += f.content;
      }
    }
    return out;
  }

  // Grok: NDJSON stream from conversations/new. The clean final answer is in
  // result.response.modelResponse.message; otherwise join streamed `token`s
  // (stripping the thinking + <xai:tool_usage_card> blocks). Also detect errors.
  function parseGrok(text) {
    let finalMsg = "", tokens = [], err = null;
    for (const ln of text.split(/\r?\n/)) {
      const s = ln.trim(); if (!s) continue;
      let o; try { o = JSON.parse(s); } catch (_) { continue; }
      if (o.error && o.error.message) { err = o.error.message; continue; }
      const r = (o.result && o.result.response) || {};
      if (r.modelResponse && typeof r.modelResponse.message === "string") finalMsg = r.modelResponse.message;
      else if (typeof r.token === "string") tokens.push(r.token);
    }
    if (finalMsg) return { text: finalMsg };
    if (err && !tokens.length) return { text: "", error: err };
    const joined = tokens.join("").replace(/<xai:tool_usage_card>[\s\S]*?<\/xai:tool_usage_card>/g, "");
    return { text: joined.trim() };
  }

  // Gemini: strip )]}' guard, then each length-prefixed line is an array
  // [["wrb.fr", null, "<stringified inner>"]]. The answer lives in rc_ blocks as
  // GROWING full-text snapshots, so we take the longest one found.
  function parseGemini(text) {
    let best = "";
    for (const ln of text.split(/\r?\n/)) {
      const s = ln.trim();
      if (!s.startsWith("[")) continue;
      let outer;
      try { outer = JSON.parse(s); } catch (_) { continue; }
      for (const row of Array.isArray(outer) ? outer : []) {
        if (!Array.isArray(row) || row[0] !== "wrb.fr" || typeof row[2] !== "string") continue;
        let inner;
        try { inner = JSON.parse(row[2]); } catch (_) { continue; }
        for (const t of collectRc(inner)) if (t.length > best.length) best = t;
      }
    }
    return best;
  }
  function collectRc(node, out) {
    out = out || [];
    if (Array.isArray(node)) {
      if (typeof node[0] === "string" && node[0].startsWith("rc_") && Array.isArray(node[1]) && typeof node[1][0] === "string") {
        out.push(node[1][0]);
      }
      for (const x of node) collectRc(x, out);
    }
    return out;
  }

  function start(cb) {
    onCapture = cb || (() => {});
    ext.webRequest.onHeadersReceived.addListener(
      onHeaders,
      { urls: Probe.providers.allMatchPatterns() },
      ["blocking", "responseHeaders"]
    );
    log.info("network capture armed for", Probe.providers.allMatchPatterns().join(", "));
  }

  Probe.capture = { start, parseAnswer };
})();
