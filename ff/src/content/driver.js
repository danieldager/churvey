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

  ext.runtime.onMessage.addListener((msg) => {
    if (!msg) return;
    if (msg.type === Probe.MSG.PING) {
      return Promise.resolve({ ok: true, build: Probe.BUILD, provider: providerId, ready: driver ? safe(() => driver.isReady(), false) : false, visible: document.visibilityState });
    }
    if (msg.type === Probe.MSG.CAPTURE_DOM) {
      return Promise.resolve({ ok: true, dom: dumpDom() });
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
          await Probe.injector.type(input, msg.prompt, { retries: 1 });
          const submittedAt = Date.now();
          await driver.submit();
          log.info(`submitted (${providerId}) @ visibility=${document.visibilityState}`);
          return { ok: true, submittedAt, visibility: document.visibilityState };
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
