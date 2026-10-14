// Generic modal / popup handler, the same on every provider page (docs/popups.md).
// scan(): every visible overlay that may sit in the way (role=dialog, aria-modal, <dialog open>, cookie banners of the
// usual consent platforms, a fixed layer covering the composer, toasts with a button), each classified by its text and
// buttons. handle(): dismisses only what is safe to dismiss, with a closed list of buttons; anything else is left alone
// and, when it blocks the page, returned as `blocking` so the runner pauses the provider (status popup_unknown).
// Never clicks upgrade / buy / subscribe / payment / delete / sign out / share, nor a link. Pure DOM: no extension API,
// so test/popups/ runs it on a plain page.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
  const q = (sel, root = document) => { try { return [...root.querySelectorAll(sel)]; } catch (_) { return []; } };
  const isVisible = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none" && Number(cs.opacity) > 0.05;
  };

  const DIALOG_SEL = '[role="dialog"], [role="alertdialog"], [aria-modal="true"], dialog[open]';
  // Consent platforms that do not use role=dialog (OneTrust, Didomi, Cookiebot, Google Funding Choices, Usercentrics, Quantcast...).
  const CMP_SEL = '#onetrust-banner-sdk, #onetrust-pc-sdk, #didomi-notice, .didomi-popup-container, #CybotCookiebotDialog, .fc-consent-root, .fc-dialog-container, #usercentrics-root, .qc-cmp2-container, #truste-consent-track, [id*="cookie-banner" i], [class*="cookie-banner" i], [id*="cookie-consent" i], [class*="cookie-consent" i], [id*="cookieconsent" i], [class*="cookieconsent" i]';
  const TOAST_SEL = '[data-sonner-toast], [class*="toast" i], [class*="snackbar" i], [role="status"]';
  // Consent platforms' own reject buttons, tried before any text.
  const REJECT_SEL = '#onetrust-reject-all-handler, #didomi-notice-disagree-button, .didomi-continue-without-agreeing, #CybotCookiebotDialogBodyButtonDecline, .fc-cta-do-not-consent, [data-testid="uc-deny-all-button"]';

  // ---- what a button must never be -----------------------------------------------------------------------------
  const NEVER_RE = /upgrade|\bbuy\b|purchase|achet|subscri|abonn|payment|paiement|\bpay(er)?\b|checkout|billing|factur|pricing|tarif|delete|supprim|effacer|sign ?out|log ?out|d[ée]connex|d[ée]connecter|\bshare\b|partag|\btrial\b|essai|premium|\bplans?\b|unlock|d[ée]bloqu|(try|get|go|start|passer [àa]|passez [àa])\s+(chatgpt\s+|claude\s+|gemini\s+)?(plus|pro|max|team|business|advanced|ultra|supergrok)\b|supergrok|install|t[ée]l[ée]charg|download/i;
  // A link leaves the page (or opens one): never clicked, whatever it says.
  function forbidden(b) {
    const lab = label(b) + " " + (b.getAttribute("data-testid") || "") + " " + (b.getAttribute("title") || "");
    if (NEVER_RE.test(lab)) return "never-click word";
    const a = b.closest("a[href]");
    if (a) {
      const h = a.getAttribute("href") || "";
      if (!/^(#|javascript:)/i.test(h)) return "link";
    }
    if (b.getAttribute("target") === "_blank") return "opens a window";
    const form = b.closest("form[action]");
    if (form) { try { if (new URL(form.action, location.href).origin !== location.origin) return "submits off site"; } catch (_) {} }
    return null;
  }

  // ---- safe buttons --------------------------------------------------------------------------------------------
  const CLOSE_RE = /^(close|fermer|dismiss|ignorer|[×✕✖xX]|close (dialog|modal|banner|popup|this|notification|announcement)|fermer (la fen[êe]tre|la bo[îi]te de dialogue|le bandeau|la notification))$/i;
  const LATER_RE = /^(not now|pas maintenant|plus tard|later|maybe later|peut-[êe]tre plus tard|remind me later|me le rappeler plus tard|no,? thanks|non,? merci|skip|skip (tour|for now|intro)|passer|dismiss|ignorer|got it|compris|j'ai compris|ok|okay|d'accord|done|termin[ée]|close|fermer)$/i;
  const CONTINUE_RE = /^(continue|continuer)$/i;
  const REJECT_RE = /^(tout refuser|refuser tout|refuser|reject all|reject|reject (all )?(cookies|optional( cookies)?|non-essential( cookies)?)|refuse all|decline|decline all|deny|deny all|refuser les cookies( non essentiels| optionnels)?|continuer sans accepter|use (only )?(necessary|essential) cookies( only)?|only (necessary|essential)( cookies)?|(strictly )?necessary (cookies )?only|cookies? (strictement )?n[ée]cessaires? uniquement|n[ée]cessaires? uniquement)$/i;
  const NECESSARY_RE = /^(accept(er)?|autoriser|allow) (only )?(les )?(cookies )?(strictly |strictement )?(necessary|essential|n[ée]cessaires?|essentiels?)( cookies)?( only| uniquement)?$/i;
  const TERMS_ACCEPT_RE = /^(accept|i accept|j'accepte|accepter|agree|i agree|accept and continue|accepter et continuer|continue|continuer|ok|got it|compris)$/i;

  // ---- classes -------------------------------------------------------------------------------------------------
  const LOGIN_BTN_RE = /^(log ?in|sign ?in|sign up|log in or sign up|se connecter|connexion|s['’]inscrire|continue with (google|apple|email|sso)|continuer avec (google|apple|un e-mail))$/i;
  const CLASSES = [
    ["challenge", /captcha|verify (that )?you are (a )?human|v[ée]rifiez que vous [êe]tes (un )?humain|security (check|verification)/i],
    ["limit", null],   // Probe.pageState.LIMIT_RE (one source of truth for limit wording)
    ["login", /(log|sign) ?in to (continue|keep|save|use)|session (has )?expired|session expir[ée]e|connectez-vous|reconnectez-vous|please (log|sign) in/i],
    ["cookie", /cookie|traceurs|\bconsent|consentement|gdpr|rgpd|partenaires (publicitaires|traitent)|vendors/i],
    ["terms", /terms (of (use|service)|and conditions)|consumer terms|usage policy|conditions (g[ée]n[ée]rales|d'utilisation)|privacy (policy|notice)|politique de (confidentialit[ée]|protection)|we'?re updating our|nous mettons [àa] jour/i],
    ["upsell", /upgrade|passez [àa]|passer [àa] (plus|pro)|subscribe|abonnez|premium|supergrok|(chatgpt|claude|gemini) (plus|pro|max|advanced|ultra)\b|free trial|essai gratuit|unlock|d[ée]bloquez|more (usage|messages) with|higher limits/i],
    ["survey", /how (was|would you rate|satisfied|likely)|rate (your|this|the) (experience|answer|response|conversation)|(give|share|leave) (us )?(your )?feedback|\bfeedback\b|survey|sondage|questionnaire|votre avis|donnez-nous votre avis|satisfait|recommand/i],
    ["onboarding", /welcome to|bienvenue (sur|dans|à)|get started|let'?s (get started|begin)|take a (quick )?tour|visite guid[ée]e|step \d+ (of|sur|\/) ?\d+|[ée]tape \d+|here'?s how|voici comment|getting started|tips? (for|to)|astuces?/i],
    ["model_picker", /choose (a|your) (model|mode)|select (a|your) (model|mode)|choisi(r|ssez) (un|le|votre) (mod[èe]le|mode)|which model|quel mod[èe]le|default model|mod[èe]le par d[ée]faut/i],
    ["announcement", /what'?s new|quoi de neuf|\bnew\b|nouveau|nouvelle|nouveaut[ée]|introducing|d[ée]couvrez|now (available|live)|d[ée]sormais|we'?ve (added|launched|released|updated|improved|made)|announc|try (the|our) new|essayez|update|mise [àa] jour/i],
  ];
  const STATUS_CLASSES = new Set(["challenge", "limit", "login"]);   // pageStatus pauses with rate_limited / logged_out / challenge

  const label = (b) => norm(b.innerText || b.value || b.getAttribute("aria-label") || b.getAttribute("title") || "");
  const buttonsOf = (el) => q('button, [role="button"], a, input[type="button"], input[type="submit"], .didomi-continue-without-agreeing', el).filter(isVisible);

  function classify(el, text) {
    const btns = buttonsOf(el).map(label);
    const all = text + " | " + btns.join(" | ") + " | " + (el.getAttribute("aria-label") || "");
    if (el.matches(CMP_SEL) || el.closest(CMP_SEL)) return "cookie";
    if (q('iframe[src*="challenges.cloudflare.com"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]', el).length) return "challenge";
    for (const [cls, re] of CLASSES) {
      const r = cls === "limit" ? Probe.pageState && Probe.pageState.LIMIT_RE : re;
      if (r && r.test(cls === "limit" ? text : all)) return cls;
      if (cls === "login" && btns.some((t) => LOGIN_BTN_RE.test(t)) && text.length < 400) return "login";
    }
    return "unknown";
  }

  // ---- finding overlays ----------------------------------------------------------------------------------------
  function composerEl(sels) { for (const s of sels || []) { const el = q(s).find(isVisible); if (el) return el; } return null; }
  // The topmost thing at the composer's centre, if it is not the composer: the overlay that covers it.
  function coverAt(x, y, composer) {
    const hit = document.elementFromPoint(x, y);
    if (!hit || (composer && (composer.contains(hit) || hit.contains(composer)))) return null;
    for (let n = hit; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if ((cs.position === "fixed" || cs.position === "absolute") && (parseInt(cs.zIndex, 10) || 0) >= 10 && !(composer && n.contains(composer))) {
        let top = n;   // the outermost fixed layer that still does not hold the composer
        for (let p = n.parentElement; p && p !== document.body; p = p.parentElement) {
          if (composer && p.contains(composer)) break;
          if (getComputedStyle(p).position === "fixed") top = p;
        }
        return top;
      }
    }
    return null;
  }
  function blocks(el, composer) {
    if (el.matches('[aria-modal="true"], [role="alertdialog"]')) return true;
    try { if (el.matches("dialog:modal")) return true; } catch (_) {}
    const r = el.getBoundingClientRect();
    if (r.width * r.height >= 0.4 * innerWidth * innerHeight) return true;
    if (composer) {
      const c = composer.getBoundingClientRect();
      const x = c.left + c.width / 2, y = c.top + c.height / 2;
      const hit = document.elementFromPoint(x, y);
      if (hit && el.contains(hit)) return true;
    }
    return false;
  }

  function scan({ composer: composerSels } = {}) {
    const composer = composerEl(composerSels);
    const found = new Map();
    const add = (el, kind) => {
      if (!el || found.has(el) || !isVisible(el)) return;
      if (composer && el.contains(composer)) return;   // the app shell, not an overlay
      const text = norm(el.innerText);
      if (!text && !buttonsOf(el).length) return;
      found.set(el, kind);
    };
    for (const el of q(DIALOG_SEL)) add(el, "dialog");
    for (const el of q(CMP_SEL)) add(el, "cookie_banner");
    for (const el of q(TOAST_SEL)) if (buttonsOf(el).length && norm(el.innerText).length <= 300) add(el, "toast");
    if (composer) {
      const c = composer.getBoundingClientRect();
      add(coverAt(c.left + c.width / 2, c.top + c.height / 2, composer), "overlay");
    }
    // Nested matches (a dialog inside a CMP container, a toast inside a dialog): keep the outermost.
    const els = [...found.keys()];
    const out = [];
    for (const el of els) {
      if (els.some((o) => o !== el && o.contains(el))) continue;
      const text = norm(el.innerText).slice(0, 1200);
      const cls = classify(el, text);
      out.push({ el, kind: found.get(el), cls, text, blocking: blocks(el, composer) });
    }
    return out;
  }

  // ---- acting --------------------------------------------------------------------------------------------------
  function realClick(el) {
    const o = { bubbles: true, cancelable: true, view: window, button: 0, buttons: 1 };
    try { el.dispatchEvent(new PointerEvent("pointerdown", o)); } catch (_) {}
    el.dispatchEvent(new MouseEvent("mousedown", o));
    try { el.dispatchEvent(new PointerEvent("pointerup", o)); } catch (_) {}
    el.dispatchEvent(new MouseEvent("mouseup", o));
    el.dispatchEvent(new MouseEvent("click", o));
  }
  function pressEscape(el) {
    const o = { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true, cancelable: true };
    const t = (document.activeElement && el.contains(document.activeElement)) ? document.activeElement : el;
    t.dispatchEvent(new KeyboardEvent("keydown", o));
    t.dispatchEvent(new KeyboardEvent("keyup", o));
  }
  const isCloseBtn = (b, box) => {
    const lab = label(b), aria = norm(b.getAttribute("aria-label") || b.getAttribute("title"));
    if (CLOSE_RE.test(lab) || CLOSE_RE.test(aria) || /^(close|fermer)\b/i.test(aria) || /close|dismiss/i.test(b.getAttribute("data-testid") || "")) return true;
    // An unlabelled icon button in the overlay's top-right corner: the usual ×.
    if (lab || aria || !box || !b.querySelector("svg")) return false;
    const r = b.getBoundingClientRect(), d = box.getBoundingClientRect();
    return r.width <= 64 && r.height <= 64 && d.right - r.right <= 64 && r.top - d.top <= 64;
  };
  // The button to press for this overlay, or null. Never one that forbidden() rejects.
  function chooseButton(o) {
    const btns = buttonsOf(o.el).filter((b) => !forbidden(b) && !b.disabled);
    const by = (test) => btns.find((b) => test(b));
    if (o.cls === "cookie") {
      return q(REJECT_SEL, o.el).find((b) => isVisible(b) && !forbidden(b)) || by((b) => REJECT_RE.test(label(b)))
        || by((b) => NECESSARY_RE.test(label(b))) || by((b) => isCloseBtn(b, o.el)) || null;
    }
    const close = by((b) => isCloseBtn(b, o.el)) || by((b) => /^(not now|pas maintenant|plus tard|later|maybe later|no,? thanks|non,? merci|skip|passer|dismiss|ignorer)$/i.test(label(b)));
    if (o.cls === "upsell" || o.cls === "model_picker") return close || by((b) => /^(got it|compris|j'ai compris)$/i.test(label(b))) || null;
    if (o.cls === "terms") return close || by((b) => TERMS_ACCEPT_RE.test(label(b))) || null;
    return close || by((b) => LATER_RE.test(label(b))) || by((b) => CONTINUE_RE.test(label(b))) || null;
  }
  // A terms update that also asks a question (a switch or a checkbox: « help improve the model », marketing...) is a
  // decision for a human, never accepted with whatever the default is.
  const hasChoice = (el) => q('[role="switch"], [role="checkbox"], input[type="checkbox"], input[type="radio"]', el).some(isVisible);

  const reported = new WeakMap();   // el -> the last action reported for it
  let onEvent = null;
  function report(o, action, stage, extra = {}) {
    const ev = { class: o.cls, kind: o.kind, text_snippet: o.text.slice(0, 200), action, stage, blocking: o.blocking, url: location.href, at: new Date().toISOString(), ...extra };
    if (reported.get(o.el) === action) return null;   // the same overlay left alone is reported once, not every 2.5 s
    reported.set(o.el, action);
    try { if (onEvent) onEvent(ev); } catch (_) {}
    return ev;
  }
  const gone = (el) => !el.isConnected || !isVisible(el);

  // One pass over the page. opts: {stage, composer: [selectors], escape: bool}. Returns {events, blocking}:
  // blocking = {class, text, reason} for an overlay that is in the way and was not (or could not be) dismissed.
  async function handle({ stage = "?", composer = null, escape = true, waitMs = 500 } = {}) {
    const events = [];
    let blocking = null;
    const push = (e) => { if (e) events.push(e); };
    for (let round = 0; round < 3; round++) {
      const ovs = scan({ composer });
      let acted = false;
      for (const o of ovs) {
        if (gone(o.el)) continue;
        if (STATUS_CLASSES.has(o.cls)) { push(report(o, "left_for_status", stage)); continue; }
        if (o.cls === "unknown" || (o.cls === "terms" && hasChoice(o.el))) {
          const why = o.cls === "unknown" ? "unknown dialog" : "terms update with a choice to make";
          if (o.blocking) { push(report(o, "paused", stage, { reason: why })); blocking = blocking || { class: o.cls, text: o.text.slice(0, 300), reason: why }; }
          else push(report(o, "ignored", stage, { reason: why + ", not blocking" }));
          continue;
        }
        if (escape && o.kind !== "toast" && o.cls !== "cookie" && o.cls !== "terms") {
          pressEscape(o.el);
          await sleep(waitMs);
          if (gone(o.el)) { push(report(o, "escape", stage)); acted = true; continue; }
        }
        const b = chooseButton(o);
        if (b) {
          const lab = label(b) || norm(b.getAttribute("aria-label")) || "(icon)";
          realClick(b);
          await sleep(waitMs);
          const ok = gone(o.el);
          const extra = o.cls === "terms" && TERMS_ACCEPT_RE.test(lab) && !CLOSE_RE.test(lab) ? { prominent: true, note: "TERMS ACCEPTED" } : {};
          push(report(o, `clicked "${lab}"` + (ok ? "" : " (still shown)"), stage, extra));
          acted = true;
          if (ok) continue;
        }
        if (o.blocking) {
          const why = b ? "still shown after the safe button" : "no safe button";
          push(report(o, "stuck", stage, { reason: why }));
          blocking = blocking || { class: o.cls, text: o.text.slice(0, 300), reason: why };
        } else push(report(o, "ignored", stage, { reason: "no safe button, not blocking" }));
      }
      if (!acted) break;
      blocking = null;   // the page changed: judge it again on the next round
    }
    return { events, blocking };
  }

  // Synchronous, one click at most, no Escape: what the drivers' startChat used to do with dismissConsent/dismissNotice.
  function sweep({ stage = "start_chat", composer = null } = {}) {
    for (const o of scan({ composer })) {
      if (STATUS_CLASSES.has(o.cls) || o.cls === "unknown" || o.cls === "terms") continue;
      const b = chooseButton(o);
      if (b) { realClick(b); report(o, `clicked "${label(b) || "(icon)"}"`, stage); return true; }
    }
    return false;
  }

  Probe.popups = { scan, handle, sweep, classify, chooseButton, forbidden, NEVER_RE, setOnEvent: (f) => { onEvent = f; } };
})();
