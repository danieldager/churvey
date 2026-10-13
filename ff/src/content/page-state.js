// What the PAGE says, independent of the network: is a limit banner, a login wall or a captcha in the way
// (pageStatus), and what answer is rendered right now (readAnswer, the DOM fallback when no stream or poll
// capture lands). Read-only; never clicks. Selectors are per provider where verified, generic otherwise.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const isVisible = (el) => !!el && (el.offsetParent !== null || (el.getClientRects && el.getClientRects().length > 0))
    && el.getBoundingClientRect().width > 0;
  const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
  const q = (sel, root = document) => { try { return [...root.querySelectorAll(sel)]; } catch (_) { return []; } };
  const anyVisible = (sel) => q(sel).some(isVisible);

  // ---- status ---------------------------------------------------------------------------------------
  // A banner, not prose: only short elements outside the conversation itself are read, so an answer that
  // talks about rate limits never trips this.
  const LIMIT_RE = new RegExp([
    "(message|usage|daily|hourly|weekly|monthly|chat|request|rate|free)\\s+(limit|quota|cap)\\b",
    "(reached|hit|exceeded|exhausted|atteint|d[ée]pass[ée])\\b.{0,50}\\b(limit|quota|limite)",
    "limite\\s+(de\\s+|d['’])?(messages?|utilisation|quotidienne|journali[èe]re|atteinte)",
    "out of (free )?(messages|prompts|queries|questions)",
    "too many (requests|messages|prompts)", "trop de (requ[êe]tes|messages)",
    "(upgrade|passez)\\b.{0,50}\\b(to continue|continuer|more messages|plus de messages)",
    "(come back|try again|reviens?|r[ée]essayez)\\b.{0,40}\\b(later|tomorrow|plus tard|demain|at \\d|in \\d|dans \\d)",
    "your limit (will )?reset", "(limit|limite)s? (resets?|r[ée]initialis)",
  ].join("|"), "i");
  const LOGIN_BTN_RE = /^(log ?in|sign ?in|sign up|log in or sign up|se connecter|connexion|s['’]inscrire|continue with google|continuer avec google)$/i;
  const CHALLENGE_TITLE_RE = /just a moment|un instant|attention required|verify you are human|checking your browser|v[ée]rification/i;
  const CHALLENGE_TEXT_RE = /captcha|verify (that )?you are (a )?human|v[ée]rifiez que vous [êe]tes (un )?humain|checking if the site connection is secure|performing security verification/i;
  const CONVERSATION_SEL = '[data-message-author-role], model-response, user-query, [data-is-streaming], .ds-markdown, [class*="response-content-markdown"], [class*="markdown"], [data-testid*="message" i], [data-testid*="user-message"], [class*="prose"]';
  const LOGIN_PATH_RE = /^\/(login|log-in|signin|sign-in|sign_in|auth\/login|auth\/signin|welcome|logout)(\/|$)|^\/auth(\/|$)/i;

  function pageStatus() {
    // 1. captcha / Cloudflare interstitial: nothing else on the page is meaningful.
    const frames = q('iframe[src*="challenges.cloudflare.com"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').filter((f) => {
      const r = f.getBoundingClientRect(); return r.width > 40 && r.height > 40 && isVisible(f);
    });
    const bodyText = norm(document.body && document.body.innerText);
    if (CHALLENGE_TITLE_RE.test(document.title) && bodyText.length < 1500) return { state: "challenge", text: norm(document.title + " " + bodyText).slice(0, 300) };
    if (frames.length || anyVisible("#challenge-form, #cf-challenge-running, .cf-turnstile, #px-captcha")
        || (bodyText.length < 700 && CHALLENGE_TEXT_RE.test(bodyText))) {
      return { state: "challenge", text: (bodyText || document.title).slice(0, 300) };
    }
    // 2. login wall.
    if (LOGIN_PATH_RE.test(location.pathname) || /(^|\.)accounts\.google\.com$/.test(location.hostname)) return { state: "logged_out", text: "redirected to " + location.pathname };
    if (anyVisible('[data-testid="login-button"], [data-testid="signup-button"], a[href*="accounts.google.com/ServiceLogin"], a[href*="accounts.google.com/signin"]')) return { state: "logged_out", text: "login button visible" };
    for (const b of q('button, a, [role="button"]')) {
      if (!isVisible(b)) continue;
      const t = norm(b.innerText || b.getAttribute("aria-label"));
      if (t && t.length < 40 && LOGIN_BTN_RE.test(t) && !b.closest(CONVERSATION_SEL)) return { state: "logged_out", text: `"${t}" button visible` };
    }
    // 3. message limit / quota banner. Short, visible, outside the conversation.
    const cands = q('[role="dialog"], [role="alertdialog"], [role="alert"], [role="status"], [aria-live], dialog[open], [class*="banner" i], [class*="toast" i], [class*="snackbar" i], [class*="notice" i], [class*="limit" i], [data-testid*="limit" i], [data-testid*="banner" i], [data-testid*="toast" i], p, span, div, h1, h2, h3, li, button, a')
      .filter((el) => el.children.length <= 4 && el.textContent.length <= 400 && isVisible(el) && !el.closest(CONVERSATION_SEL));
    // The whole banner but not the page around it: the longest matching text up to 220 chars (a bigger container
    // starts repeating the sidebar; a smaller one is a fragment of the banner).
    let best = null;
    for (const el of cands) {
      const t = norm(el.innerText);
      if (t.length >= 8 && t.length <= 220 && LIMIT_RE.test(t) && (!best || t.length > best.length)) best = t;
    }
    if (best) return { state: "rate_limited", text: best };
    return { state: "ok", text: "" };
  }

  // ---- the rendered answer -----------------------------------------------------------------------------
  // msgs: one element per assistant turn (the LAST is read); body: where its prose sits (default: the element);
  // stop: present while generating; done: present once the turn is complete (action bar, copy button...).
  const ANSWER = {
    // ChatGPT dropped data-message-author-role / data-testid in 2026-10 (the DIL renderer): the answer is one or more
    // MarkdownRoot blocks inside a turn container that says data-talvt-turn-state="complete" once it is done.
    chatgpt: { msgs: '[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"]', turn: '[data-talvt-turn-state], [data-message-author-role="assistant"]', body: null, stop: 'button[data-testid="stop-button"], button[aria-label*="Stop" i]', turnState: ["data-talvt-turn-state", "complete"], done: 'button[aria-label="Regenerate response"], button[aria-label="Copy"], button[data-testid="copy-turn-action-button"]' },
    gemini: { msgs: "model-response", body: "message-content, .markdown", stop: 'button[aria-label*="Stop" i]', done: 'button[aria-label*="Copy" i], message-actions, .response-footer' },
    grok: { msgs: '[id^="response-"]:not([id*="user"]), div.message-bubble', body: ".response-content-markdown, [class*='markdown']", stop: 'button[aria-label*="Stop" i]', done: 'button[aria-label*="Copy" i], button[aria-label*="Regenerate" i]' },
    claude: { msgs: "[data-is-streaming]", body: ".standard-markdown, .progressive-markdown", stop: 'button[aria-label*="Stop" i]', done: '[data-is-streaming="false"], button[data-testid="action-bar-retry"]' },
    deepseek: { msgs: ".ds-markdown", body: null, stop: 'div[role="button"][aria-label*="stop" i], button[aria-label*="stop" i]', done: ".ds-icon-button, .ds-markdown + div" },
    mistral: { msgs: '[data-message-author-role="assistant"], [data-testid*="assistant" i], [class*="assistant" i]', body: "[class*='markdown'], [class*='prose']", stop: 'button[aria-label*="Stop" i], button[aria-label*="Arrêter" i]', done: 'button[aria-label*="Copy" i], button[aria-label*="Copier" i]' },
  };

  function readAnswer(providerId) {
    const cfg = ANSWER[providerId];
    if (!cfg) return { text: "", len: 0, generating: false, finished: false, links: [] };
    const turns = q(cfg.msgs).filter((t) => !t.parentElement || !t.parentElement.closest(cfg.msgs));
    let last = turns[turns.length - 1];
    let generating = anyVisible(cfg.stop);
    if (!last) return { text: "", len: 0, generating, finished: false, links: [], turns: 0 };
    let text;
    if (cfg.turn) {   // an answer made of several blocks inside one turn container: read them all, in order
      const box = last.closest(cfg.turn) || last;
      if (cfg.turnState) { const st = box.getAttribute(cfg.turnState[0]); if (st && st !== cfg.turnState[1]) generating = true; }
      text = q(cfg.msgs, box).filter((t) => !t.parentElement.closest(cfg.msgs)).map((t) => (t.innerText || "").trim()).filter(Boolean).join("\n\n");
      last = box;
    } else {
      const body = (cfg.body && q(cfg.body, last).filter((b) => b.innerText).sort((a, b) => b.innerText.length - a.innerText.length)[0]) || last;
      text = (body.innerText || "").trim();
    }
    const own = location.hostname.replace(/^www\./, "");
    const links = [];
    const seen = new Set();
    for (const a of q('a[href^="http"]', last)) {
      let u; try { u = new URL(a.href); } catch (_) { continue; }
      if (u.hostname.replace(/^www\./, "").endsWith(own) || seen.has(a.href)) continue;
      seen.add(a.href);
      links.push({ url: a.href, title: norm(a.innerText || a.getAttribute("aria-label") || a.title).slice(0, 200) || null });
    }
    const marker = !cfg.done || last.matches(cfg.done) || q(cfg.done, last).some(isVisible) || (turns.length <= 1 && q(cfg.done).some(isVisible));
    return { text, len: text.length, generating, finished: !generating && text.length > 0 && marker, marker, links, turns: turns.length };
  }

  Probe.pageState = { pageStatus, readAnswer, LIMIT_RE };
})();
