// Fixture dialogs for content/popups.js. Each case: the HTML put on the page and what the handler must do.
// expect: class, clicked (button id, or null = nothing clicked), never (ids that must not be clicked), blocking (bool),
// action (a prefix of the event's action). Every button records its id in window.__clicks; data-close removes the fixture.
window.CASES = [
  { name: "cookie_onetrust", expect: { class: "cookie", clicked: "reject", never: ["accept"] },
    html: `<div id="onetrust-banner-sdk" style="position:fixed;bottom:0;left:0;right:0;height:120px;background:#eee;z-index:999">
      We use cookies to improve your experience. <button id="accept" data-close>Accept All Cookies</button>
      <button id="onetrust-reject-all-handler" data-id="reject" data-close>Reject All</button></div>` },
  { name: "cookie_didomi_fr", expect: { class: "cookie", clicked: "cont", never: ["agree"] },
    html: `<div id="didomi-notice" style="position:fixed;bottom:0;left:0;right:0;background:#eee;z-index:999">
      Nous et nos partenaires utilisons des cookies et des traceurs. <button id="agree" data-close>Accepter &amp; Fermer</button>
      <span class="didomi-continue-without-agreeing" data-id="cont" data-close role="button">Continuer sans accepter</span></div>` },
  { name: "cookie_google_fr", expect: { class: "cookie", clicked: "refuse", never: ["all", "more"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:10%;background:#fff;z-index:999">
      Avant d'accéder à Google. Nous utilisons des cookies et des données pour fournir nos services.
      <button id="all" data-close>Tout accepter</button><button id="refuse" data-close>Tout refuser</button>
      <a id="more" href="https://consent.google.com/more">Plus d'options</a></div>` },
  { name: "cookie_chatgpt_2026_10", expect: { class: "cookie", clicked: "rej", never: ["all", "learn"] },
    html: `<div role="dialog" style="position:fixed;bottom:16px;left:16px;width:380px;background:#fff;z-index:999">
      We use cookies Cookies help this site function, measure usage, and support marketing. Manage your cookie preferences anytime.
      <a id="learn" href="https://openai.com/policies/cookie-policy">Learn more about our cookie policy.</a>
      <button id="rej" data-close>Reject non-essential</button><button id="all" data-close>Accept all</button></div>` },
  { name: "cookie_accept_all_only", expect: { class: "cookie", clicked: null, never: ["all"], blocking: true, action: "stuck" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:20%;background:#fff;z-index:999">
      This site uses cookies. <button id="all" data-close>Accept all</button></div>` },
  { name: "cookie_necessary_only", expect: { class: "cookie", clicked: "nec", never: ["all"], blocking: false },
    html: `<div class="cookie-banner" style="position:fixed;bottom:0;left:0;width:300px;background:#eee;z-index:999">
      Cookies help us. <button id="all" data-close>Accept all</button><button id="nec" data-close>Accept only necessary cookies</button></div>` },
  { name: "whats_new_got_it", expect: { class: "announcement", clicked: "ok", never: ["try"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      <h2>What's new</h2>Introducing Projects: keep your chats organised.
      <a id="try" href="/projects">Try it now</a><button id="ok" data-close>Got it</button></div>` },
  { name: "announcement_escape", expect: { class: "announcement", clicked: null, never: ["learn"], blocking: true, action: "escape" },
    html: `<div role="dialog" aria-modal="true" data-escape style="position:fixed;inset:15%;background:#fff;z-index:999">
      Now available: voice mode in French. <a id="learn" href="https://example.com/voice">Learn more</a></div>` },
  { name: "terms_accept", expect: { class: "terms", clicked: "acc", never: [], blocking: true, prominent: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      We've updated our Terms of Service and Privacy Policy. <a id="read" href="https://example.com/terms">Read them</a>
      <button id="acc" data-close>Accept</button></div>` },
  { name: "terms_with_switch", expect: { class: "terms", clicked: null, never: ["acc", "sw"], blocking: true, action: "paused" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Updates to Consumer Terms and Privacy Policy. You can help improve Claude.
      <button id="sw" role="switch" aria-checked="true" aria-label="Help improve Claude"></button>
      <button id="acc" data-close>Accept</button></div>` },
  { name: "upsell_upgrade_only", expect: { class: "upsell", clicked: null, never: ["up", "sub"], blocking: true, action: "stuck" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Upgrade to Pro. Unlock priority access and new features.
      <button id="up" data-close>Upgrade to Pro</button><button id="sub" data-close>Subscribe now</button></div>` },
  { name: "upsell_not_now", expect: { class: "upsell", clicked: "later", never: ["up"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Upgrade to Claude Pro for higher limits. <button id="up" data-close>Upgrade</button><button id="later" data-close>Not now</button></div>` },
  { name: "survey_fr", expect: { class: "survey", clicked: "later", never: ["send"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Comment évaluez-vous cette réponse ? Donnez-nous votre avis.
      <button id="send" data-close>Envoyer</button><button id="later" data-close>Plus tard</button></div>` },
  { name: "onboarding_skip", expect: { class: "onboarding", clicked: "skip", never: ["next"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Welcome to Grok. Step 1 of 3. <button id="next">Next</button><button id="skip" data-close>Skip</button></div>` },
  { name: "model_picker_close", expect: { class: "model_picker", clicked: "x", never: ["fast", "exp"], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Choose your model. <button id="fast" data-close>Fast</button><button id="exp" data-close>Expert</button>
      <button id="x" aria-label="Close" data-close><svg width="10" height="10"></svg></button></div>` },
  { name: "icon_close", expect: { class: "announcement", clicked: "x", never: [], blocking: true },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;top:100px;left:100px;width:500px;height:300px;background:#fff;z-index:999">
      Introducing voice mode.
      <button id="x" data-close style="position:absolute;top:8px;right:8px;width:24px;height:24px"><svg width="12" height="12"><path d="M0 0L12 12"/></svg></button></div>` },
  { name: "unknown_modal", expect: { class: "unknown", clicked: null, never: ["reload", "cancel"], blocking: true, action: "paused" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Quelque chose s'est mal passé dans votre espace de travail. <button id="cancel">Annuler</button><button id="reload">Recharger</button></div>` },
  { name: "unknown_popover_not_blocking", expect: { class: "unknown", clicked: null, never: ["b"], blocking: false, action: "ignored" },
    html: `<div role="dialog" style="position:absolute;top:10px;left:10px;width:180px;height:60px;background:#fff">
      Renommer le fil <button id="b">Valider</button></div>` },
  { name: "share_dialog", expect: { class: "unknown", clicked: null, never: ["share", "copy"], blocking: true, action: "paused" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Share this chat. Anyone with the link can view it. <button id="share">Share link</button><button id="copy">Copy link</button></div>` },
  { name: "limit_dialog", expect: { class: "limit", clicked: null, never: ["up"], blocking: true, action: "left_for_status" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      You've reached your message limit. Upgrade to Pro to continue. <button id="up">Upgrade</button></div>` },
  { name: "login_dialog", expect: { class: "login", clicked: null, never: ["in", "up"], blocking: true, action: "left_for_status" },
    html: `<div role="dialog" aria-modal="true" style="position:fixed;inset:15%;background:#fff;z-index:999">
      Log in to continue your chat. <button id="in">Log in</button><button id="up">Sign up</button></div>` },
  { name: "toast_dismiss", expect: { class: "unknown", clicked: null, never: ["d"], blocking: false, action: "ignored" },
    html: `<div class="toast" style="position:fixed;top:10px;right:10px;width:200px;background:#eee;z-index:999">
      Copied to clipboard <button id="d" data-close>Undo</button></div>` },
  { name: "toast_announcement", expect: { class: "announcement", clicked: "ok", never: [], blocking: false },
    html: `<div data-sonner-toast style="position:fixed;top:10px;right:10px;width:220px;background:#eee;z-index:999">
      New: memory is now available. <button id="ok" data-close>Dismiss</button></div>` },
  { name: "fixed_overlay_over_composer", expect: { class: "announcement", kind: "overlay", clicked: "ok", never: [], blocking: true },
    html: `<div style="position:fixed;left:0;right:0;bottom:0;height:160px;background:#ffd;z-index:50">
      Nouveau : la recherche approfondie est désormais disponible. <button id="ok" data-close>Compris</button></div>` },
];
