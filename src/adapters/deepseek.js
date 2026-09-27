// DeepSeek adapter (chat.deepseek.com). Requires login.
// NOTE: selectors are best-effort and MUST be verified with the popup's
// "Capture page" button before trusting a real run. Update only this block.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const B = Probe.adapterBase;
  const log = Probe.log.make("deepseek");

  const SELECTORS = {
    composer: [
      "textarea#chat-input",
      'textarea[placeholder*="message" i]',
      'div[contenteditable="true"]',
      "textarea",
    ],
    sendButton: [
      'div[role="button"][aria-label*="send" i]',
      'button[aria-label*="send" i]',
      'button[type="submit"]',
    ],
    stopButton: ['div[role="button"][aria-label*="stop" i]', 'button[aria-label*="stop" i]'],
    newChat: [
      'a[href="/"]',
      '[class*="new-chat" i]',
      'button[aria-label*="new chat" i]',
    ],
    // DeepSeek renders the assistant answer in .ds-markdown; the assistant-
    // specific class avoids matching anything the user typed.
    assistantTurn: [
      "div.ds-assistant-message-main-content",
      'div[class*="ds-markdown"]',
      'div[class*="markdown" i]',
    ],
    loginMarker: ["textarea#chat-input", 'textarea[placeholder*="message" i]', "textarea"],
    modelLabel: ['button[aria-label*="model" i]', '[class*="model" i] button'],
  };

  const impl = {
    id: "deepseek",
    homeUrl: "https://chat.deepseek.com/",
    matchPattern: "https://chat.deepseek.com/*",
    quiescenceMs: 1800,
    responseTimeoutMs: 180000,

    hostMatch(h) {
      return h.endsWith("chat.deepseek.com");
    },
    isReady() {
      return !!B.pick(SELECTORS.loginMarker);
    },
    modelLabel() {
      const el = B.pick(SELECTORS.modelLabel);
      return el ? B.textOf(el).split("\n")[0] || null : null;
    },
    async startFreshChat() {
      // DeepSeek has no private mode (privacy handled by purgeHistory once/run).
      B.dismissConsent();
      B.dismissNotice();
      B.dismissDialog(/new|clear|continue|confirm|^ok$|yes|start/i);
      // Prefer an in-app "New chat" (DeepSeek uses div[role=button]); reload last.
      if (!B.clickByText(/^\s*new chat\s*$/i) && !B.clickFirst(SELECTORS.newChat)) {
        if (location.pathname !== "/") location.assign("/");
      }
      await Probe.cadence.sleep(800);
      const el = await B.waitFor(SELECTORS.composer, { timeoutMs: 20000 });
      if ((el.innerText || el.value || "").trim()) Probe.injector.clear(el);
    },

    // Privacy for DeepSeek = delete all chats via Settings → Data. Best-effort,
    // by text (DeepSeek uses div[role=button]); non-fatal if the UI differs.
    async purgeHistory() {
      const sleep = Probe.cadence.sleep;
      const dlgText = () => (document.querySelector('[role="dialog"]') || {}).innerText || "";
      if (!/settings/i.test(dlgText())) {
        B.clickByText(/^settings$/i) || B.clickFirst(['[aria-label*="setting" i]']);
        await sleep(900);
      }
      B.clickByText(/^data$/i);
      await sleep(500);
      if (B.clickByText(/delete all (chats|conversations)|clear all (chats|conversations)/i)) {
        await sleep(700);
        B.clickByText(/^(delete|delete all|confirm|yes|ok)$/i);
        await sleep(900);
        log.info("purged chat history");
      } else {
        log.warn("'delete all chats' control not found in Settings (capture the Settings page to refine)");
      }
      B.clickFirst(['[aria-label*="close" i]', 'button[aria-label*="close" i]']);
      await sleep(400);
    },
    async locateInput() {
      return B.waitFor(SELECTORS.composer, { timeoutMs: 15000 });
    },
    async submit() {
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
      if (!el) throw new Error("deepseek: composer missing at submit");
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true }));
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
