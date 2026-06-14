// Per-provider INPUT driving (capture happens at the network layer, so these no
// longer need response/streaming selectors — just: start a fresh/private chat,
// find the composer, type, submit). Selectors reuse what we validated in Chrome.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const sleep = Probe.cadence.sleep;

  // --- tiny DOM helpers ---
  function pick(sels, { last = false } = {}) {
    for (const s of sels) { const n = document.querySelectorAll(s); if (n.length) return last ? n[n.length - 1] : n[0]; }
    return null;
  }
  async function waitFor(sels, { timeoutMs = 18000 } = {}) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) { const el = pick(sels); if (el) return el; await sleep(150); }
    throw new Error(`waitFor timed out: ${sels.join(" | ")}`);
  }
  // Full pointer sequence — synthetic .click() alone often doesn't fire React
  // buttons that listen on pointerdown/mousedown (e.g. Claude incognito).
  function realClick(el) {
    const o = { bubbles: true, cancelable: true, view: window, button: 0, buttons: 1 };
    try { el.dispatchEvent(new PointerEvent("pointerdown", o)); } catch (_) {}
    el.dispatchEvent(new MouseEvent("mousedown", o));
    try { el.dispatchEvent(new PointerEvent("pointerup", o)); } catch (_) {}
    el.dispatchEvent(new MouseEvent("mouseup", o));
    el.dispatchEvent(new MouseEvent("click", o));
  }
  function clickFirst(sels) {
    for (const s of sels) for (const el of document.querySelectorAll(s)) {
      if (el.tagName === "A" && el.getAttribute("href")) { try { if (new URL(el.href, location.href).origin !== location.origin) continue; } catch (_) {} }
      realClick(el); return true;
    }
    return false;
  }
  function clickByText(re) {
    for (const el of document.querySelectorAll('button, a, [role="button"], [role="menuitem"]')) {
      if (el.offsetParent === null) continue;
      const t = (el.innerText || "").trim();
      if (t && re.test(t)) { realClick(el); return true; }
    }
    return false;
  }
  // Exact-text click across plain elements too (DeepSeek uses unlabeled <div>s);
  // picks the leaf-most match so we click the actual control, not a container.
  function clickExact(txt) {
    let best = null;
    for (const el of document.querySelectorAll('div,span,button,a,[role="button"],[role="menuitem"]')) {
      if (el.offsetParent === null) continue;
      if ((el.innerText || "").trim() === txt) {
        if (!best || el.querySelectorAll("*").length < best.querySelectorAll("*").length) best = el;
      }
    }
    if (best) { realClick(best); return true; }
    return false;
  }
  function dismissConsent() {
    for (const s of ["#onetrust-accept-btn-handler", "#accept-recommended-btn-handler", ".onetrust-close-btn-handler"]) {
      const el = document.querySelector(s); if (el && el.offsetParent !== null) { realClick(el); return true; }
    }
    const re = /^(accept all( cookies)?|accept cookies|accept|i agree|agree|allow all|got it|confirm my choices)$/i;
    const b = [...document.querySelectorAll('button,[role="button"]')].find((x) => x.offsetParent && re.test((x.innerText || x.getAttribute("aria-label") || "").trim()));
    if (b) { realClick(b); return true; } return false;
  }
  function dismissNotice() {
    const re = /^(not now|no thanks|maybe later|later|skip|dismiss|got it|continue|stay logged out|close|done)$/i;
    for (const dlg of document.querySelectorAll('[role="dialog"],[aria-modal="true"],dialog[open]')) {
      const lbl = (dlg.getAttribute("aria-label") || "") + " " + (dlg.id || "");
      if (dlg.closest("#onetrust-consent-sdk") || /privacy|cookie|consent|preference/i.test(lbl)) continue;
      const hit = [...dlg.querySelectorAll('button,a[role="button"],[role="button"]')].find((b) => re.test((b.innerText || b.getAttribute("aria-label") || "").trim()));
      if (hit) { hit.click(); return true; }
    }
    return false;
  }
  function pressKey(key, mods = {}) {
    const isMac = /mac/i.test(navigator.platform || navigator.userAgent || "");
    const o = { key, code: "Key" + key.toUpperCase(), bubbles: true, cancelable: true, metaKey: !!mods.meta && isMac, ctrlKey: (!!mods.meta && !isMac) || !!mods.ctrl, shiftKey: !!mods.shift };
    for (const t of [document, document.body, document.activeElement].filter(Boolean)) { t.dispatchEvent(new KeyboardEvent("keydown", o)); t.dispatchEvent(new KeyboardEvent("keyup", o)); }
  }
  async function submitViaButtonOrEnter(sendSels, composerSels, waitMs = 4000) {
    const t0 = Date.now();
    while (Date.now() - t0 < waitMs) {
      const btn = pick(sendSels);
      if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") { btn.click(); return; }
      await sleep(150);
    }
    const el = pick(composerSels);
    if (!el) throw new Error("submit: composer missing");
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true }));
  }

  const B = { pick, waitFor, clickFirst, clickByText, dismissConsent, dismissNotice, pressKey, submitViaButtonOrEnter, sleep };

  // --- drivers ---
  const DRIVERS = {
    chatgpt: {
      composer: ["#prompt-textarea", 'div.ProseMirror[contenteditable="true"]'],
      send: ['button[data-testid="send-button"]', 'button[aria-label*="Send" i]'],
      newChat: ['a[data-testid="create-new-chat-button"]', 'button[aria-label*="New chat" i]', 'nav a[href="/"]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        if (priv) {
          const isTemp = new URLSearchParams(location.search).get("temporary-chat") === "true";
          const hasMsgs = !!pick(['[data-message-author-role="assistant"]']);
          if (!isTemp || hasMsgs) { location.assign("/?temporary-chat=true"); await sleep(4000); return; }
        } else if (!clickFirst(this.newChat)) { if (location.pathname !== "/") location.assign("/"); }
        await sleep(700);
        const el = await waitFor(this.composer); if ((el.innerText || "").trim()) Probe.injector.clear(el);
      },
      locateInput() { return waitFor(this.composer); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
    },
    gemini: {
      composer: ['rich-textarea div.ql-editor[contenteditable="true"]', 'div.ql-editor[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]'],
      send: ['button[aria-label*="Send" i]', "button.send-button"],
      newChat: ['expandable-button[data-test-id="new-chat-button"] button', 'button[aria-label*="New chat" i]'],
      temporary: ['button[aria-label="Temporary chat"]', 'button[aria-label*="temporary" i]', '[role="button"][aria-label*="temporary" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        if (priv) {
          // SINGLE plain click — a full pointer sequence (realClick) appears to
          // double-toggle Gemini's "Temporary chat" control (it regressed when we
          // switched global clicks to pointer events).
          const tb = pick(this.temporary);
          if (tb) tb.click();
          else { Probe.log.make("gemini").warn("temporary control not found; NON-private"); if (!clickFirst(this.newChat) && location.pathname !== "/app") location.assign("/app"); }
        } else if (!clickFirst(this.newChat)) { if (location.pathname !== "/app") location.assign("/app"); }
        await sleep(900);
        const el = await waitFor(this.composer); if ((el.innerText || "").trim()) Probe.injector.clear(el);
      },
      locateInput() { return waitFor(this.composer); },
      // Gemini defers/aborts its StreamGenerate request when the tab is
      // backgrounded right after sending. Keep focus a few seconds so the request
      // actually fires + starts streaming before the conductor switches away.
      async submit() {
        await submitViaButtonOrEnter(this.send, this.composer);
        await sleep(4500);
      },
    },
    grok: {
      composer: ['div[contenteditable="true"][role="textbox"][aria-label*="Grok" i]', 'div.tiptap[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]'],
      send: ['button[data-testid="send-button"]', 'button[aria-label*="Submit" i]', 'button[type="submit"]'],
      newChat: ['a[href="/"]'],
      private: ['button[aria-label*="private" i]', '[role="button"][aria-label*="private" i]', 'a[aria-label*="private" i]', 'button[aria-label*="incognito" i]', '[role="button"][aria-label*="incognito" i]', '[role="button"][aria-label*="ephemeral" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        // New chat first — this is what surfaces Grok's private-chat button.
        if (!clickFirst(this.newChat)) { if (location.pathname !== "/") location.assign("/"); }
        await sleep(1100);
        if (priv) {
          if (!clickByText(/private chat|private/i) && !clickFirst(this.private)) {
            pressKey("j", { meta: true, shift: true }); // shortcut fallback
          }
          await sleep(700);
        }
        const el = await waitFor(this.composer); if ((el.innerText || el.value || "").trim()) Probe.injector.clear(el);
      },
      locateInput() { return waitFor(this.composer); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
    },
    claude: {
      composer: ['div[contenteditable="true"].ProseMirror', 'div[contenteditable="true"]'],
      send: ['button[aria-label="Send message"]', 'button[aria-label*="Send" i]'],
      newChat: ['a[href="/new"]', 'button[aria-label*="New chat" i]'],
      incognito: ['button[aria-label*="incognito" i]', 'a[aria-label*="incognito" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        if (priv) {
          // Reset to a new chat, then click the incognito ghost — this starts a
          // FRESH incognito chat each item (navigating to the same /new?incognito=
          // URL is a no-op, which is why it kept reusing the first chat).
          clickFirst(this.newChat);
          await sleep(600);
          if (!clickFirst(this.incognito) && !clickByText(/incognito/i)) {
            location.assign("/new?incognito="); await sleep(2500); return; // URL fallback
          }
          await sleep(700);
          const el2 = await waitFor(this.composer); if ((el2.innerText || "").trim()) Probe.injector.clear(el2);
          return;
        } else if (!clickFirst(this.newChat)) {
          if (location.pathname !== "/new") location.assign("/new");
        }
        await sleep(900);
        const el = await waitFor(this.composer); if ((el.innerText || "").trim()) Probe.injector.clear(el);
      },
      locateInput() { return waitFor(this.composer); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
    },
    deepseek: {
      composer: ["textarea#chat-input", 'textarea[placeholder*="message" i]', "textarea"],
      send: ['div[role="button"][aria-label*="send" i]', 'button[aria-label*="send" i]'],
      newChat: ['a[href="/"]'],
      isReady() { return !!pick(this.composer); },
      async startChat(opts = {}) {
        dismissConsent(); dismissNotice();
        // DeepSeek has no private mode → delete ALL chats before every question
        // so no prior history can bleed in. Fast API call (from your recording).
        if (opts.private) await this.deleteAll();
        if (!clickByText(/^\s*new chat\s*$/i) && !clickFirst(this.newChat)) { if (location.pathname !== "/") location.assign("/"); }
        await sleep(800);
        const el = await waitFor(this.composer); if ((el.innerText || el.value || "").trim()) Probe.injector.clear(el);
      },
      // Read DeepSeek's bearer token from page storage (content scripts share the
      // page's localStorage origin) so the API call is authenticated like the app's.
      // DeepSeek's bearer is NOT a JWT (base64-ish), so look in token-named keys
      // and accept a plain string value (or JSON {value}).
      findToken() {
        const fromRaw = (raw) => {
          if (!raw) return null;
          try { const o = JSON.parse(raw); if (o && typeof o.value === "string") return o.value; if (typeof o === "string") return o; } catch (_) {}
          return typeof raw === "string" && raw.length >= 20 ? raw : null;
        };
        try {
          for (const k of ["userToken", "user_token", "token"]) { const v = fromRaw(localStorage.getItem(k)); if (v) return v; }
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (/token/i.test(key)) { const v = fromRaw(localStorage.getItem(key)); if (v) return v; }
          }
        } catch (_) {}
        return null;
      },
      // Delete all chats — try the authenticated API first; if that fails (auth),
      // fall back to the recorded UI path: profile → Settings → Data → Delete all
      // → Delete all chats. Never touches the Profile-tab "Delete account".
      async deleteAll() {
        const log = Probe.log.make("deepseek");
        const token = this.findToken();
        const headers = { "content-type": "application/json", "x-app-version": "2.0.0" };
        if (token) headers["authorization"] = "Bearer " + token;
        try {
          const res = await fetch("/api/v0/chat_session/delete_all", { method: "POST", credentials: "include", headers, body: "{}" });
          if (res && res.ok) { log.info(`deleted all chats (API${token ? "+token" : ""})`); return true; }
          log.warn(`delete_all API -> ${res && res.status} (token=${!!token}); trying UI`);
        } catch (e) { log.warn(`delete_all API failed: ${e?.message || e}; trying UI`); }

        // UI fallback.
        const settingsOpen = () => /general[\s\S]*profile[\s\S]*data/i.test((document.querySelector('[role="dialog"]') || {}).innerText || "");
        if (!settingsOpen()) { clickFirst(["._2afd28d", '[class*="profile" i]']); await sleep(600); clickExact("Settings"); await sleep(800); }
        if (!settingsOpen()) { log.warn("UI: could not open Settings"); return false; }
        clickExact("Data"); await sleep(600);
        let ok = false;
        if (clickExact("Delete all")) {
          await sleep(700);
          clickExact("Delete all chats") || clickByText(/^(delete all chats|delete all|confirm|delete|yes|ok)$/i);
          await sleep(1000); ok = true; log.info("deleted all chats (UI)");
        } else log.warn("UI: 'Delete all' not found under Data");
        document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await sleep(400);
        return ok;
      },
      locateInput() { return waitFor(this.composer); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
    },
  };

  Probe.drivers = {
    B,
    forHost(hostname) {
      const p = Probe.providers.byHost(hostname);
      return p ? DRIVERS[p.id] : null;
    },
    idForHost(hostname) {
      const p = Probe.providers.byHost(hostname);
      return p ? p.id : null;
    },
  };
})();
