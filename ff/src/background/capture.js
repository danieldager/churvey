// Network capture: tee streamed response bodies for provider chat endpoints via
// Firefox's webRequest.filterResponseData (the capability Chrome MV3 lacks).
// In discovery mode we record every POST JSON/SSE response on provider hosts so
// we can identify the real completion endpoint + format and write exact parsers.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("capture");

  let onCapture = () => {};

  // Completion streams that are still OPEN, by requestId. Gemini holds its
  // StreamGenerate connection open long past the finished, visible answer
  // (measured 2026-09-15: 120.4s for an answer that was on screen in ~4s), and
  // capture used to deliver only at filter.onstop — so the item burned the whole
  // 90s timeout with its answer on screen. flush() hands over what has arrived so
  // far, on demand, without touching the still-open connection.
  const live = new Map(); // requestId -> {details, provider, ct, chunks, bytes, openedAt, delivered}

  // Deliver the bytes buffered so far. Safe to call while the stream is open:
  // the chunks are copied, the filter keeps writing through to the page, and
  // `delivered` stops onstop from recording the same answer twice.
  function deliver(e) {
    if (e.delivered) return false;
    e.delivered = true;
    let text = ""; try { text = new TextDecoder("utf-8").decode(concat(e.chunks)); } catch (_) {}
    handle(e.details, e.provider, e.ct, text, e.bytes);
    return true;
  }

  // Flush the newest open completion stream on `tabId` that started at/after
  // `sinceMs` and has sent nothing for `quietMs`. Two independent guards against
  // handing over half an answer: `since` keeps a PREVIOUS turn's still-open stream
  // from being taken for this turn's, and `quiet` means the model has stopped
  // emitting — a pause long enough to fool BOTH this and the caller's DOM
  // stability check at the same time is what we are betting against.
  function flush(tabId, sinceMs = 0, quietMs = 2000) {
    const now = Date.now();
    let best = null;
    for (const e of live.values()) {
      if (e.details.tabId !== tabId || e.delivered || !e.chunks.length) continue;
      if (e.openedAt < sinceMs || now - e.lastDataAt < quietMs) continue;
      if (!best || e.openedAt > best.openedAt) best = e;
    }
    if (!best) return false;
    // Never burn the one delivery on an empty parse: if what has arrived does not
    // yet yield an answer, leave the stream alone and let onstop (or a later
    // flush) have it.
    let text = ""; try { text = new TextDecoder("utf-8").decode(concat(best.chunks)); } catch (_) {}
    if (!parseAnswer(best.provider.id, best.ct, text).text) return false;
    log.info(`[${best.provider.id}] flushing open stream ${best.details.requestId} at +${now - best.openedAt}ms (${best.chunks.length}chunks ${best.bytes}b, quiet ${now - best.lastDataAt}ms)`);
    return deliver(best);
  }

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

      const completion = isCompletion(provider, details.url);
      const t0 = Date.now();

      const filter = ext.webRequest.filterResponseData(details.requestId);
      const chunks = []; let bytes = 0;
      const entry = { details, provider, ct, chunks, bytes: 0, openedAt: t0, lastDataAt: t0, delivered: false };
      if (completion) live.set(details.requestId, entry);
      filter.ondata = (e) => {
        chunks.push(e.data); bytes += e.data.byteLength; entry.bytes = bytes; entry.lastDataAt = Date.now(); filter.write(e.data);
      };
      filter.onerror = () => { live.delete(details.requestId); log.warn("filter error", filter.error, details.url); };
      filter.onstop = () => {
        try { filter.disconnect(); } catch (_) {}
        live.delete(details.requestId);
        entry.bytes = bytes;
        deliver(entry); // no-op if a DOM-gated flush already handed it over
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
      raw: completion ? text.slice(0, 1000000) : undefined, // full-ish for matched endpoints (Grok/Gemini streams exceed 300KB)
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
    if (providerId === "chatgpt") {
      const t = parseChatgpt(text);
      if (t) return { text: t };
      // fall through to generic branches for non-stream (JSON error) bodies
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

  // ChatGPT: delta_encoding v1 — the stream builds message documents via ops.
  // The answer HEAD arrives inside an `o:"add"` message object, mid-answer chunks
  // arrive in `o:"patch"` batches (and bare-list batches), and only the remainder
  // is bare string `v` appends. The old generic parser kept just the bare appends,
  // silently dropping ~80% of long answers. This applies the ops faithfully.
  function parseChatgpt(text) {
    const roots = []; // completed message docs
    let root = null, lastPath = "";

    const navigate = (doc, tokens) => {
      let cur = doc;
      for (let i = 0; i < tokens.length - 1; i++) {
        const tok = tokens[i], nextIsIdx = /^\d+$/.test(tokens[i + 1]);
        if (Array.isArray(cur)) {
          const idx = +tok;
          while (cur.length <= idx) cur.push({});
          if (cur[idx] == null) cur[idx] = nextIsIdx ? [] : {};
          cur = cur[idx];
        } else {
          if (cur[tok] == null) cur[tok] = nextIsIdx ? [] : {};
          cur = cur[tok];
        }
      }
      return [cur, tokens[tokens.length - 1]];
    };
    const apply = (op, path, value) => {
      if (!path) {
        if (op === "add") { if (root !== null) roots.push(root); root = value; }
        else if (op === "replace") root = value;
        return;
      }
      if (root === null) root = {};
      const tokens = path.split("/").filter(Boolean);
      const [cont, key] = navigate(root, tokens);
      const k = Array.isArray(cont) ? +key : key;
      if (Array.isArray(cont)) while (cont.length <= k) cont.push(op === "append" ? "" : null);
      const old = cont[k];
      if (op === "append") {
        if (typeof old === "string" && typeof value === "string") cont[k] = old + value;
        else if (Array.isArray(old) && Array.isArray(value)) cont[k] = old.concat(value);
        else cont[k] = value;
      } else if (op === "add" || op === "replace") cont[k] = value;
    };
    const feed = (j) => {
      if (!j || typeof j !== "object") return;
      if (j.type && !("v" in j)) return; // control frames (markers, moderation, resume)
      const op = j.o, path = j.p, v = j.v;
      if (op === "patch" || (op == null && Array.isArray(v) && path == null)) {
        for (const sub of v) {
          if (!sub || typeof sub !== "object") continue;
          apply(sub.o || "append", sub.p || "", sub.v);
          if (sub.p) lastPath = sub.p;
        }
        return;
      }
      if (op == null && path == null) {
        if (typeof v === "string") apply("append", lastPath || "/message/content/parts/0", v);
        else if (v && typeof v === "object") { apply("add", "", v); lastPath = ""; }
        return;
      }
      if (path != null) lastPath = path;
      apply(op || "append", path || "", v);
    };

    for (const ln of text.split(/\r?\n/)) {
      const m = ln.match(/^data:\s?(.*)$/); if (!m) continue;
      const p = m[1].trim(); if (!p || p === "[DONE]") continue;
      let j; try { j = JSON.parse(p); } catch (_) { continue; }
      feed(j);
    }
    if (root !== null) roots.push(root);

    // Join text parts of assistant messages; prefer the last "final"-channel one.
    const texts = [];
    for (const r of roots) {
      const msg = r && r.message;
      if (!msg || !msg.author || msg.author.role !== "assistant") continue;
      const c = msg.content;
      if (!c || c.content_type !== "text" || !Array.isArray(c.parts)) continue;
      const t = c.parts.filter((x) => typeof x === "string").join("");
      if (t.trim()) texts.push({ channel: msg.channel, t });
    }
    if (!texts.length) return "";
    const finals = texts.filter((x) => x.channel == null || x.channel === "final");
    return (finals.length ? finals[finals.length - 1] : texts[texts.length - 1]).t;
  }

  // DeepSeek: SSE incremental-patch stream building a response document. Ops:
  // init {"v":{response:{...}}}, path ops {"p":"response/fragments/-1/content",
  // "o":"APPEND","v":"..."}, BATCH lists of sub-ops (these carry NEW fragments,
  // including the answer head), and bare {"v":"str"} continuations at the last
  // path. The old parser missed BATCH and mis-tracked the path, dropping heads.
  function parseDeepseek(text) {
    let root = {}, lastPath = null;
    const resolve = (tokens) => {
      let cur = root;
      for (let i = 0; i < tokens.length - 1; i++) {
        let tok = tokens[i];
        const nextIsIdx = /^-?\d+$/.test(tokens[i + 1]);
        if (Array.isArray(cur)) {
          let idx = tok === "-1" ? cur.length - 1 : +tok;
          while (cur.length <= idx) cur.push({});
          if (cur[idx] == null) cur[idx] = nextIsIdx ? [] : {};
          cur = cur[idx];
        } else {
          if (cur[tok] == null) cur[tok] = nextIsIdx ? [] : {};
          cur = cur[tok];
        }
      }
      return [cur, tokens[tokens.length - 1]];
    };
    const apply = (path, op, value) => {
      if (!path) { if (value && typeof value === "object" && !Array.isArray(value)) root = value; return; }
      const tokens = path.split("/").filter(Boolean);
      const [cont, key] = resolve(tokens);
      let k = key;
      if (Array.isArray(cont)) {
        k = key === "-1" ? cont.length - 1 : +key;
        while (cont.length <= k) cont.push(null);
      }
      const old = cont[k];
      if (op === "APPEND") {
        if (typeof old === "string" && typeof value === "string") cont[k] = old + value;
        else if (Array.isArray(old) && Array.isArray(value)) cont[k] = old.concat(value);
        else cont[k] = value;
      } else cont[k] = value; // SET / default
    };
    const feed = (j) => {
      if (!j || typeof j !== "object" || !("v" in j)) return;
      const path = j.p, op = j.o, v = j.v;
      if (op === "BATCH" && Array.isArray(v)) {
        for (const sub of v) {
          if (!sub || typeof sub !== "object" || !("v" in sub)) continue;
          const full = ((path || "") + "/" + (sub.p || "")).replace(/^\/|\/$/g, "");
          apply(full, sub.o || "SET", sub.v);
          if (typeof sub.v === "string") lastPath = full;
        }
        return;
      }
      if (path == null && op == null) {
        if (typeof v === "string" && lastPath) apply(lastPath, "APPEND", v);
        else if (v && typeof v === "object") { apply("", "SET", v); lastPath = null; }
        return;
      }
      apply(path || "", op || "SET", v);
      if (typeof v === "string" && path) lastPath = path;
    };
    for (const ln of text.split(/\r?\n/)) {
      const m = ln.match(/^data:\s?(.*)$/); if (!m) continue;
      const p = m[1].trim(); if (!p || p === "[DONE]") continue;
      let j; try { j = JSON.parse(p); } catch (_) { continue; }
      feed(j);
    }
    const resp = (root && root.response) || (root && root.fragments ? root : null);
    const frags = (resp && resp.fragments) || [];
    return frags.filter((f) => f && f.type === "RESPONSE" && typeof f.content === "string").map((f) => f.content).join("");
  }

  // Grok embeds UI widget markup inside the answer text — <grok:render> inline
  // citation cards and <xai:tool_usage_card> blocks. Neither is model prose, so
  // strip both from EVERY path. (The modelResponse.message path used to skip this
  // entirely: the render cards were ~36% of the captured characters.)
  function stripGrokMarkup(s) {
    return (s || "")
      .replace(/<grok:render[\s\S]*?<\/grok:render>/g, "")
      .replace(/<grok:render[^>]*\/>/g, "")
      .replace(/<xai:tool_usage_card>[\s\S]*?<\/xai:tool_usage_card>/g, "")
      .replace(/[ \t]{2,}/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  // Grok: NDJSON stream from conversations/new. The clean final answer is in
  // result.response.modelResponse.message; otherwise join streamed `token`s
  // (stripping the thinking blocks). Also detect errors.
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
    if (finalMsg) return { text: stripGrokMarkup(finalMsg) };
    if (err && !tokens.length) return { text: "", error: err };
    return { text: stripGrokMarkup(tokens.join("")) };
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

  Probe.capture = { start, parseAnswer, flush };
})();
