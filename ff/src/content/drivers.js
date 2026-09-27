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
  // Close the top-most modal. DeepSeek's Settings close is an icon button in the
  // modal header with no aria-label, so target that; fall back to a labelled close.
  function closeModal() {
    const dlg = pick([".ds-modal-content", '[role="dialog"]', '[aria-modal="true"]']);
    if (!dlg) return false;
    const hdr = dlg.querySelector(".ds-modal-content__header-wrapper") || dlg;
    const btn = hdr.querySelector('[aria-label*="close" i]')
      || hdr.querySelector(".ds-button--iconLabelPrimary")
      || [...hdr.querySelectorAll('.ds-button,button,[role="button"]')].filter((x) => x.offsetParent !== null).pop();
    if (btn) { realClick(btn); return true; }
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
  // Which branch actually sent the prompt is the difference between an answer and a
  // 90s "no response (timeout)", and until 2026-09-15 nothing recorded it. Added while
  // chasing Gemini's timeouts, and it earned its keep immediately by RULING OUT the
  // suspect: on every attempt of the 2026-09-15 test the button was clicked in 4-9ms
  // and the Enter fallback never ran, so the prompt is sent and the loss is downstream.
  async function submitViaButtonOrEnter(sendSels, composerSels, waitMs = 4000) {
    const slog = Probe.log.make("submit");
    const t0 = Date.now();
    while (Date.now() - t0 < waitMs) {
      const btn = pick(sendSels);
      if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") {
        btn.click();
        slog.info(`sent via send-button after ${Date.now() - t0}ms`);
        return;
      }
      await sleep(150);
    }
    const el = pick(composerSels);
    if (!el) throw new Error("submit: composer missing");
    const btn = pick(sendSels);
    slog.warn(`send button never enabled in ${waitMs}ms (button ${btn ? "present but disabled" : "NOT FOUND"}) — falling back to Enter`);
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
      // Temp-chat lives behind the sidebar: (open sidebar) -> Gemini "sparkle" icon
      // -> temp-chat button. Custom-element selectors (stable), not ng-* classes.
      sidebar: ['button[aria-label="Open sidebar" i]'],
      sparkle: ['a.side-nav-sparkle-button', 'side-nav-sparkle-button a', 'side-nav-sparkle-button'],
      tempChat: ['temp-chat-button button', 'temp-chat-button gem-icon-button button', 'temp-chat-button'],
      newChat: ['a[aria-label*="New chat" i]', 'side-nav-action-button a', 'a[href="/app"]'],
      // Anything that only exists once the conversation has a turn in it. Used to
      // prove the chat is actually EMPTY before we submit (see the guard below).
      turns: ['user-query', 'model-response', 'button[aria-label*="Copy prompt" i]'],
      isReady() { return !!pick(this.composer); },
      hasTurns() { return this.turns.some((s) => document.querySelector(s)); },
      async startChat() {
        dismissConsent(); dismissNotice();
        const log = Probe.log.make("gemini");
        // Fresh TEMPORARY chat per question. ORDER MATTERS:
        //   1. NEW CHAT   (Shift+Cmd/Ctrl+O, or the sidebar "New chat" button)
        //   2. THEN the temp-chat button -> a new *temporary* chat
        // Clicking temp-chat on its own does NOT start a new conversation when you are
        // already inside one — it only toggles the mode. That is how the entire Gemini
        // set ended up as ONE long chat, silently carrying context between questions.
        const newChatShortcut = () => {
          const ev = (extra) => new KeyboardEvent("keydown", {
            key: "o", code: "KeyO", keyCode: 79, which: 79,
            shiftKey: true, bubbles: true, cancelable: true, ...extra,
          });
          for (const t of [document, document.body]) {
            t.dispatchEvent(ev({ metaKey: true }));   // macOS
            t.dispatchEvent(ev({ ctrlKey: true }));   // other platforms
          }
        };
        newChatShortcut();
        await sleep(900);
        if (this.hasTurns()) {   // shortcut didn't take — use the sidebar button
          if (!pick(this.newChat)) { clickFirst(this.sidebar); await sleep(600); }
          if (!clickFirst(this.newChat)) clickByText(/^\s*new chat\s*$/i);
          await sleep(1100);
        }
        // Now convert the fresh chat to a TEMPORARY one (nested behind the sparkle).
        if (!pick(this.sparkle) && !pick(this.tempChat)) { clickFirst(this.sidebar); await sleep(600); }
        clickFirst(this.sparkle);
        await sleep(700);
        if (!clickFirst(this.tempChat)) log.warn("temp-chat button not found; chat will NOT be temporary");
        await sleep(1300);
        // HARD GUARD. Submitting into a chat that still holds previous turns silently
        // contaminates the answer with earlier context (exactly how the Gemini set got
        // polluted). Fail loudly instead: the runner records an ERROR and re-asks,
        // rather than banking a dirty answer.
        if (this.hasTurns()) {
          throw new Error("gemini: previous turns still present after reset — refusing to ask in a dirty chat");
        }
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
      // Is the visible answer finished? Gemini keeps its StreamGenerate connection
      // open for up to two minutes after the answer is complete and on screen, so
      // the network layer cannot tell us when to stop waiting — the page can. The
      // background polls this and flushes the buffered stream once generation has
      // stopped and the text has held still. Returns the LAST response's length.
      answerState() {
        // Advisory only: if Gemini renames this control the gate falls back to text
        // stability + a quiet network stream, which carry the decision anyway.
        const stop = [...document.querySelectorAll('button[aria-label*="Stop" i]')].some((b) => b.offsetParent !== null);
        const resp = [...document.querySelectorAll("model-response")].pop();
        const text = resp ? (resp.innerText || "").trim() : "";
        return { generating: stop, len: text.length };
      },
      // Citations render as chips that expand into <a href> source cards; the URLs
      // are NOT reliably in the response stream, so scrape them from the DOM. The
      // background calls this after the answer is captured. Returns [{title,url}].
      async scrapeSources() {
        const chips = [...document.querySelectorAll("source-inline-chip button, sources-carousel-inline button")];
        for (const c of chips.slice(0, 15)) { try { c.click(); await sleep(120); } catch (_) {} }
        await sleep(600);
        const out = [], seen = new Set();
        for (const a of document.querySelectorAll("sources-carousel-inline a[href], inline-source-card a[href], .stacked-cards-container a[href], mat-dialog-container a[href]")) {
          const href = a.getAttribute("href") || "";
          if (/^(javascript:|#|mailto:)/.test(href)) continue;
          const url = a.href; if (!url || seen.has(url)) continue; seen.add(url);
          out.push({ title: (a.innerText || "").trim().slice(0, 200) || null, url });
        }
        // Close any sources panel/dialog we expanded so it doesn't cover the composer.
        document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
        return out;
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
      // The SAME button toggles: aria-label is "Use incognito" when OFF and
      // "Exit incognito" when ON. Match only the ENTER label so we never click
      // "Exit" (which drops the question into a saved, non-private chat).
      incognitoOn: ['button[aria-label*="Use incognito" i]', 'a[aria-label*="Use incognito" i]'],
      incognitoOff: ['button[aria-label*="Exit incognito" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        if (priv) {
          // Start a FRESH incognito chat each item. Claude keeps ONE incognito
          // session and "New chat" does NOT reset it (it just kept appending). The
          // reliable reset is to EXIT incognito if we're in it, then re-ENTER —
          // entering always spawns a new empty incognito chat. Entering is the LAST
          // step, so the prompt lands in the fresh incognito chat, never a saved one.
          if (pick(this.incognitoOff)) { clickFirst(this.incognitoOff); await sleep(700); }
          if (!clickFirst(this.incognitoOn) && !clickByText(/^use incognito$/i)) {
            location.assign("/new?incognito="); await sleep(2500); return; // URL fallback
          }
          await sleep(800);
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
        // Close the Settings modal so it doesn't sit over the composer. DeepSeek's
        // close is an unlabelled icon button in the modal header — click it; only
        // fall back to Escape (which alone did not dismiss it) if that fails.
        if (!closeModal()) {
          for (const t of [document, document.body, document.activeElement].filter(Boolean))
            t.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
        }
        await sleep(500);
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
