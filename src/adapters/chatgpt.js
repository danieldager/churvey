// ChatGPT adapter (chatgpt.com / chat.openai.com).
// SELECTORS are the single place to update on a deploy-driven UI change.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const B = Probe.adapterBase;

  const SELECTORS = {
    composer: ['#prompt-textarea', 'div[contenteditable="true"]#prompt-textarea', 'div.ProseMirror[contenteditable="true"]'],
    sendButton: ['button[data-testid="send-button"]', 'button[aria-label="Send prompt"]', 'button[aria-label*="Send" i]'],
    stopButton: ['button[data-testid="stop-button"]', 'button[aria-label="Stop streaming"]', 'button[aria-label*="Stop" i]'],
    newChat: [
      'a[data-testid="create-new-chat-button"]',
      'button[aria-label*="New chat" i]',
      'a[aria-label*="New chat" i]',
      'nav a[href="/"]',
    ],
    assistantTurn: ['[data-message-author-role="assistant"]'],
    // Login gate: composer only exists once authenticated and loaded.
    loginMarker: ['#prompt-textarea', 'div.ProseMirror[contenteditable="true"]'],
    modelLabel: [
      '[data-testid="model-switcher-dropdown-button"]',
      'button[aria-label*="Model selector" i]',
      'button[aria-haspopup="menu"] span',
    ],
  };

  const impl = {
    id: "chatgpt",
    homeUrl: "https://chatgpt.com/",
    matchPattern: "https://chatgpt.com/*",
    quiescenceMs: 1300,
    responseTimeoutMs: 150000,

    hostMatch(h) {
      return h.endsWith("chatgpt.com") || h.endsWith("chat.openai.com");
    },

    isReady() {
      return !!B.pick(SELECTORS.loginMarker);
    },

    modelLabel() {
      const el = B.pick(SELECTORS.modelLabel);
      return el ? B.textOf(el) || null : null;
    },

    async startFreshChat(opts = {}) {
      const confirmRe = /new chat|clear|continue|confirm|^ok$|yes|delete|start/i;
      B.dismissConsent();
      B.dismissNotice();
      B.dismissDialog(confirmRe);

      if (opts.private) {
        // Temporary Chat = ChatGPT's private mode. Drive it via the URL param;
        // navigating gives a guaranteed-fresh temporary chat each item. The
        // reload is safe (stable owner id re-claims this same item).
        const isTemp = new URLSearchParams(location.search).get("temporary-chat") === "true";
        const hasMsgs = !!B.pick(SELECTORS.assistantTurn);
        if (!isTemp || hasMsgs) {
          location.assign("/?temporary-chat=true");
          await Probe.cadence.sleep(4000); // page reloads; this item resumes after
          return;
        }
      } else if (!B.clickFirst(SELECTORS.newChat)) {
        if (location.pathname !== "/") location.assign("/");
      }

      await Probe.cadence.sleep(700);
      if (B.dismissDialog(confirmRe)) await Probe.cadence.sleep(500);
      const el = await B.waitFor(SELECTORS.composer, { timeoutMs: 20000 });
      if ((el.innerText || "").trim()) Probe.injector.clear(el);
    },

    async locateInput() {
      return B.waitFor(SELECTORS.composer, { timeoutMs: 15000 });
    },

    async submit() {
      // Wait for send button to become enabled, then click.
      const start = Date.now();
      while (Date.now() - start < 8000) {
        const btn = B.pick(SELECTORS.sendButton);
        if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") {
          btn.click();
          return;
        }
        await Probe.cadence.sleep(150);
      }
      // Fallback: Enter key on the composer.
      const el = B.pick(SELECTORS.composer);
      if (el) {
        el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
      } else {
        throw new Error("chatgpt: send button never enabled and composer missing");
      }
    },

    isStreaming() {
      // Stop button visible == still generating.
      return !!B.pick(SELECTORS.stopButton);
    },

    getResponseNode() {
      return B.pick(SELECTORS.assistantTurn, { last: true });
    },

    extractResponseText() {
      const node = this.getResponseNode();
      return B.textOf(node);
    },

    chatUrl() {
      return location.href;
    },
  };

  impl.SELECTORS = SELECTORS;
  Probe.registry = Probe.registry || { _list: [] };
  Probe.registry._list.push(Probe.adapterBase.makeAdapter(impl));
})();
