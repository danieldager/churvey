// Claude adapter (claude.ai).
// NOTE: selectors are best-effort and MUST be verified against the live DOM
// (DevTools) before a real run — Claude's markup changes between deploys. Update
// only this SELECTORS block when they drift.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const B = Probe.adapterBase;
  const log = Probe.log.make("claude");

  const SELECTORS = {
    composer: [
      'div[contenteditable="true"].ProseMirror',
      'fieldset div[contenteditable="true"]',
      'div[contenteditable="true"]',
    ],
    sendButton: ['button[aria-label="Send message"]', 'button[aria-label*="Send" i]'],
    stopButton: ['button[aria-label*="Stop" i]', 'button[aria-label="Stop response"]'],
    newChat: ['a[href="/new"]', 'button[aria-label*="New chat" i]', 'a[aria-label*="New chat" i]'],
    // The ghost icon (top-right) — starts an incognito chat (Claude's private mode).
    incognito: ['button[aria-label*="incognito" i]', 'a[aria-label*="incognito" i]'],
    assistantTurn: ['div.font-claude-message', '[data-testid="assistant-message"]', '[data-is-streaming]'],
    loginMarker: ['div[contenteditable="true"].ProseMirror', 'div[contenteditable="true"]'],
    modelLabel: ['button[data-testid="model-selector-dropdown"]', 'button[aria-haspopup="menu"]'],
  };

  const impl = {
    id: "claude",
    homeUrl: "https://claude.ai/new",
    matchPattern: "https://claude.ai/*",
    quiescenceMs: 1300,
    responseTimeoutMs: 150000,

    hostMatch(h) {
      return h.endsWith("claude.ai");
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
        // Click the ghost to start a fresh incognito chat.
        if (!B.clickFirst(SELECTORS.incognito)) {
          log.warn("incognito button not found; running NON-private (verify selector via Capture page)");
          if (!B.clickFirst(SELECTORS.newChat) && location.pathname !== "/new") location.assign("/new");
        }
      } else if (!B.clickFirst(SELECTORS.newChat)) {
        if (location.pathname !== "/new") location.assign("/new");
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
        throw new Error("claude: send button never enabled and composer missing");
      }
    },
    isStreaming() {
      if (B.pick(SELECTORS.stopButton)) return true;
      const streamingNode = document.querySelector('[data-is-streaming="true"]');
      return !!streamingNode;
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
