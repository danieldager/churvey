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

  // --- attaching a picture to the composer -----------------------------------
  // Photo-dependent claims are the ones the media rule throws away: the words only
  // point at the picture. They become probeable if the picture goes into the chat
  // with the prompt. The composer is React, so there are three ways in and none is
  // guaranteed: the hidden <input type=file> (assign a FileList and fire change),
  // a synthetic paste carrying the File, and a synthetic drop. Try them in that
  // order and stop at the first that makes a preview appear.
  function previewCount() {
    return document.querySelectorAll('img[src^="blob:"], img[src^="data:image"], '
      + '[data-testid*="file" i], [data-testid*="attachment" i], [data-testid*="thumbnail" i]').length;
  }
  async function previewGrew(base, timeoutMs = 20000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      if (previewCount() > base) return Date.now() - t0;
      await sleep(300);
    }
    return null;
  }
  // files: [{name, dataUrl}] from the background (it has the host permission).
  async function attachFiles(composerSels, files) {
    const alog = Probe.log.make("attach");
    const dt = new DataTransfer();
    for (const f of files) {
      const blob = await (await fetch(f.dataUrl)).blob();
      dt.items.add(new File([blob], f.name || "image.jpg", { type: blob.type || "image/jpeg" }));
    }
    const el = await waitFor(composerSels);
    for (const [name, run] of [
      ["file-input", () => {
        const inp = [...document.querySelectorAll('input[type="file"]')]
          .find((i) => !i.disabled && (!i.accept || /image|\*/i.test(i.accept)));
        if (!inp) return false;
        inp.files = dt.files;
        inp.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }],
      ["paste", () => {
        el.focus();
        el.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt }));
        return true;
      }],
      ["drop", () => {
        for (const t of ["dragenter", "dragover", "drop"]) {
          el.dispatchEvent(new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: dt }));
        }
        return true;
      }],
    ]) {
      const base = previewCount();
      let fired = false;
      try { fired = run(); } catch (e) { alog.warn(`${name} threw`, e?.message || e); }
      if (!fired) { alog.info(`${name}: not available`); continue; }
      const ms = await previewGrew(base);
      if (ms !== null) { alog.info(`attached ${files.length} file(s) via ${name} in ${ms}ms`); return name; }
      alog.warn(`${name}: no preview appeared in 20s`);
    }
    throw new Error("attach: no strategy produced a preview");
  }

  const B = { pick, waitFor, clickFirst, clickByText, dismissConsent, dismissNotice, pressKey, submitViaButtonOrEnter, attachFiles, sleep };

  // --- drivers ---
  const DRIVERS = {
    chatgpt: {
      composer: ["#prompt-textarea", 'div.ProseMirror[contenteditable="true"]'],
      send: ['button[data-testid="send-button"]', 'button[aria-label*="Send" i]'],
      newChat: ['a[data-testid="create-new-chat-button"]', 'button[aria-label*="New chat" i]', 'nav a[href="/"]'],
      isReady() { return !!pick(this.composer); },
      // Every question gets a FRESH page load of a new chat. The old shortcut ("already on ?temporary-chat=true and no
      // assistant message on screen -> reuse") is how the 2026-10-13 pilot asked 16 questions in ONE temporary chat:
      // ChatGPT's markup no longer has [data-message-author-role], so a used chat always looked empty.
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        location.assign(priv ? "/?temporary-chat=true" : "/");
        await sleep(4000);
      },
      // Before submit: on the home route (no /c/<id>) with the temporary-chat switch showing "Turn off temporary chat".
      isolationState() {
        const temp = new URLSearchParams(location.search).get("temporary-chat") === "true";
        const btn = !!pick(['button[aria-label="Turn off temporary chat"]']);
        return { temporary: temp && btn, newChat: location.pathname === "/",
                 evidence: `page ${location.pathname}${location.search}${btn ? ", 'Turn off temporary chat' switch" : ", no temporary-chat switch"}` };
      },
      async api(path, init = {}) {
        const s = await (await fetch(location.origin + "/api/auth/session", { credentials: "include" })).json();
        if (!s.accessToken) throw new Error("not signed in");
        return fetch(location.origin + path, { credentials: "include", ...init, headers: { authorization: "Bearer " + s.accessToken, "content-type": "application/json", ...(init.headers || {}) } });
      },
      // settings.sunshine = "Reference saved memories", settings.moonshine = "Reference chat history" (both behind the one
      // "Enable memory" switch in Settings > Personalization since 2026-10; checked against that switch on 2026-10-14).
      async memoryStatus() {
        const r = await this.api("/backend-api/settings/user");
        if (!r.ok) return { status: "unknown", detail: `settings/user ${r.status}` };
        const s = (await r.json()).settings || {};
        if (typeof s.sunshine !== "boolean" && typeof s.moonshine !== "boolean") return { status: "unknown", detail: "settings/user has no sunshine/moonshine field" };
        return { status: s.sunshine || s.moonshine ? "on" : "off", detail: `saved memories (sunshine)=${s.sunshine}, chat history (moonshine)=${s.moonshine}` };
      },
      async deleteChats(ids) {
        const out = {};
        for (const id of ids) {
          const r = await this.api(`/backend-api/conversation/${id}`, { method: "PATCH", body: JSON.stringify({ is_visible: false }) });
          if (r.ok || r.status !== 404) { out[id] = r.ok ? "deleted" : `error ${r.status}`; continue; }
          // A temporary chat answers GET (is_temporary_chat: true) but 404s on the delete: ChatGPT does not let the
          // user delete it (it is kept up to 30 days, out of the history). Measured 2026-10-14.
          const g = await this.api(`/backend-api/conversation/${id}`);
          out[id] = g.ok && (await g.json()).is_temporary_chat === true ? "unsupported" : "not_found";
        }
        return out;
      },
      async listChats() {
        const ids = [];
        for (let off = 0; off < 10000; off += 100) {
          const r = await this.api(`/backend-api/conversations?offset=${off}&limit=100&order=updated`);
          if (!r.ok) throw new Error(`conversations ${r.status}`);
          const j = await r.json();
          for (const c of j.items || []) ids.push(c.id);
          if (!(j.items || []).length || ids.length >= (j.total || 0)) break;
        }
        return ids;
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
      // The temp-chat button's host <gem-icon-button> carries class `temp-chat-on` while the chat is temporary (2026-10-14).
      isTemp() { return !!document.querySelector("temp-chat-button .temp-chat-on, gem-icon-button.temp-chat-button.temp-chat-on"); },
      isolationState() {
        const temp = this.isTemp(), turns = this.hasTurns(), conv = /\/app\/[0-9a-f]{8,}/.test(location.pathname);
        return { temporary: temp, newChat: !turns && !conv,
                 evidence: `page ${location.pathname}${temp ? ", temp-chat button on (temp-chat-on)" : ", temp-chat button off"}${turns ? ", earlier turns on screen" : ""}` };
      },
      // Settings > Personal context (gemini.google.com/saved-info): the "Memory" switch ("Gemini learns from your past
      // chats"). Only readable on that page; the background navigates there first (`needs`).
      async memoryStatus() {
        if (location.pathname !== "/saved-info") return { needs: "https://gemini.google.com/saved-info" };
        const t0 = Date.now();
        while (Date.now() - t0 < 15000) {
          for (const s of document.querySelectorAll('[role="switch"], button[aria-checked]')) {
            let n = s, t = "";
            for (let i = 0; i < 6 && n; i++) { n = n.parentElement; t = (n && n.innerText || "").trim(); if (t.length > 20) break; }
            if (/^memory\b/i.test(t)) {
              const on = s.getAttribute("aria-checked") === "true";
              const saved = /haven't asked Gemini to save anything/i.test(document.body.innerText) ? "no saved info" : "saved info present";
              return { status: on ? "on" : "off", detail: `Personal context > Memory switch ${on ? "on" : "off"}; ${saved}` };
            }
          }
          await sleep(500);
        }
        return { status: "unknown", detail: "no Memory switch on /saved-info" };
      },
      // Temporary chats never enter the history and Gemini has no delete-by-id we can call.
      deleteChats(ids) { return Object.fromEntries(ids.map((id) => [id, "unsupported"])); },
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
        // Now convert the fresh chat to a TEMPORARY one (nested behind the sparkle). The button TOGGLES: never click it
        // when the chat is already temporary, that would turn it off.
        if (!this.isTemp()) {
          if (!pick(this.sparkle) && !pick(this.tempChat)) { clickFirst(this.sidebar); await sleep(600); }
          clickFirst(this.sparkle);
          await sleep(700);
          if (!clickFirst(this.tempChat)) log.warn("temp-chat button not found; chat will NOT be temporary");
          await sleep(1300);
        }
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
      send: ['button[data-testid="chat-submit"]', 'button[aria-label="Submit"]', 'button[data-testid="send-button"]', 'button[aria-label*="Submit" i]', 'button[type="submit"]'],
      newChat: ['a[data-testid="new-chat"]', 'a[href="/"]'],
      private: ['a[aria-label="Switch to Private Chat"]', 'button[aria-label*="private" i]', '[role="button"][aria-label*="private" i]', 'a[aria-label*="private" i]', 'button[aria-label*="incognito" i]', '[role="button"][aria-label*="incognito" i]', '[role="button"][aria-label*="ephemeral" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        // New chat first — this is what surfaces Grok's private-chat button.
        if (!clickFirst(this.newChat)) { if (location.pathname !== "/") location.assign("/"); }
        await sleep(1100);
        // The private link reads "Private" in BOTH states; only its aria-label says which. Click only "Switch to Private
        // Chat" (clicking by text used to be able to switch a private chat back to a default one).
        if (priv && !pick(this.privateOn)) {
          if (!clickFirst(this.private)) pressKey("j", { meta: true, shift: true }); // shortcut fallback
          await sleep(700);
        }
        const el = await waitFor(this.composer); if ((el.innerText || el.value || "").trim()) Probe.injector.clear(el);
      },
      privateOn: ['a[aria-label="Switch to Default Chat"]'],
      isolationState() {
        const on = !!pick(this.privateOn), conv = /\/c\/[0-9a-f-]{36}/.test(location.pathname);
        return { temporary: on, newChat: !conv, evidence: `page ${location.pathname}${on ? ", 'Switch to Default Chat' link (private on)" : ", private chat off"}` };
      },
      async rest(path, init) {
        const r = await fetch(location.origin + path, { credentials: "include", ...(init || {}) });
        return r;
      },
      async memoryStatus() {
        const r = await this.rest("/rest/user-settings");
        if (!r.ok) return { status: "unknown", detail: `user-settings ${r.status}` };
        const s = await r.json();
        if (typeof s.enableMemory !== "boolean") return { status: "unknown", detail: "user-settings has no enableMemory" };
        return { status: s.enableMemory ? "on" : "off", detail: `enableMemory=${s.enableMemory}, allowXPersonalization=${s.allowXPersonalization}` };
      },
      async deleteChats(ids) {
        const out = {};
        for (const id of ids) {
          const r = await this.rest(`/rest/app-chat/conversations/${id}`, { method: "DELETE" });
          out[id] = r.ok ? "deleted" : r.status === 404 ? "not_found" : `error ${r.status}`;
        }
        return out;
      },
      async listChats() {
        const ids = [];
        let token = "";
        for (let i = 0; i < 100; i++) {
          const r = await this.rest(`/rest/app-chat/conversations?pageSize=100${token ? "&pageToken=" + encodeURIComponent(token) : ""}`);
          if (!r.ok) throw new Error(`conversations ${r.status}`);
          const j = await r.json();
          for (const c of j.conversations || []) ids.push(c.conversationId);
          token = j.nextPageToken || "";
          if (!token) break;
        }
        return ids;
      },
      locateInput() { return waitFor(this.composer); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
      // Since 2026-10 grok.com streams the answer over a websocket gateway (response.create),
      // so there is no HTTP body to tee. The finished turn is read back from the same endpoints
      // the page uses: response-node (is anything still in flight?) then load-responses (the
      // full assistant message incl. <grok:render> cards, cardAttachmentsJson, webSearchResults).
      async poll(convId, prompt) {
        const base = `${location.origin}/rest/app-chat/conversations/${convId}`;
        const get = async (u, init) => { const r = await fetch(u, { credentials: "include", ...init }); if (!r.ok) throw new Error(`${u.split("?")[0]} ${r.status}`); return r.json(); };
        const nodes = await get(`${base}/response-node?includeThreads=true`);
        const list = nodes.responseNodes || [];
        const human = list.find((n) => n.sender === "human");
        const asst = human && list.find((n) => n.sender === "assistant" && n.parentResponseId === human.responseId);
        if (!asst || (nodes.inflightResponses || []).length) return { state: "pending" };
        const body = JSON.stringify({ responseIds: [human.responseId, asst.responseId] });
        const loaded = await get(`${base}/load-responses`, { method: "POST", headers: { "content-type": "application/json" }, body });
        const rs = loaded.responses || [];
        const h = rs.find((r) => r.responseId === human.responseId), a = rs.find((r) => r.responseId === asst.responseId);
        if (!a || a.partial || typeof a.message !== "string" || !a.message) return { state: "pending" };
        const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
        if (h && norm(h.message).slice(0, 60) !== norm(prompt).slice(0, 60)) return { state: "mismatch" };
        // Isolation evidence: conversations_v2 says whether the chat is private (`temporary`), the node list how many turns.
        let temporary = null;
        try { const c = await get(`${location.origin}/rest/app-chat/conversations_v2/${convId}`); temporary = !!(c.conversation && c.conversation.temporary); } catch (_) {}
        return { state: "done", response: a, isolation: { chatId: convId, temporary, humanTurns: list.filter((n) => n.sender === "human").length, evidence: `conversations_v2 temporary=${temporary}` } };
      },
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
      isolationState() {
        const on = !!pick(this.incognitoOff) && /incognito/.test(location.search);
        return { temporary: on, newChat: location.pathname === "/new", evidence: `page ${location.pathname}${location.search}${pick(this.incognitoOff) ? ", 'Exit incognito' button" : ", not incognito"}` };
      },
      async api(path, init) {
        return fetch(`${location.origin}/api/organizations/${await this.orgId()}${path}`, { credentials: "include", ...(init || {}) });
      },
      // Settings > Memory: "Search and reference chats" = enabled_saffron_search, "Generate memory from chats" =
      // enabled_saffron. null = never switched on (both switches showed off for null on 2026-10-14).
      async memoryStatus() {
        const r = await fetch(`${location.origin}/api/account`, { credentials: "include" });
        if (!r.ok) return { status: "unknown", detail: `/api/account ${r.status}` };
        const s = (await r.json()).settings || {};
        if (!("enabled_saffron" in s) && !("enabled_saffron_search" in s)) return { status: "unknown", detail: "account settings have no enabled_saffron*" };
        const on = s.enabled_saffron === true || s.enabled_saffron_search === true;
        return { status: on ? "on" : "off", detail: `generate memory (enabled_saffron)=${s.enabled_saffron}, search past chats (enabled_saffron_search)=${s.enabled_saffron_search}` };
      },
      async deleteChats(ids) {
        const out = {};
        for (const id of ids) {
          const r = await this.api(`/chat_conversations/${id}`, { method: "DELETE" });
          out[id] = r.ok ? "deleted" : r.status === 404 ? "not_found" : `error ${r.status}`;
        }
        return out;
      },
      async listChats() {
        const r = await this.api("/chat_conversations");
        if (!r.ok) throw new Error(`chat_conversations ${r.status}`);
        return (await r.json()).map((c) => c.uuid);
      },
      locateInput() { return waitFor(this.composer); },
      // Claude only, for now: the other two drivers are untouched deliberately.
      attach(files) { return attachFiles(this.composer, files); },
      submit() { return submitViaButtonOrEnter(this.send, this.composer); },
      // Since 2026-10 claude.ai sends and streams over /claudeai-rpc (connect+proto), so there is no
      // JSON completion for capture to tee. The finished turn is read back from the REST endpoint the
      // old UI used, which still serves the whole conversation: GET chat_conversations/<id>?tree=True.
      // Nothing is served for a turn that is still streaming (the assistant message appears whole, with
      // stop_reason, when it ends), so "finished" is: the leaf is an assistant message with a final
      // stop_reason, no block still open, identical on two consecutive polls, and the page agrees
      // (no Stop button, the message's data-is-streaming is "false").
      _org: null, _seen: null,
      async orgId() {
        if (this._org) return this._org;
        for (const e of performance.getEntriesByType("resource")) {
          const m = /\/api\/organizations\/([0-9a-f-]{36})\//.exec(e.name);
          if (m) return (this._org = m[1]);
        }
        const r = await fetch(`${location.origin}/api/organizations`, { credentials: "include" });
        if (!r.ok) throw new Error(`/api/organizations ${r.status}`);
        const orgs = await r.json();
        const o = orgs.find((x) => (x.capabilities || []).includes("chat")) || orgs[0];
        if (!o) throw new Error("no organization");
        return (this._org = o.uuid);
      },
      async poll(_convId, prompt) {
        const m = /^\/chat\/([0-9a-f-]{36})/.exec(location.pathname);
        if (!m) return { state: "pending" };
        const convId = m[1];
        const r = await fetch(`${location.origin}/api/organizations/${await this.orgId()}/chat_conversations/${convId}?tree=True&rendering_mode=messages&render_all_tools=true`, { credentials: "include" });
        if (!r.ok) throw new Error(`chat_conversations ${r.status}`);
        const conv = await r.json();
        const byId = {}; for (const x of conv.chat_messages || []) byId[x.uuid] = x;
        const leaf = byId[conv.current_leaf_message_uuid] || (conv.chat_messages || []).slice(-1)[0];
        if (!leaf || leaf.sender !== "assistant") return { state: "pending" };
        const human = byId[leaf.parent_message_uuid];
        const norm = (t) => String(t || "").replace(/\s+/g, " ").trim();
        const said = human && (human.text || (human.content || []).filter((b) => b.type === "text").map((b) => b.text).join(" "));
        if (human && norm(said).slice(0, 60) !== norm(prompt).slice(0, 60)) return { state: "mismatch" };
        const blocks = leaf.content || [];
        const open = blocks.some((b) => !b.stop_timestamp);
        const final = !!leaf.stop_reason && !/^(tool_use|pause_turn)$/.test(leaf.stop_reason);
        const hasText = blocks.some((b) => b.type === "text" && (b.text || "").trim());
        const sig = leaf.uuid + "|" + leaf.stop_reason + "|" + blocks.length + "|" + blocks.reduce((n, b) => n + (b.text || "").length + JSON.stringify(b.content || "").length, 0);
        const same = this._seen && this._seen.sig === sig;
        this._seen = { sig, n: same ? this._seen.n + 1 : 1 };
        const stopBtn = [...document.querySelectorAll('button[aria-label*="Stop" i]')].some((b) => b.offsetParent !== null);
        const streaming = !!document.querySelector('[data-is-streaming="true"]');
        if (!(final && !open && hasText && this._seen.n >= 2 && !stopBtn && !streaming)) return { state: "pending" };
        const humanTurns = (conv.chat_messages || []).filter((x) => x.sender === "human").length;
        return { state: "done", response: { convId, model: conv.model || null, message: leaf },
                 isolation: { chatId: convId, temporary: conv.is_temporary === true, humanTurns, evidence: `conversation is_temporary=${conv.is_temporary}` } };
      },
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
    mistral: {
      // Recorded 2026-10-06: Le Chat's "work" UI. Temporary chat = the route /work/temporary-chat
      // (its top-bar link); the composer is a ProseMirror editor and the recording shows no send-button click.
      composer: ['div.ProseMirror[contenteditable="true"]', 'div[contenteditable="true"]'],
      send: ['button[type="submit"]', 'button[aria-label*="Send" i]', 'button[aria-label*="Envoyer" i]'],
      isReady() { return !!pick(this.composer); },
      async startChat({ private: priv }) {
        dismissConsent(); dismissNotice();
        // A fresh page load is the only reliable "new chat": the route is the mode.
        location.assign(priv ? "/work/temporary-chat" : "/work");
        await sleep(4000);
      },
      isolationState() {
        const exit = [...document.querySelectorAll('a[href="/work"], button')].some((e) => /exit temporary chat/i.test(e.innerText || ""));
        const temp = location.pathname === "/work/temporary-chat";
        const msgs = !!document.querySelector('[data-message-author-role], [data-testid*="message" i]');
        return { temporary: temp && exit, newChat: temp ? !msgs : location.pathname === "/work",
                 evidence: `page ${location.pathname}${exit ? ", 'Exit temporary chat' link" : ", no temporary-chat link"}` };
      },
      // tRPC: Le Chat's own client calls these with GET ?batch=1&input=..., mutations with POST.
      async trpc(proc, input, mutate) {
        const u = `${location.origin}/api/trpc/${proc}?batch=1`;
        const body = { 0: { json: input === undefined ? null : input } };
        const r = mutate
          ? await fetch(u, { method: "POST", credentials: "include", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
          : await fetch(`${u}&input=${encodeURIComponent(JSON.stringify(input === undefined ? { 0: { json: null, meta: { values: ["undefined"], v: 1 } } } : body))}`, { credentials: "include" });
        const j = await r.json().catch(() => null);
        return { status: r.status, data: j && j[0] && j[0].result ? j[0].result.data.json : undefined };
      },
      // Settings > Privacy > Personalization > "Knowledge" ("save and organize key insights from your chats").
      async memoryStatus() {
        const k = await this.trpc("user.getKnowledgeToggleState");
        if (!k.data || typeof k.data.enabled !== "boolean") return { status: "unknown", detail: `getKnowledgeToggleState ${k.status}` };
        return { status: k.data.enabled ? "on" : "off", detail: `Knowledge enabled=${k.data.enabled}` };
      },
      async deleteChats(ids) {
        const out = {};
        for (const id of ids) {
          const r = await this.trpc("chat.delete", { id }, true);
          out[id] = r.status === 200 ? "deleted" : r.status === 404 ? "not_found" : `error ${r.status}`;
        }
        return out;
      },
      async listChats() {
        const r = await this.trpc("chat.last", { chatVisibility: "private", chatPermission: "write", includeProjectChats: true, includeScheduledTaskChats: true, direction: "forward" });
        if (!r.data) throw new Error(`chat.last ${r.status}`);
        return (r.data.items || []).map((c) => c.id);
      },
      // Web search must be ON for every question. Find the toggle, log what we saw, switch it on if it is off.
      async ensureWebSearch() {
        const log = Probe.log.make("mistral");
        const re = /web ?search|recherche (sur le )?web|search the web|recherche/i;
        const cands = [...document.querySelectorAll('button,[role="button"],[role="switch"],[role="menuitemcheckbox"],[role="checkbox"],label')]
          .filter((b) => b.offsetParent !== null && re.test((b.innerText || "") + " " + (b.getAttribute("aria-label") || "")));
        log.info("web-search candidates: " + JSON.stringify(cands.slice(0, 5).map((b) => ({ t: (b.innerText || "").trim().slice(0, 40), a: b.getAttribute("aria-label"), p: b.getAttribute("aria-pressed"), c: b.getAttribute("aria-checked"), s: b.getAttribute("data-state") }))));
        const btns = [...document.querySelectorAll("button")].filter((b) => b.offsetParent !== null).map((b) => (b.getAttribute("aria-label") || (b.innerText || "").trim() || "?").slice(0, 30));
        log.info("buttons: " + btns.slice(0, 30).join(" | "));
        for (const b of cands) {
          const on = b.getAttribute("aria-pressed") === "true" || b.getAttribute("aria-checked") === "true" || b.getAttribute("data-state") === "on" || b.getAttribute("data-state") === "checked";
          const off = b.getAttribute("aria-pressed") === "false" || b.getAttribute("aria-checked") === "false" || b.getAttribute("data-state") === "off" || b.getAttribute("data-state") === "unchecked";
          if (off && !on) { realClick(b); log.info("web search toggled ON"); await sleep(400); }
        }
      },
      async locateInput() {
        const el = await waitFor(this.composer);
        await this.ensureWebSearch();
        return el;
      },
      submit() { return submitViaButtonOrEnter(this.send, this.composer, 2000); },
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
