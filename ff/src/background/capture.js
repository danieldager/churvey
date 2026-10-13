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
  // Path + the batchexecute rpcids, which is what distinguishes Google endpoints.
  function shortUrl(url) {
    try { const u = new URL(url); return u.pathname + (u.searchParams.get("rpcids") ? "?rpcids=" + u.searchParams.get("rpcids") : ""); }
    catch (_) { return String(url).slice(0, 120); }
  }

  function onHeaders(details) {
    try {
      if (details.method !== "POST") return {};
      const ct = headerVal(details.responseHeaders, "content-type");
      if (!/event-stream|application\/json|text\/plain|ndjson|x-component|octet-stream/i.test(ct)) return {};
      const provider = Probe.providers.forUrl(details.url);
      if (!provider) return {};

      const completion = isCompletion(provider, details.url);
      // 2026-09-15: Gemini answers on screen in seconds yet items time out at 90s.
      // Capture only delivers at filter.onstop, so we need the shape of the stream
      // (when it starts, when its first byte lands, when it CLOSES) to tell a
      // held-open connection from a pairing race. Gemini-only: the ring is 300 lines.
      const trace = provider.id === "gemini";
      const t0 = Date.now();
      let firstAt = 0, nchunks = 0;
      if (trace) {
        log.info(`[gemini] stream OPEN ${details.requestId} ${completion ? "COMPLETION" : "other"} ${shortUrl(details.url)}`);
      }

      const filter = ext.webRequest.filterResponseData(details.requestId);
      const chunks = []; let bytes = 0;
      const entry = { details, provider, ct, chunks, bytes: 0, openedAt: t0, lastDataAt: t0, delivered: false };
      if (completion) live.set(details.requestId, entry);
      filter.ondata = (e) => {
        if (trace && !firstAt) { firstAt = Date.now(); log.info(`[gemini] stream FIRSTBYTE ${details.requestId} +${firstAt - t0}ms`); }
        nchunks++;
        chunks.push(e.data); bytes += e.data.byteLength; entry.bytes = bytes; entry.lastDataAt = Date.now(); filter.write(e.data);
      };
      filter.onerror = () => { live.delete(details.requestId); log.warn("filter error", filter.error, details.url); };
      filter.onstop = () => {
        try { filter.disconnect(); } catch (_) {}
        live.delete(details.requestId);
        if (trace) log.info(`[gemini] stream STOP ${details.requestId} +${Date.now() - t0}ms (first +${firstAt ? firstAt - t0 : -1}ms) ${nchunks}chunks ${bytes}b${entry.delivered ? " (already flushed)" : ""}`);
        entry.bytes = bytes;
        deliver(entry); // no-op if a DOM-gated flush already handed it over
      };
      return {};
    } catch (e) {
      log.error("onHeaders", e?.message || e);
      return {};
    }
  }

  function handle(details, provider, ct, text, bytes, method = "stream") {
    const completion = isCompletion(provider, details.url);
    const parsed = completion ? parseAnswer(provider.id, ct, text) : { text: "" };
    if (Probe.capture && Probe.capture.tap) { try { Probe.capture.tap(details, ct, text); } catch (_) {} }
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
      captureMethod: method, // stream (tee'd network body) | poll (page read the finished turn back)
      answer: parsed.text || null,
      answerLen: (parsed.text || "").length,
      error: parsed.error || null,
      model: completion ? sniffModel(provider.id, text) : null,
      sample: text.slice(0, 1500), // for discovery
      raw: completion ? text.slice(0, 2000000) : undefined, // full-ish for matched endpoints (Grok/Gemini streams exceed 300KB); persisted on the record
    });
  }

  function sniffModel(pid, text) {
    let m;
    if (pid === "claude") { m = text.match(/"model":"(claude[^"]+)"/); if (m) return m[1]; }
    if (pid === "chatgpt") { m = text.match(/"model_slug":"([^"]+)"/) || text.match(/"model":"(gpt[^"]+)"/i); if (m) return m[1]; }
    if (pid === "deepseek") { m = text.match(/"model":"([^"]+)"/); if (m) return m[1]; }
    return null;
  }

  // Mistral Le Chat: POST /api/chat answers as lines "<n>:{json}"; the interesting ones are
  // {"json":{"type":"message","messageId","patches":[{op,path,value}]}} -- RFC6902-ish patches
  // (add/replace/remove, plus "append" for string concat) against one state object per message.
  // The assistant message ends up with contentChunks (reasoning chunks carry _context.type
  // "reasoning", tool_call chunks the search) and citedSources [{id,title,url,description}].
  // The model writes citations as markdown links; mid-stream they are "search-result://<id>".
  function mistralMessages(text) {
    const msgs = {};
    for (const ln of text.split(/\r?\n/)) {
      const m = /^\d+:(.*)$/.exec(ln); if (!m) continue;
      let o; try { o = JSON.parse(m[1]); } catch (_) { continue; }
      const j = o && o.json;
      if (!j || j.type !== "message" || !Array.isArray(j.patches)) continue;
      const st = (msgs[j.messageId] ||= {});
      for (const p of j.patches) {
        try {
          if (p.path === "/") { for (const k of Object.keys(st)) delete st[k]; Object.assign(st, p.value); continue; }
          const keys = p.path.split("/").slice(1);
          let cur = st;
          for (const k of keys.slice(0, -1)) cur = cur[k];
          const k = keys[keys.length - 1];
          if (Array.isArray(cur)) {
            const i = +k;
            if (p.op === "add") cur.splice(i, 0, p.value);
            else if (p.op === "replace") cur[i] = p.value;
            else if (p.op === "remove") cur.splice(i, 1);
            else if (p.op === "append") cur[i] += p.value;
          } else if (p.op === "add" || p.op === "replace") cur[k] = p.value;
          else if (p.op === "remove") delete cur[k];
          else if (p.op === "append") cur[k] = (cur[k] || "") + p.value;
        } catch (_) {}
      }
    }
    return Object.values(msgs).filter((m) => m.role === "assistant");
  }
  // The visible answer: top-level text chunks that are not the reasoning trace, with any
  // still-unresolved search-result://<id> link target swapped for the cited source's URL.
  function mistralAnswer(msg) {
    const src = {}; for (const s of msg.citedSources || []) if (s && s.id) src[s.id] = s.url;
    return (msg.contentChunks || [])
      .filter((c) => c && c.type === "text" && !(c._context && c._context.type === "reasoning"))
      .map((c) => c.text || "").join("")
      .replace(/search-result:\/\/([A-Za-z0-9_-]+)/g, (m, id) => src[id] || m);
  }
  function parseMistral(text) {
    const msgs = mistralMessages(text);
    const best = msgs.map((m) => ({ m, t: mistralAnswer(m) })).sort((a, b) => b.t.length - a.t.length)[0];
    if (best && best.t.trim()) return { text: best.t.trim() };
    if (text.length < 4000) { const e = /"(?:message|error)":"([^"]{5,200})"/.exec(text); if (e) return { text: "", error: e[1] }; }
    return { text: "" };
  }

  // claude.ai (polled): the assistant message of GET chat_conversations/<id>, wrapped by deliverClaude.
  // The answer is its text blocks only (thinking and tool blocks are not prose); Probe.citations owns the
  // block join so the citation offsets index exactly this string.
  function parseClaudeConv(text) {
    try {
      const o = JSON.parse(text).__probe_claude;
      const t = Probe.citations.claudeJoin(o.message.content).text;
      return t.trim() ? { text: t } : { text: "" };
    } catch (_) { return { text: "" }; }
  }

  // Provider-aware extraction (formats confirmed from discovery).
  function parseAnswer(providerId, ct, text) {
    if (providerId === "claude" && text.startsWith('{"__probe_claude"')) return parseClaudeConv(text);
    if (providerId === "mistral") return parseMistral(text);
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
  // Since 2026-10 the stream multiplexes message docs: an event's `c` is the slot (doc) it edits, an event
  // without `c` edits the slot of the event before. A searched answer arrives as segment messages (the prose
  // between two searches) plus one model_dil_v2 message that receives the same text, segment after segment,
  // so it holds the whole answer. Applying every op to the newest doc wrote the last segment twice,
  // chunk-interleaved, and lost the earlier segments. The text comes back with its UI markup removed
  // (Probe.citations.dilClean, the same cleaning the citation offsets are computed on).
  function parseChatgpt(text) {
    const docs = []; // {doc, lastPath} per message doc, in order of creation
    const slots = new Map(); // c -> its entry in docs
    let cur = null, slot = null;
    const start = (doc) => { cur = { doc, lastPath: "" }; docs.push(cur); if (slot != null) slots.set(slot, cur); };

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
        if (op === "add") start(value);
        else if (op === "replace") { if (cur) cur.doc = value; else start(value); }
        return;
      }
      if (cur === null) start({});
      const tokens = path.split("/").filter(Boolean);
      const [cont, key] = navigate(cur.doc, tokens);
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
      if (j.c != null && j.c !== slot) { slot = j.c; cur = slots.get(slot) || null; }
      const op = j.o, path = j.p, v = j.v;
      if (op === "patch" || (op == null && Array.isArray(v) && path == null)) {
        for (const sub of v) {
          if (!sub || typeof sub !== "object") continue;
          apply(sub.o || "append", sub.p || "", sub.v);
          if (sub.p) cur.lastPath = sub.p;
        }
        return;
      }
      if (op == null && path == null) {
        if (typeof v === "string") apply("append", (cur && cur.lastPath) || "/message/content/parts/0", v);
        else if (v && typeof v === "object") apply("add", "", v);
        return;
      }
      apply(op || "append", path || "", v);
      if (path) cur.lastPath = path;
    };

    for (const ln of text.split(/\r?\n/)) {
      const m = ln.match(/^data:\s?(.*)$/); if (!m) continue;
      const p = m[1].trim(); if (!p || p === "[DONE]") continue;
      let j; try { j = JSON.parse(p); } catch (_) { continue; }
      feed(j);
    }

    // The answer = the longest final-channel assistant text (the model_dil_v2 message when the answer
    // has segments), else the longest assistant text.
    const texts = [];
    for (const { doc: r } of docs) {
      const msg = r && r.message;
      if (!msg || !msg.author || msg.author.role !== "assistant") continue;
      const c = msg.content;
      if (!c || c.content_type !== "text" || !Array.isArray(c.parts)) continue;
      const t = c.parts.filter((x) => typeof x === "string").join("");
      if (t.trim()) texts.push({ channel: msg.channel, t });
    }
    if (!texts.length) return "";
    const finals = texts.filter((x) => x.channel == null || x.channel === "final");
    const best = (finals.length ? finals : texts).reduce((a, b) => (b.t.length >= a.t.length ? b : a));
    return Probe.citations.dilClean(best.t).text;
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

  // grok.com: the answer travels over a websocket, so the only HTTP trace of a chat is the page's own
  // GETs of /rest/app-chat/conversations[_v2]/<id>. The newest id seen per tab is the current chat
  // (a fresh private chat fetches its id before the question is typed).
  const grokConv = new Map(); // tabId -> {id, at}
  const GROK_CONV_RE = /\/rest\/app-chat\/conversations(?:_v2)?\/([0-9a-f]{8}-[0-9a-f-]{27})/;
  function noteGrokConv(d) {
    const m = GROK_CONV_RE.exec(d.url);
    if (m && d.tabId >= 0) grokConv.set(d.tabId, { id: m[1], at: Date.now() });
    return {};
  }
  // Hand a conversation read back by the runner to the normal pairing path, as if it were the old
  // NDJSON stream: one line holding the assistant message under result.response.modelResponse.
  function deliverGrok(tabId, convId, response) {
    const text = JSON.stringify({ result: { response: { modelResponse: response } } }) + "\n";
    const provider = Probe.providers.byId("grok");
    handle({ tabId, url: `https://grok.com/rest/app-chat/conversations/${convId}/__probe_grok_synth__`, method: "POST", statusCode: 200, requestId: "grok-synth" },
      provider, "application/x-ndjson", text, text.length, "poll");
  }

  // claude.ai: same idea as grok. `response` = {convId, model, message} read back by the page.
  function deliverClaude(tabId, response) {
    const text = JSON.stringify({ __probe_claude: response });
    const provider = Probe.providers.byId("claude");
    handle({ tabId, url: `https://claude.ai/api/__probe_claude_synth__/${response.convId}`, method: "POST", statusCode: 200, requestId: "claude-synth" },
      provider, "application/json", text, text.length, "poll");
  }

  function start(cb) {
    onCapture = cb || (() => {});
    ext.webRequest.onBeforeRequest.addListener(noteGrokConv, { urls: ["https://grok.com/rest/app-chat/conversations*"] });
    ext.webRequest.onHeadersReceived.addListener(
      onHeaders,
      { urls: Probe.providers.allMatchPatterns() },
      ["blocking", "responseHeaders"]
    );
    log.info("network capture armed for", Probe.providers.allMatchPatterns().join(", "));
  }

  Probe.capture = { start, parseAnswer, flush, tap: null, mistralMessages, mistralAnswer, grokConvId: (tabId) => (grokConv.get(tabId) || {}).id || null, deliverGrok, deliverClaude };
})();
