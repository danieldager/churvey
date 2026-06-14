// Grok adapter (grok.com). Selectors verified against a live logged-in capture.
// Update only this SELECTORS block on UI drift (re-run popup "Capture page").
(() => {
  const Probe = (globalThis.Probe ||= {});
  const B = Probe.adapterBase;
  const log = Probe.log.make("grok");

  const SELECTORS = {
    // TipTap/ProseMirror contenteditable labeled "Ask Grok anything".
    composer: [
      'div[contenteditable="true"][role="textbox"][aria-label*="Grok" i]',
      'div.tiptap[contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"]',
    ],
    // Send button is hidden until text is present; Enter also submits. Best-effort.
    sendButton: [
      'button[data-testid="send-button"]',
      'button[aria-label="Submit"]',
      'button[aria-label*="Submit" i]',
      'button[type="submit"]',
    ],
    stopButton: [
      'button[data-testid="stop-button"]',
      'button[aria-label*="Stop" i]',
      'button[aria-label="Stop model response"]',
    ],
    // SPA home link → fresh chat (clickFirst skips off-site links). location
    // fallback in startFreshChat is safe (pathname guard prevents reload loops).
    newChat: ['a[href="/"]'],
    // Best-effort: Grok's top-right private button is likely a div[role=button]
    // (the old-diagnostics capture couldn't enumerate it). Cover common shapes.
    private: [
      'button[aria-label*="private" i]',
      '[role="button"][aria-label*="private" i]',
      'a[aria-label*="private" i]',
      'button[aria-label*="incognito" i]',
      '[role="button"][aria-label*="incognito" i]',
      'button[aria-label*="ephemeral" i]',
      '[role="button"][aria-label*="ephemeral" i]',
      'a[href*="private" i]',
    ],
    // Only the assistant bubble — NOT div.message-bubble (that also matches the
    // user's own question bubble, which caused prompt-echo captures).
    assistantTurn: ['[data-testid="assistant-message"]'],
    // Key readiness off the REAL composer, not the hidden dummy textarea.
    loginMarker: [
      'div[contenteditable="true"][role="textbox"][aria-label*="Grok" i]',
      'div.tiptap[contenteditable="true"]',
    ],
    modelLabel: ['#model-select-trigger', 'button[aria-label="Model select"]'],
  };

  const impl = {
    id: "grok",
    homeUrl: "https://grok.com/",
    matchPattern: "https://grok.com/*",
    quiescenceMs: 2000, // no reliable stop-button signal; lean on quiescence
    responseTimeoutMs: 180000,

    hostMatch(h) {
      return h.endsWith("grok.com");
    },
    isReady() {
      return !!B.pick(SELECTORS.loginMarker);
    },
    modelLabel() {
      const el = B.pick(SELECTORS.modelLabel);
      return el ? B.textOf(el).split("\n")[0] || null : null;
    },
    async startFreshChat(opts = {}) {
      B.dismissConsent();
      B.dismissNotice();
      B.dismissDialog(/new|clear|continue|confirm|^ok$|yes|start/i);
      if (opts.private) {
        // Cmd/Ctrl+Shift+J opens a fresh private chat (verified shortcut).
        B.pressKey("j", { meta: true, shift: true });
        await Probe.cadence.sleep(600);
        // Fallback: a private button, if the shortcut didn't register.
        if (!B.pick(SELECTORS.composer)) B.clickFirst(SELECTORS.private);
      } else if (!B.clickFirst(SELECTORS.newChat)) {
        if (location.pathname !== "/") location.assign("/");
      }
      await Probe.cadence.sleep(800);
      const el = await B.waitFor(SELECTORS.composer, { timeoutMs: 20000 });
      if ((el.innerText || el.value || "").trim()) Probe.injector.clear(el);
    },
    async locateInput() {
      return B.waitFor(SELECTORS.composer, { timeoutMs: 15000 });
    },
    async submit() {
      // Brief look for a send button; otherwise Enter (works for Grok's editor).
      const start = Date.now();
      while (Date.now() - start < 2500) {
        const btn = B.pick(SELECTORS.sendButton);
        if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") {
          btn.click();
          return;
        }
        await Probe.cadence.sleep(150);
      }
      const el = B.pick(SELECTORS.composer);
      if (!el) throw new Error("grok: composer missing at submit");
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true }));
    },
    isStreaming() {
      return !!B.pick(SELECTORS.stopButton);
    },
    getResponseNode() {
      return B.pick(SELECTORS.assistantTurn, { last: true });
    },
    extractResponseText() {
      const node = this.getResponseNode();
      if (!node) return "";
      // Strip Grok's "Thought for Ns" reasoning block and action buttons so we
      // keep just the answer text.
      const clone = node.cloneNode(true);
      clone.querySelectorAll(".thinking-container, button").forEach((n) => n.remove());
      return (clone.innerText || "").trim();
    },
    chatUrl() {
      return location.href;
    },
  };

  impl.SELECTORS = SELECTORS;
  Probe.registry = Probe.registry || { _list: [] };
  Probe.registry._list.push(Probe.adapterBase.makeAdapter(impl));
})();
