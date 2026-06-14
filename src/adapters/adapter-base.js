// Shared helpers for provider adapters + the adapter contract (as JSDoc).
//
// Adapter contract — each adapter is an object:
//   id: string
//   hostMatch(hostname): boolean
//   isReady(): boolean                 page loaded AND user logged in
//   modelLabel(): string|null          visible model name, else null
//   startFreshChat(): Promise<void>    open a brand-new conversation
//   locateInput(): Promise<HTMLElement>
//   submit(): Promise<void>            send the composed message
//   isStreaming(): boolean             true while a response is generating
//   getResponseNode(): HTMLElement|null  latest assistant turn
//   extractResponseText(): string      full text of latest assistant turn
//   chatUrl(): string|null
//
// typeQuestion() and detectResponseComplete() are provided generically below by
// makeAdapter(); adapters supply the primitives above.
(() => {
  const Probe = (globalThis.Probe ||= {});

  // Try each selector in order; return the first (optionally last) match.
  function pick(selectors, { last = false } = {}) {
    for (const sel of selectors) {
      const nodes = document.querySelectorAll(sel);
      if (nodes.length) return last ? nodes[nodes.length - 1] : nodes[0];
    }
    return null;
  }

  function pickAll(selectors) {
    for (const sel of selectors) {
      const nodes = document.querySelectorAll(sel);
      if (nodes.length) return Array.from(nodes);
    }
    return [];
  }

  // Wait until a selector resolves to an element, or reject on timeout.
  async function waitFor(selectors, { timeoutMs = 15000, last = false } = {}) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const el = pick(selectors, { last });
      if (el) return el;
      await Probe.cadence.sleep(150);
    }
    throw new Error(`waitFor timed out: ${selectors.join(" | ")}`);
  }

  // Click the first matching element — but NEVER follow an off-site anchor
  // (cookie-consent banners embed cross-origin links like cookiepedia.co.uk that
  // would otherwise open a stray tab when a selector accidentally matches them).
  function clickFirst(selectors) {
    for (const sel of selectors) {
      for (const el of document.querySelectorAll(sel)) {
        if (el.tagName === "A" && el.getAttribute("href")) {
          try {
            const u = new URL(el.href, location.href);
            if (u.origin !== location.origin) continue; // skip off-site link
          } catch (_) {}
        }
        el.click();
        return true;
      }
    }
    return false;
  }

  // Dismiss a cookie-consent banner (OneTrust and common variants) so it can't
  // overlay the composer or get mis-clicked. Clicks an "accept"-type button only.
  function dismissConsent() {
    const ids = [
      "#onetrust-accept-btn-handler",
      "#accept-recommended-btn-handler",
      ".onetrust-close-btn-handler",
      'button[aria-label="Accept all"]',
    ];
    for (const s of ids) {
      const el = document.querySelector(s);
      if (el && el.offsetParent !== null) {
        el.click();
        return true;
      }
    }
    const re = /^(accept all|accept all cookies|accept cookies|accept|i agree|agree|allow all|got it)$/i;
    const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
    const hit = btns.find(
      (b) => b.offsetParent !== null && re.test((b.innerText || b.getAttribute("aria-label") || "").trim())
    );
    if (hit) {
      hit.click();
      return true;
    }
    return false;
  }

  function textOf(el) {
    return el ? (el.innerText || el.textContent || "").trim() : "";
  }

  // If a modal/dialog is open, click the first button whose label matches
  // `confirmRe`. Returns true if it clicked something. Defensive only — the real
  // fix for an unexpected dialog is usually a selector correction.
  function dismissDialog(confirmRe) {
    const dlg = pick(['[role="dialog"]', '[aria-modal="true"]', "dialog[open]"]);
    if (!dlg) return false;
    // Never treat a cookie/privacy consent dialog as a chat confirmation — its
    // buttons ("Clear", "Confirm My Choices") would match confirm regexes.
    const label = (dlg.getAttribute("aria-label") || "") + " " + (dlg.id || "");
    if (dlg.closest("#onetrust-consent-sdk") || /privacy|cookie|consent|preference/i.test(label)) {
      return false;
    }
    const btns = Array.from(dlg.querySelectorAll("button"));
    const hit = btns.find((b) =>
      confirmRe.test((b.innerText || b.getAttribute("aria-label") || "").trim())
    );
    if (hit) {
      hit.click();
      return true;
    }
    return false;
  }

  // Wraps an adapter's primitives with the generic typeQuestion /
  // detectResponseComplete behaviour so every provider behaves identically.
  function makeAdapter(impl) {
    return {
      ...impl,

      async typeQuestion(el, text) {
        return Probe.injector.type(el, text, { retries: 1 });
      },

      async detectResponseComplete({ timeoutMs } = {}) {
        const res = await Probe.watcher.waitForComplete({
          getResponseNode: () => impl.getResponseNode(),
          isStreaming: () => impl.isStreaming(),
          extractText: () => impl.extractResponseText(),
          quiescenceMs: impl.quiescenceMs ?? 1200,
          timeoutMs: timeoutMs ?? impl.responseTimeoutMs ?? 120000,
        });
        return { ...res, modelLabel: impl.modelLabel() };
      },
    };
  }

  // Dispatch a keyboard shortcut. `meta:true` maps to Cmd on macOS, Ctrl
  // elsewhere. Fires on document/body/activeElement to maximize the chance the
  // app's global hotkey handler catches it.
  function pressKey(key, mods = {}) {
    const isMac = /mac/i.test((navigator.platform || navigator.userAgent || ""));
    const opts = {
      key,
      code: "Key" + key.toUpperCase(),
      bubbles: true,
      cancelable: true,
      metaKey: !!mods.meta && isMac,
      ctrlKey: (!!mods.meta && !isMac) || !!mods.ctrl,
      shiftKey: !!mods.shift,
      altKey: !!mods.alt,
    };
    for (const t of [document, document.body, document.activeElement].filter(Boolean)) {
      t.dispatchEvent(new KeyboardEvent("keydown", opts));
      t.dispatchEvent(new KeyboardEvent("keyup", opts));
    }
  }

  // Click the first visible clickable whose trimmed text matches `re`. Handles
  // apps that use <div role="button"> with no aria-label (e.g. DeepSeek).
  function clickByText(re, root = document) {
    const els = root.querySelectorAll('button, a, [role="button"], [role="menuitem"]');
    for (const el of els) {
      if (el.offsetParent === null) continue;
      const t = (el.innerText || "").trim();
      if (t && re.test(t)) {
        el.click();
        return true;
      }
    }
    return false;
  }

  // Dismiss promo / interstitial / "log in to continue" notices by clicking a
  // soft-dismiss button. NEVER clicks login/signup/accept-tracking actions.
  // Handles e.g. Gemini "Our biggest I/O updates" (Not now) and ChatGPT
  // "Thanks for trying ChatGPT" (Stay logged out).
  function dismissNotice() {
    const re = /^(not now|no thanks|no,? thanks|maybe later|later|skip|dismiss|got it|continue|stay logged out|close|done)$/i;
    const scopes = document.querySelectorAll('[role="dialog"], [aria-modal="true"], dialog[open]');
    for (const dlg of scopes) {
      const label = (dlg.getAttribute("aria-label") || "") + " " + (dlg.id || "");
      if (dlg.closest("#onetrust-consent-sdk") || /privacy|cookie|consent|preference/i.test(label)) continue;
      const btns = Array.from(dlg.querySelectorAll('button, a[role="button"], [role="button"]'));
      const hit = btns.find((b) => re.test((b.innerText || b.getAttribute("aria-label") || "").trim()));
      if (hit) {
        hit.click();
        return true;
      }
    }
    return false;
  }

  // "Provider busy" / rate-limit detection. Checked against short alert/toast/
  // error/banner elements only, to avoid matching an answer that happens to use
  // these words.
  const OVERLOAD_RE = /(high demand|at capacity|too many requests|rate.?limit(ed)?|try again (later|in a)|temporarily unavailable|overloaded|servers? are busy|something went wrong)/i;

  function isOverloaded() {
    const sels = ['[role="alert"]', '[class*="toast" i]', '[class*="error" i]', '[class*="banner" i]'];
    for (const s of sels) {
      for (const el of document.querySelectorAll(s)) {
        if (el.offsetParent === null) continue; // not visible
        const t = (el.innerText || "").trim();
        if (t && t.length < 300 && OVERLOAD_RE.test(t)) return true;
      }
    }
    return false;
  }

  Probe.adapterBase = {
    pick, pickAll, waitFor, clickFirst, clickByText, pressKey, textOf,
    dismissDialog, dismissConsent, dismissNotice, isOverloaded, OVERLOAD_RE, makeAdapter,
  };
})();
