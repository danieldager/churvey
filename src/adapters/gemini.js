// Gemini adapter (gemini.google.com).
// NOTE: selectors are best-effort and MUST be verified against the live DOM
// before a real run. Gemini uses a Quill (.ql-editor) composer and Angular
// custom elements; markup changes between deploys. Update only this block.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const B = Probe.adapterBase;
  const log = Probe.log.make("gemini");

  const SELECTORS = {
    composer: [
      'rich-textarea div.ql-editor[contenteditable="true"]',
      'div.ql-editor[contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"]',
      'div[contenteditable="true"]',
    ],
    sendButton: [
      'button[aria-label*="Send" i]',
      'button.send-button',
      'button[mattooltip*="Send" i]',
    ],
    stopButton: ['button[aria-label*="Stop" i]', 'button.stop', 'button[aria-label*="Cancel" i]'],
    newChat: [
      'expandable-button[data-test-id="new-chat-button"] button',
      'button[aria-label*="New chat" i]',
      '[data-test-id="new-chat-button"]',
    ],
    // Verified: the top-right button has aria-label "Temporary chat".
    temporary: [
      'button[aria-label="Temporary chat"]',
      'button[aria-label*="temporary" i]',
      '[role="button"][aria-label*="temporary" i]',
      'a[aria-label*="temporary" i]',
    ],
    assistantTurn: ['model-response .model-response-text', 'message-content', '.model-response-text', '.response-container'],
    loginMarker: ['div.ql-editor[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]'],
    modelLabel: ['button[aria-label*="model" i]', '.current-mode-title', 'bard-mode-switcher button'],
  };

  const impl = {
    id: "gemini",
    homeUrl: "https://gemini.google.com/app",
    matchPattern: "https://gemini.google.com/*",
    quiescenceMs: 1500,
    responseTimeoutMs: 150000,

    hostMatch(h) {
      return h.endsWith("gemini.google.com");
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
      if (opts.private) {
        if (!B.clickByText(/temporary chat/i) && !B.clickFirst(SELECTORS.temporary)) {
          log.warn("temporary-chat control not found; running NON-private (verify via Capture page)");
          if (!B.clickFirst(SELECTORS.newChat) && location.pathname !== "/app") location.assign("/app");
        }
      } else if (!B.clickFirst(SELECTORS.newChat)) {
        if (location.pathname !== "/app") location.assign("/app");
      }
      await Probe.cadence.sleep(900);
      const el = await B.waitFor(SELECTORS.composer, { timeoutMs: 20000 });
      if ((el.innerText || "").trim()) Probe.injector.clear(el);
    },
    async locateInput() {
      return B.waitFor(SELECTORS.composer, { timeoutMs: 15000 });
    },
    async submit() {
      const start = Date.now();
      while (Date.now() - start < 8000) {
        const btn = B.pick(SELECTORS.sendButton);
        if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") {
          btn.click();
          return;
        }
        await Probe.cadence.sleep(150);
      }
      const el = B.pick(SELECTORS.composer);
      if (el) {
        el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
      } else {
        throw new Error("gemini: send button never enabled and composer missing");
      }
    },
    isStreaming() {
      return !!B.pick(SELECTORS.stopButton);
    },
    getResponseNode() {
      return B.pick(SELECTORS.assistantTurn, { last: true });
    },
    extractResponseText() {
      return B.textOf(this.getResponseNode());
    },
    chatUrl() {
      return location.href;
    },
  };

  impl.SELECTORS = SELECTORS;
  Probe.registry = Probe.registry || { _list: [] };
  Probe.registry._list.push(Probe.adapterBase.makeAdapter(impl));
})();
