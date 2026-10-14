// Content driver: INPUT only. The background tells us to ASK; we start a fresh
// (optionally private) chat, type the prompt, and submit. The ANSWER is captured
// by the background at the network layer — we just report that we submitted.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const ext = globalThis.ext;
  const log = Probe.log.make("driver");

  const driver = Probe.drivers.forHost(location.hostname);
  const providerId = Probe.drivers.idForHost(location.hostname);
  if (!driver) { log.warn("no driver for", location.hostname); }

  function safe(fn, fb) { try { return fn(); } catch (_) { return fb; } }

  function dumpDom() {
    const clip = (s, n) => { s = (s || "").trim(); return s.length > n ? s.slice(0, n) + "…" : s; };
    const clsOf = (el) => { const c = el.className; return clip(typeof c === "string" ? c : (c && c.baseVal) || "", 90); };
    const desc = (el) => ({
      tag: el.tagName.toLowerCase(),
      text: clip(el.innerText || el.getAttribute("title") || "", 40),
      aria: el.getAttribute("aria-label"),
      title: el.getAttribute("title"),
      testid: el.getAttribute("data-testid"),
      href: el.getAttribute && el.getAttribute("href"),
      cls: clsOf(el),
    });
    const vis = (el) => el.offsetParent !== null || (el.getClientRects && el.getClientRects().length > 0);

    // Broad set of "clickable-ish" elements.
    const seen = new Set(); const buttons = [];
    for (const el of document.querySelectorAll('button, [role="button"], a, [aria-label], [data-testid], [onclick], [tabindex]')) {
      if (!vis(el) || seen.has(el)) continue;
      seen.add(el); buttons.push(desc(el));
      if (buttons.length >= 250) break;
    }

    // Everything in the top-right header region (where Grok's private button is).
    const W = window.innerWidth; const topRight = [];
    for (const el of document.querySelectorAll("button, [role='button'], a, svg, [aria-label], [data-testid]")) {
      const r = el.getBoundingClientRect();
      if (r.width < 6 || r.height < 6) continue;
      if (r.top < 150 && r.left > W * 0.5) { topRight.push({ ...desc(el), rect: [Math.round(r.left), Math.round(r.top)] }); }
      if (topRight.length >= 50) break;
    }

    const dialogs = [...document.querySelectorAll('[role="dialog"], [aria-modal="true"], dialog[open]')]
      .map((d) => ({ aria: d.getAttribute("aria-label"), text: clip(d.innerText, 500), buttons: [...d.querySelectorAll('button, [role="button"], a')].map((b) => clip(b.innerText || b.getAttribute("aria-label") || "", 40)) }));

    return { provider: providerId, url: location.href, ts: new Date().toISOString(), visibility: document.visibilityState, topRight, buttons, dialogs };
  }

  // Audit of capture: the external links the page shows for the answer (inline chips, Sources lists),
  // after opening any "Sources"/"N sources" button once. Read-only apart from that click; a provider
  // driver can override with its own visibleSources().
  async function visibleSources(open) {
    const own = location.hostname.replace(/^www\./, "");
    const collect = (where) => {
      const out = [];
      for (const a of document.querySelectorAll('a[href^="http"]')) {
        let u; try { u = new URL(a.href); } catch (_) { continue; }
        if (u.hostname.replace(/^www\./, "").endsWith(own)) continue;
        if (a.closest('nav, aside[aria-label*="histor" i], [data-testid*="composer"], footer, form')) continue;
        if (/gstatic|googleusercontent|google\.com\/(intl|policies|support)|mistral\.ai\/(terms|privacy)|openai\.com\/(policies|privacy)|anthropic\.com\/(legal|privacy)|x\.ai\//i.test(a.href)) continue;
        out.push({ url: a.href, title: (a.innerText || a.getAttribute("aria-label") || a.title || "").trim().slice(0, 160) || null, where });
      }
      return out;
    };
    const links = collect("page");
    const re = /^(sources?|\d+\s+sources?|sources?\s*\(?\d+\)?|\d+\s+(web\s+)?(pages?|results?|r[eé]sultats?|sites?)|(view|show|voir|afficher)\s+(all\s+)?(\d+\s+)?sources?|[0-9]+\s+r[eé]f[eé]rences?|r[eé]f[eé]rences?|citations?)$/i;
    // The label may sit in a nested span (ChatGPT's "Sources" pill): match on an element's own text, click its button.
    const own_ = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").trim();
    const btns = [...new Set([...document.querySelectorAll("button,[role=button],a,div,span")]
      .filter((e) => e.offsetParent !== null && (re.test(own_(e)) || (e.matches("button,[role=button]") && re.test((e.getAttribute("aria-label") || "").trim()))))
      .map((e) => e.closest("button,[role=button],a") || e))];
    const buttons = btns.map((b) => (b.innerText || b.getAttribute("aria-label") || "").trim());
    if (open) {
      for (const b of btns.slice(0, 2)) {
        try { b.click(); } catch (_) {}
        await Probe.cadence.sleep(900);
        links.push(...collect("opened:" + (b.innerText || b.getAttribute("aria-label") || "").trim().slice(0, 30)));
        document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
        await Probe.cadence.sleep(300);
      }
    }
    if (driver && driver.scrapeSources) for (const x of (await driver.scrapeSources()) || []) links.push({ url: x.url, title: x.title, where: "driver_scrape" });
    const hints = [...document.querySelectorAll("button,[role=button],a,summary,div,span")].filter((e) => e.offsetParent !== null && e.children.length < 6)
      .map((e) => ({ tag: e.tagName.toLowerCase(), cls: String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className).slice(0, 60), text: (e.innerText || "").trim().slice(0, 40), aria: e.getAttribute("aria-label"), testid: e.getAttribute("data-testid") }))
      .filter((h) => /sources?\b|r[eé]f[eé]rences?|citations?|searched|recherch|results?\b|r[eé]sultats?/i.test(h.text + " " + (h.aria || "")) && (h.text.length < 40)).slice(0, 25);
    const seen = new Set(), uniq = [];
    for (const l of links) { const k = l.url + "|" + l.where; if (!seen.has(k)) { seen.add(k); uniq.push(l); } }
    const custom = {};
    for (const e of document.querySelectorAll("*")) { const t = e.tagName.toLowerCase(); if (/source|citation|ground|attribution|chip/.test(t)) { const c = (custom[t] ||= { n: 0, text: [], anchors: 0, aria: [] }); c.n++; if (c.text.length < 3) c.text.push((e.innerText || e.textContent || "").trim().slice(0, 160)); c.anchors += e.querySelectorAll("a[href]").length; for (const b of e.querySelectorAll("[aria-label]")) if (c.aria.length < 6) c.aria.push(b.getAttribute("aria-label").slice(0, 90)); } }
    return { links: uniq, buttons, hints, custom };
  }

  // `churvey probe` and `churvey account prepare` (background probe.js / isolation.js): one driver function by name.
  // fingerprint, memoryControls and bannerTest are generic; the rest exist only where the driver defines them.
  const PROBE_FNS = new Set(["loginState", "fingerprint", "endpointShapes", "memoryControls", "memoryOff", "deleteAllChats", "bannerTest"]);
  async function probeCall(fn, args) {
    if (!PROBE_FNS.has(fn)) throw new Error(`not a probe function: ${fn}`);
    if (fn === "fingerprint") return Probe.drivers.B.fingerprint(driver);
    if (fn === "memoryControls") return Probe.drivers.B.memoryControls(driver || {}, false);
    if (fn === "bannerTest") return bannerTest();
    if (!driver || typeof driver[fn] !== "function") throw new Error(`no ${fn} for provider`);
    return driver[fn](...args);
  }
  // Does the limit-banner detector still work on this page? Put a typical banner inside the app (<main>, where a real
  // one appears: a page-wide container excluded as « conversation » would hide it), read pageStatus, take it off.
  function bannerTest() {
    const before = { ...Probe.pageState.pageStatus(), banner: Probe.pageState.limitBanner() };
    const el = document.createElement("div");
    el.setAttribute("role", "alert");
    el.style.cssText = "position:fixed;top:8px;left:8px;z-index:2147483647;background:#fee;padding:6px;font:14px sans-serif";
    el.textContent = "You've reached your message limit. Try again later.";
    (document.querySelector("main") || document.body).appendChild(el);
    let during;
    try { during = { ...Probe.pageState.pageStatus(), banner: Probe.pageState.limitBanner() }; } finally { el.remove(); }
    return { before, during };
  }

  ext.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === Probe.MSG.PROBE_CALL) {
      return (async () => {
        try { return { ok: true, result: await probeCall(msg.fn, msg.args || []) }; }
        catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (!msg) return;
    if (msg.type === Probe.MSG.PING) {
      return Promise.resolve({ ok: true, build: Probe.BUILD, provider: providerId, ready: driver ? safe(() => driver.isReady(), false) : false, visible: document.visibilityState });
    }
    if (msg.type === Probe.MSG.CAPTURE_DOM) {
      return Promise.resolve({ ok: true, dom: dumpDom() });
    }
    if (msg.type === Probe.MSG.ANSWER_STATE) {
      if (!driver || typeof driver.answerState !== "function") return Promise.resolve({ ok: false });
      return Promise.resolve({ ok: true, ...safe(() => driver.answerState(), { generating: false, len: 0 }) });
    }
    if (msg.type === Probe.MSG.VISIBLE_SOURCES) {
      return (async () => {
        try { return { ok: true, ...(await ((driver && driver.visibleSources) ? driver.visibleSources(!!msg.open) : visibleSources(!!msg.open))) }; }
        catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (msg.type === Probe.MSG.GROK_POLL || msg.type === Probe.MSG.POLL) {
      return (async () => {
        if (!driver || typeof driver.poll !== "function") return { ok: false, error: "no poll" };
        try { return { ok: true, ...(await driver.poll(msg.convId, msg.prompt)) }; }
        catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (msg.type === Probe.MSG.PAGE_STATUS) {
      return Promise.resolve({ ok: true, ...safe(() => Probe.pageState.pageStatus(), { state: "ok", text: "" }) });
    }
    if (msg.type === Probe.MSG.READ_ANSWER) {
      return Promise.resolve({ ok: true, ...safe(() => Probe.pageState.readAnswer(providerId), { text: "", len: 0, generating: false, finished: false, links: [] }) });
    }
    if (msg.type === Probe.MSG.SCRAPE_SOURCES) {
      return (async () => {
        if (!driver || typeof driver.scrapeSources !== "function") return { ok: false, error: "no scraper" };
        try { return { ok: true, citations: (await driver.scrapeSources()) || [] }; }
        catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (msg.type === Probe.MSG.REC_ON) { startRec(); return Promise.resolve({ ok: true }); }
    if (msg.type === Probe.MSG.REC_OFF) { stopRec(); return Promise.resolve({ ok: true }); }
    if (msg.type === Probe.MSG.PURGE) {
      return (async () => {
        if (!driver || typeof driver.deleteAll !== "function") return { ok: false, error: "no purge for provider" };
        try { await driver.deleteAll(); return { ok: true }; }
        catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (msg.type === Probe.MSG.ISOLATION_STATE) {
      if (!driver || typeof driver.isolationState !== "function") return Promise.resolve({ ok: false, error: "no isolation check for provider" });
      return Promise.resolve(safe(() => ({ ok: true, ...driver.isolationState() }), { ok: false, error: "isolationState threw" }));
    }
    if (msg.type === Probe.MSG.MEMORY_STATUS || msg.type === Probe.MSG.DELETE_CHATS || msg.type === Probe.MSG.LIST_CHATS) {
      const fn = { [Probe.MSG.MEMORY_STATUS]: "memoryStatus", [Probe.MSG.DELETE_CHATS]: "deleteChats", [Probe.MSG.LIST_CHATS]: "listChats" }[msg.type];
      return (async () => {
        if (!driver || typeof driver[fn] !== "function") return { ok: false, error: `no ${fn} for provider` };
        try {
          const r = await driver[fn](msg.ids || []);
          return msg.type === Probe.MSG.MEMORY_STATUS ? { ok: true, ...r } : msg.type === Probe.MSG.DELETE_CHATS ? { ok: true, results: r } : { ok: true, ids: r };
        } catch (e) { return { ok: false, error: String(e?.message || e) }; }
      })();
    }
    if (msg.type === Probe.MSG.NEW_CHAT) {
      return (async () => {
        if (!driver) return { ok: false, error: "no driver" };
        if (!driver.isReady()) return { ok: false, error: "not ready (login/page)" };
        try {
          // May navigate (ChatGPT temporary / DeepSeek). If it does, the page
          // unloads and this response is never delivered — the conductor waits
          // for the tab to become ready again, then sends SUBMIT.
          await driver.startChat({ private: !!msg.private });
          return { ok: true };
        } catch (e) {
          return { ok: false, error: String(e?.message || e) };
        }
      })();
    }
    if (msg.type === Probe.MSG.SUBMIT) {
      return (async () => {
        if (!driver) return { ok: false, error: "no driver" };
        try {
          const input = await driver.locateInput();
          // Pictures go in BEFORE the text: the send button stays disabled while an
          // upload is in flight, and submitViaButtonOrEnter waits for it anyway.
          let attached = null;
          if (msg.attachments && msg.attachments.length) {
            if (typeof driver.attach !== "function") {
              log.warn(`driver ${providerId} cannot attach files - sending text only`);
            } else {
              // Never fatal: if no strategy lands the picture we still send the
              // text, and the answer itself says whether the picture arrived.
              try { attached = await driver.attach(msg.attachments); }
              catch (e) { attached = "failed: " + String(e?.message || e); log.warn("attach failed", attached); }
            }
          }
          await Probe.injector.type(input, msg.prompt, { retries: 1 });
          const submittedAt = Date.now();
          await driver.submit();
          log.info(`submitted (${providerId}) @ visibility=${document.visibilityState}`);
          return { ok: true, submittedAt, attached, visibility: document.visibilityState };
        } catch (e) {
          log.error("submit failed", e?.message || e);
          return { ok: false, error: String(e?.message || e) };
        }
      })();
    }
  });

  // --- interaction recorder (records your clicks + DOM dialog changes; network
  // is recorded in the background). Survives navigation by re-checking on load. ---
  let recAttached = false, recObserver = null;
  function cls(el) { const c = el.className; return (typeof c === "string" ? c : (c && c.baseVal) || ""); }
  function recDesc(el) {
    if (!el || el.nodeType !== 1) return null;
    return { tag: el.tagName.toLowerCase(), id: el.id || null, cls: cls(el).slice(0, 100), aria: el.getAttribute("aria-label"), testid: el.getAttribute("data-testid"), href: el.getAttribute && el.getAttribute("href"), text: (el.innerText || "").trim().slice(0, 60), path: cssPath(el) };
  }
  function cssPath(el) {
    const parts = []; let n = el, depth = 0;
    while (n && n.nodeType === 1 && depth < 6) {
      let s = n.tagName.toLowerCase();
      if (n.id) { parts.unshift(s + "#" + n.id); break; }
      const c = (typeof n.className === "string" ? n.className : "").trim().split(/\s+/).filter(Boolean).slice(0, 2);
      if (c.length) s += "." + c.join(".");
      const p = n.parentElement;
      if (p) { const sib = [...p.children].filter((x) => x.tagName === n.tagName); if (sib.length > 1) s += `:nth-of-type(${sib.indexOf(n) + 1})`; }
      parts.unshift(s); n = n.parentElement; depth++;
    }
    return parts.join(" > ");
  }
  function recSend(event) { try { ext.runtime.sendMessage({ type: Probe.MSG.REC_EVENT, event }); } catch (_) {} }
  function recClick(e) {
    const t = e.target;
    const clickable = (t.closest && t.closest('button, [role="button"], a, [role="menuitem"], input, [tabindex]')) || t;
    recSend({ kind: "click", ts: Date.now(), url: location.href, target: recDesc(t), clickable: recDesc(clickable) });
  }
  function recInput(e) {
    const t = e.target; if (!t || (t.tagName !== "INPUT" && t.tagName !== "TEXTAREA")) return;
    recSend({ kind: "input", ts: Date.now(), url: location.href, target: recDesc(t) });
  }
  function startRec() {
    if (recAttached) return; recAttached = true;
    document.addEventListener("click", recClick, true);
    document.addEventListener("change", recInput, true);
    recObserver = new MutationObserver((muts) => {
      for (const m of muts) for (const node of m.addedNodes) {
        if (node.nodeType === 1 && (node.matches?.('[role="dialog"]') || node.querySelector?.('[role="dialog"]'))) {
          recSend({ kind: "dom", ts: Date.now(), change: "dialog-added", text: (node.innerText || "").trim().slice(0, 140) });
        }
      }
    });
    try { recObserver.observe(document.body, { childList: true, subtree: true }); } catch (_) {}
    log.info("recording interactions");
  }
  function stopRec() {
    if (!recAttached) return; recAttached = false;
    document.removeEventListener("click", recClick, true);
    document.removeEventListener("change", recInput, true);
    if (recObserver) { recObserver.disconnect(); recObserver = null; }
  }
  // Re-arm after navigation if a recording is in progress.
  ext.runtime.sendMessage({ type: Probe.MSG.REC_ACTIVE }).then((r) => { if (r && r.recording) startRec(); }).catch(() => {});

  // Announce readiness so the background can map tab -> provider.
  try { ext.runtime.sendMessage({ type: Probe.MSG.DRIVER_READY, provider: providerId }); } catch (_) {}
  log.info(`driver ready on ${location.hostname} (provider ${providerId}, build ${Probe.BUILD})`);
})();
