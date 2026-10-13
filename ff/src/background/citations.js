// Displayed citations, parsed per provider from the raw completion stream.
//
// parse(pid, raw, answer) -> one entry per (source, place it is attached):
//   { url, title, domain, site_name, cited_text,   // the source: cited_text = its snippet, when the provider sends one
//     anchor_text, anchor_start, anchor_end,        // the answer segment the citation supports, and its offsets in `text` below
//     marker, ref_id, char_offset, via }            // ChatGPT marker (cite...), provider ref id, = anchor_end, where it came from
// "Displayed" = what the chat UI shows as a citation (Gemini source chips, Claude inline
// chips, ChatGPT cite markers + its Sources list). The search-result pool the model
// retrieved but did not cite is NOT here; it stays in record.fetchedUrls.
// Offsets index the provider's own text (`text_of`, returned as parse.lastText), which
// equals the recorded responseText whenever `anchor_text` is found there verbatim.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const domainOf = (u) => { const m = /^https?:\/\/([^\/?#:]+)/i.exec(u || ""); return m ? m[1].toLowerCase().replace(/^www\./, "") : null; };
  // THE place URLs are normalised on the ff/ side: drop the #fragment (Gemini's "#:~:text=" scroll
  // directives, any anchor) and tracking params (utm_*, gclid, fbclid, ...), so a cited URL equals
  // the page that was fetched / cached. No re-encoding. The Python twin is dashboard/ingest/url_canon.py
  // (the authority at ingest; keep the two lists in step).
  const TRACK_RE = /^(utm_|mc_(cid|eid)$|_ga$|_gl$|gclid$|dclid$|fbclid$|msclkid$|yclid$|igshid$|srsltid$|ocid$)/i;
  function canon(u) {
    if (!u) return u;
    let s = String(u); const h = s.indexOf("#"); if (h >= 0) s = s.slice(0, h);
    const q = s.indexOf("?"); if (q < 0) return s;
    const kept = s.slice(q + 1).split("&").filter((kv) => kv && !TRACK_RE.test(kv.split("=")[0]));
    return s.slice(0, q) + (kept.length ? "?" + kept.join("&") : "");
  }
  const clean = canon;
  const mk = (o) => ({
    url: canon(o.url) || null, title: o.title || null, domain: o.url ? domainOf(o.url) : null, site_name: o.site_name || null,
    cited_text: o.cited_text || null, anchor_text: o.anchor_text || null,
    anchor_start: o.anchor_start ?? null, anchor_end: o.anchor_end ?? null,
    marker: o.marker || null, ref_id: o.ref_id ?? null, char_offset: o.anchor_end ?? null, via: o.via,
  });

  // The segment a citation placed at `pos` supports: back to the previous citation on
  // this line, or the start of the line, minus list bullets / heading hashes.
  function segmentBefore(text, pos, floor) {
    const nl = text.lastIndexOf("\n", pos - 1) + 1;
    let s = Math.max(nl, floor || 0);
    const m = /^[\s>*\-•#]+/.exec(text.slice(s, pos));
    if (m) s += m[0].length;
    return { start: s, end: pos, text: text.slice(s, pos).trim() };
  }

  // SSE: "event: x\ndata: {...}" blocks -> [{event, data}] (data parsed when JSON).
  function sse(raw) {
    const out = [];
    for (const blk of String(raw).split(/\r?\n\r?\n/)) {
      let event = null; const data = [];
      for (const l of blk.split(/\r?\n/)) {
        if (l.startsWith("event:")) event = l.slice(6).trim();
        else if (l.startsWith("data:")) data.push(l.slice(5).replace(/^ /, ""));
      }
      if (!data.length) continue;
      const s = data.join("\n");
      let d = s; try { d = JSON.parse(s); } catch (_) {}
      out.push({ event, data: d });
    }
    return out;
  }

  // ---- Claude: citation_start_delta / citation_end_delta wrap the text they cite -------
  function claude(raw) {
    let text = "", prevEnd = 0, lastSeg = null; const blocks = {}, open = {}, out = [];
    for (const { data: d } of sse(raw)) {
      if (!d || typeof d !== "object") continue;
      if (d.type === "content_block_start") blocks[d.index] = d.content_block && d.content_block.type;
      else if (d.type === "content_block_delta" && blocks[d.index] === "text" && d.delta) {
        const dl = d.delta;
        if (dl.type === "text_delta") text += dl.text || "";
        else if (dl.type === "citation_start_delta" && dl.citation) open[dl.citation.uuid] = { c: dl.citation, at: text.length };
        else if (dl.type === "citation_end_delta") {
          const o = open[dl.citation_uuid]; if (!o) continue;
          delete open[dl.citation_uuid];
          // Text between start and end is the cited span; an empty span is a chip placed
          // after the text before it (the usual case), so take the segment behind it.
          const seg = o.at < text.length ? { start: o.at, end: text.length, text: text.slice(o.at).trim() } : segmentBefore(text, text.length, prevEnd);
          prevEnd = text.length;
          // Second chip on the same spot: same segment as the chip before it.
          if (!seg.text && lastSeg && lastSeg.end === seg.end) Object.assign(seg, lastSeg); else lastSeg = seg;
          const srcs = Array.isArray(o.c.sources) && o.c.sources.length ? o.c.sources : [o.c];
          const md = o.c.metadata || {};
          for (const s of srcs) {
            out.push(mk({ url: s.url, title: s.title, site_name: s.source || md.site_name || null, cited_text: null,
                          anchor_text: seg.text, anchor_start: seg.start, anchor_end: seg.end, ref_id: o.c.uuid, via: "claude_inline" }));
          }
        }
      }
    }
    return { entries: out, text };
  }

  // ---- ChatGPT: delta-encoded SSE; cite markers in the text, URLs in search_result_groups ----
  function setPath(root, path, op, v) {
    const keys = path.split("/").slice(1).map((k) => k.replace(/~1/g, "/").replace(/~0/g, "~"));
    let cur = root;
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i];
      if (cur[k] == null || typeof cur[k] !== "object") cur[k] = /^\d+$/.test(keys[i + 1]) ? [] : {};
      cur = cur[k];
    }
    const k = keys[keys.length - 1], old = cur[k];
    if (op === "remove") { if (Array.isArray(cur)) cur.splice(+k, 1); else delete cur[k]; return; }
    if (op === "append" && old != null) {
      if (typeof old === "string") cur[k] = old + v;
      else if (Array.isArray(old)) Array.isArray(v) ? old.push(...v) : old.push(v);
      else if (typeof old === "object" && v && typeof v === "object") Object.assign(old, v);
      else cur[k] = v;
    } else cur[k] = v;
  }
  function chatgptMessages(raw) {
    const msgs = []; let cur = null, lastP = "", lastO = "";
    const apply = (op) => { if (cur && op && typeof op.p === "string" && op.p) { try { setPath(cur, op.p, op.o, op.v); } catch (_) {} } };
    for (const { data: d } of sse(raw)) {
      if (!d || typeof d !== "object" || !("v" in d)) continue;
      if (typeof d.p === "string") lastP = d.p;
      if (typeof d.o === "string") lastO = d.o;
      const v = d.v;
      if (v && typeof v === "object" && !Array.isArray(v) && v.message) { cur = { message: v.message }; msgs.push(cur); }
      else if (Array.isArray(v)) v.forEach((op) => { if (op && op.p != null) apply(op); });
      else if (typeof v === "string") apply({ p: lastP, o: lastO || "append", v });
    }
    return msgs;
  }
  const MARKER_RE = /cite((?:turn\d+[a-z]+\d+)+)/g;
  const REF_RE = /turn(\d+)([a-z]+)(\d+)/g;
  function chatgpt(raw) {
    const msgs = chatgptMessages(raw);
    const pool = {}; // "turn:type:index" -> {url,title,attribution,snippet}
    for (const m of msgs) {
      const groups = m.message.metadata && m.message.metadata.search_result_groups;
      for (const g of groups || []) for (const e of g.entries || []) {
        const r = e.ref_id; if (!r || !e.url) continue;
        pool[`${r.turn_index}:${r.ref_type}:${r.ref_index}`] = { url: clean(e.url), title: e.title || null, site: e.attribution || g.domain || null, snippet: e.snippet || null };
      }
    }
    const asst = msgs.filter((m) => m.message.author && m.message.author.role === "assistant" && m.message.content && m.message.content.content_type === "text");
    const fin = asst.filter((m) => m.message.channel === "final");
    const cand = (fin.length ? fin : asst).sort((a, b) => partsText(b).length - partsText(a).length)[0];
    if (!cand) return { entries: [], text: "" };
    const text = partsText(cand), out = [];
    const meta = cand.message.metadata || {}, crefs = meta.content_references || [];
    // Streams whose search_result_groups omit some refs: the grouped_webpages items carry them
    // (item.refs[0] = the item itself, further refs = its supporting_websites in order).
    for (const c of crefs) for (const it of c.items || []) {
      const flat = [it, ...(it.supporting_websites || [])];
      (it.refs || []).forEach((r, i) => {
        const k = `${r.turn_index}:${r.ref_type}:${r.ref_index}`, f = flat[i];
        if (!pool[k] && f && f.url) pool[k] = { url: clean(f.url), title: f.title || null, site: f.attribution || null, snippet: f.snippet || null };
      });
    }
    let prevEnd = 0;
    for (const m of text.matchAll(MARKER_RE)) {
      const seg = segmentBefore(text, m.index, prevEnd); prevEnd = m.index + m[0].length;
      for (const r of m[1].matchAll(REF_RE)) {
        const hit = pool[`${r[1]}:${r[2]}:${r[3]}`];
        out.push(mk({ url: hit && hit.url, title: hit && hit.title, site_name: hit && hit.site, cited_text: hit && hit.snippet,
                      anchor_text: seg.text, anchor_start: seg.start, anchor_end: seg.end, marker: r[0], ref_id: `${r[1]}:${r[2]}:${r[3]}`, via: "chatgpt_marker" }));
      }
    }
    // The Sources list ChatGPT prints under the answer.
    for (const c of crefs) if (c.type === "sources_footnote") for (const s of c.sources || []) {
      out.push(mk({ url: clean(s.url), title: s.title, site_name: s.attribution, via: "chatgpt_sources_list" }));
    }
    return { entries: out, text };
  }
  const partsText = (m) => ((m.message.content && m.message.content.parts) || []).filter((p) => typeof p === "string").join("");

  // ---- Gemini: StreamGenerate chunks; per-segment grounding [[text,..,[[s,e]..]], .., [[url,title,icon,snippet,..,site]], "spp_.."] ----
  function geminiChunks(raw) {
    const out = [];
    for (const line of String(raw).split("\n")) {
      const t = line.trim(); if (!t.startsWith("[[")) continue;
      let a; try { a = JSON.parse(t); } catch (_) { continue; }
      for (const it of a) if (Array.isArray(it) && it[0] === "wrb.fr" && typeof it[2] === "string") { try { out.push(JSON.parse(it[2])); } catch (_) {} }
    }
    return out;
  }
  function gemini(raw) {
    const chunks = geminiChunks(raw);
    let text = "";
    for (const c of chunks) { const t = c && c[4] && c[4][0] && c[4][0][1] && c[4][0][1][0]; if (typeof t === "string" && t.length >= text.length) text = t; }
    const groups = new Map();
    const walk = (x, depth) => {
      if (!Array.isArray(x) || depth > 14) return;
      if (typeof x[3] === "string" && x[3].startsWith("spp_") && Array.isArray(x[2]) && Array.isArray(x[0]) && typeof x[0][0] === "string") groups.set(x[3], x);
      else for (const y of x) walk(y, depth + 1);
    };
    for (const c of chunks) walk(c, 0);
    const out = [];
    for (const g of groups.values()) {
      const off = g[0][3] && g[0][3][0], s = off ? off[0] : null, e = off ? off[1] : null;
      // Real offsets when the segment sits at them in the text; else find it by content.
      let start = s, end = e;
      if (typeof s !== "number" || text.slice(s, e).trim() !== g[0][0].trim()) { const i = text.indexOf(g[0][0]); start = i < 0 ? s : i; end = i < 0 ? e : i + g[0][0].length; }
      for (const src of g[2]) {
        if (!Array.isArray(src) || typeof src[0] !== "string" || !/^https?:/.test(src[0])) continue;
        out.push(mk({ url: src[0], title: src[1], cited_text: typeof src[3] === "string" ? src[3] : null, site_name: typeof src[6] === "string" ? src[6] : null,
                      anchor_text: g[0][0], anchor_start: start, anchor_end: end, ref_id: g[3], via: "gemini_grounding" }));
      }
    }
    out.sort((a, b) => (a.anchor_start ?? 1e9) - (b.anchor_start ?? 1e9));
    // Answers Gemini wrote without per-segment grounding (searched, then answered from memory of
    // the results: 5 of 33 searched answers on 2026-09-30) stream NO grounding, only the
    // "Searched the web" panel: [favicon, url, title, null, []] per result. Those results are the
    // only sources the stream carries for that answer, so keep them, answer-level (no anchor),
    // and only when there is no grounding (otherwise they are the retrieval pool, record.fetchedUrls).
    if (!out.length) {
      const seen = new Set();
      const panel = (x, depth) => {
        if (!Array.isArray(x) || depth > 14) return;
        if (x.length >= 3 && typeof x[0] === "string" && /gstatic\.com\/faviconV2/.test(x[0]) && typeof x[1] === "string" && /^https?:/.test(x[1])) {
          if (!seen.has(x[1])) { seen.add(x[1]); out.push(mk({ url: x[1], title: typeof x[2] === "string" ? x[2] : null, via: "gemini_search_panel" })); }
        } else for (const y of x) panel(y, depth + 1);
      };
      for (const c of chunks) panel(c, 0);
    }
    return { entries: out, text };
  }

  // ---- Grok (grok.com): NDJSON; the final modelResponse.message carries <grok:render card_id=..
  // type="render_inline_citation"> tags after the sentence they support, and cardAttachmentsJson maps
  // card_id -> url (citation_id is an index into another list and does not match: use the card).
  // Answers without a search carry no tags. webSearchResults (the pool) stays in fetchedUrls.
  function grok(raw, answer) {
    let m = null;
    for (const ln of String(raw).split(/\r?\n/)) {
      const t = ln.trim(); if (!t) continue;
      let o; try { o = JSON.parse(t); } catch (_) { continue; }
      const r = o && o.result && o.result.response;
      if (r && r.modelResponse && typeof r.modelResponse.message === "string") m = r.modelResponse;
    }
    if (!m) return { entries: [], text: answer || "" };
    const cards = {};
    for (const c of m.cardAttachmentsJson || []) { try { const j = typeof c === "string" ? JSON.parse(c) : c; if (j && j.id) cards[j.id] = j; } catch (_) {} }
    // Message with each tag replaced by a private-use mark; the segment before a mark is what it supports.
    const TAG = /<grok:render\b[^>]*?card_id="(\w+)"[^>]*>[\s\S]*?<\/grok:render>/g;
    const ids = []; let msg = m.message.replace(TAG, (_, id) => { ids.push(id); return "\ue000"; })
      .replace(/<grok:render[\s\S]*?<\/grok:render>/g, "").replace(/<xai:tool_usage_card>[\s\S]*?<\/xai:tool_usage_card>/g, "")
      .replace(/[ \t]{2,}/g, " ").replace(/\n{3,}/g, "\n\n").trim();
    const text = answer || msg.replace(/\ue000/g, "");
    const out = []; let k = 0, prevEnd = 0, lastSeg = null;
    for (let i = msg.indexOf("\ue000"); i >= 0; i = msg.indexOf("\ue000", i + 1), k++) {
      const before = msg.slice(0, i).replace(/\ue000/g, "");
      let seg = segmentBefore(before, before.length, 0);
      if (seg.text) {   // offsets in the recorded answer, found by content (the tags were stripped from it)
        const at = text.indexOf(seg.text, Math.max(0, prevEnd - 5));
        seg = at >= 0 ? { start: at, end: at + seg.text.length, text: seg.text } : { start: null, end: null, text: seg.text };
        lastSeg = seg; if (at >= 0) prevEnd = seg.end;
      } else if (lastSeg) seg = lastSeg;   // second tag on the same spot
      const c = cards[ids[k]]; if (!c || !c.url) continue;
      out.push(mk({ url: c.url, title: c.title || null, anchor_text: seg.text, anchor_start: seg.start, anchor_end: seg.end, ref_id: ids[k], via: "grok_inline" }));
    }
    return { entries: out, text };
  }

  // ---- Mistral: the model writes [label](url) after the sentence it supports; citedSources
  // (id,title,url,description) is the list the UI shows. Anchor = the sentence/clause before the link.
  const stripHtml = (t) => t ? String(t).replace(/<[^>]+>/g, "").replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim() : null;
  function mistral(raw) {
    const msgs = Probe.capture.mistralMessages(raw).sort((a, b) => Probe.capture.mistralAnswer(b).length - Probe.capture.mistralAnswer(a).length);
    const msg = msgs[0]; if (!msg) return { entries: [], text: "" };
    const text = Probe.capture.mistralAnswer(msg).trim();
    const byUrl = {}; for (const s of msg.citedSources || []) if (s && s.url) byUrl[s.url] = s;
    const out = [], used = new Set(); let prevEnd = 0, lastSeg = null;
    for (const m of text.matchAll(/\[([^\]\n]{1,200})\]\(/g)) {
      // URL runs to the matching close paren (wikipedia urls contain parens).
      let i = m.index + m[0].length, depth = 1; const u0 = i;
      while (i < text.length && depth) { if (text[i] === "(") depth++; else if (text[i] === ")") depth--; i++; }
      const url = text.slice(u0, i - 1);
      if (!/^https?:\/\//.test(url)) continue;
      let pos = m.index; while (pos > 0 && /[\s(\[]/.test(text[pos - 1])) pos--;
      const seg = segmentBefore(text, pos, prevEnd);
      const lead = /^[\s).,;:\]]+/.exec(text.slice(seg.start, pos)); if (lead) seg.start += lead[0].length;
      seg.text = text.slice(seg.start, pos).trim(); prevEnd = i;
      // Several links in one bracket, "([A](u), [B](v))": they support the same segment.
      if (!seg.text && lastSeg) Object.assign(seg, lastSeg); else lastSeg = { start: seg.start, end: pos, text: seg.text };
      const src = byUrl[url]; used.add(url);
      out.push(mk({ url, title: (src && src.title) || m[1], site_name: m[1], cited_text: src ? stripHtml(src.description) : null,
                    anchor_text: seg.text, anchor_start: seg.start, anchor_end: pos, ref_id: src ? src.id : null, via: "mistral_inline" }));
    }
    // Sources the UI lists but the text never links: citedSources, then the rest of the search results
    // (contentChunks[].publicResult.results), which Le Chat's Sources list also shows (10 listed, 6 linked inline).
    const listed = [...(msg.citedSources || [])];
    for (const ch of msg.contentChunks || []) for (const r of (ch && ch.publicResult && ch.publicResult.results) || []) listed.push(r);
    for (const s of listed) if (s && s.url && !used.has(s.url)) {
      used.add(s.url);
      out.push(mk({ url: s.url, title: s.title, cited_text: stripHtml(s.description), ref_id: s.id, via: "mistral_source" }));
    }
    return { entries: out, text };
  }

  // Markdown links the model wrote itself in the answer, any provider.
  function textLinks(text) {
    const out = [];
    for (const m of text.matchAll(/\[([^\]\n]{1,200})\]\((https?:\/\/[^\s)]+)\)/g)) {
      const seg = segmentBefore(text, m.index, 0);
      out.push(mk({ url: clean(m[2]), title: m[1], anchor_text: seg.text, anchor_start: seg.start, anchor_end: m.index, via: "text_link" }));
    }
    return out;
  }

  const PARSERS = { claude, chatgpt, gemini, mistral, grok };
  function parse(pid, raw, answer) {
    if (!raw) return [];
    let r = { entries: [], text: "" };
    try { if (PARSERS[pid]) r = PARSERS[pid](raw, answer); } catch (_) {}
    parse.lastText = r.text;
    const uniq = new Set(); // Gemini and Claude repeat a source per chip; one row per (source, place)
    r.entries = r.entries.filter((e) => { const k = e.url + "|" + e.anchor_start + "|" + e.marker; if (uniq.has(k)) return false; uniq.add(k); return true; });
    const seen = new Set(r.entries.map((e) => e.url + "|" + e.anchor_start));
    for (const e of textLinks(r.text || answer || "")) if (!seen.has(e.url + "|" + e.anchor_start) && !r.entries.some((x) => x.url === e.url)) r.entries.push(e);
    return r.entries;
  }
  Probe.citations = { parse, canon };
})();
