# Popups and modals

A chatbot page sometimes puts a window over the composer: a cookie banner, « what's new », a terms update, an upgrade
offer, a survey, a tour. Until 14 October 2026 only a few cookie and « Not now » buttons were clicked, at the start of a
chat; anything else sat there until someone clicked it by hand. Code: `ff/src/content/popups.js` (content script, every
provider page), `ff/src/background/runner.js` (when it runs, what happens next), `churvey/probe.py` (`popups` check).

## When it runs

| stage | when | Escape | an overlay that cannot be dismissed |
|---|---|---|---|
| `start_chat` | the drivers' `startChat` (was `dismissConsent` / `dismissNotice`) | no | left alone |
| `pre_submit` | after the page is ready and `pageStatus` is ok, before the question is typed | yes | **provider paused**, `popup_unknown` |
| `waiting` | every 2.5 s while an answer is awaited (`guardWatch`) | no (some pages read Escape as « stop ») | left alone: the answer may still land |
| `stall` | the submit failed, or no stream started `popupStallMs` (default 30 s) after the submit | yes | **provider paused**, `popup_unknown` |
| `probe_*` | `churvey probe`, on its home page, new chat and temporary chat | yes | reported (FAIL) |

**Stall rule.** If the submit failed, or nothing has started streaming after 30 s, the handler runs; if it dismissed
something during this item (at any stage), the item is asked again **once**, in a new chat, without counting a failure.
A second stall takes the normal path (timeout, backoff, `MAX_ATTEMPTS`).

## What is an overlay

Visible elements, outermost only, never the app shell (a box that holds the composer):

* `[role=dialog]`, `[role=alertdialog]`, `[aria-modal=true]`, `<dialog open>`;
* consent platforms that use no dialog role: OneTrust, Didomi, Cookiebot, Google Funding Choices, Usercentrics,
  Quantcast, TrustArc, and `*cookie-banner*` / `*cookie-consent*` ids and classes;
* toasts with a button (`[data-sonner-toast]`, `*toast*`, `*snackbar*`, `[role=status]`);
* whatever fixed or absolute layer (z-index ≥ 10) sits on top of the composer's centre.

It **blocks** when it is modal (`aria-modal`, `alertdialog`, `dialog:modal`), covers 40 % of the window, or covers the
composer's centre.

## Classes and actions

Classified by the overlay's text, its buttons and its aria-label (EN + FR), first match wins:

| class | recognised by (examples) | action |
|---|---|---|
| `challenge` | captcha iframe, « verify you are human » | none: `pageStatus` pauses with `challenge` |
| `limit` | `page-state.js LIMIT_RE` (« reached your message limit ») | none: `rate_limited` |
| `login` | « log in to continue », a Log in / Sign up button in a short dialog | none: `logged_out` |
| `cookie` | consent-platform container, « cookies », « traceurs », « consent » | the platform's reject button, else « Tout refuser » / « Refuser » / « Reject all » / « Continuer sans accepter » / « Only necessary », else « Accepter (seulement) les nécessaires », else ×. **Never « Accept all »**: a banner that only offers it blocks → paused |
| `terms` | « Terms of Service », « Consumer Terms », « politique de confidentialité », « we're updating our » | × / « Plus tard » first, else « Accept » / « J'accepte » / « Continuer », logged as `prominent: true`, `TERMS ACCEPTED` in the log and the launcher output. **A terms dialog with a switch, checkbox or radio is never accepted** (it asks a question, e.g. « help improve Claude », and the default may be yes): paused |
| `upsell` | « Upgrade », « Passez à », « Subscribe », « ChatGPT Plus », « SuperGrok », « free trial » | × / « Not now » / « Plus tard » / « No thanks » / « Skip » / « Got it » only (no « Continue ») |
| `survey` | « how would you rate », « feedback », « votre avis », « sondage » | Escape, then × / « Plus tard » / « Not now » / « Skip » / « Dismiss » |
| `onboarding` | « Welcome to », « Step 1 of 3 », « get started », « visite guidée » | same as survey (« Skip », « Passer »...) |
| `model_picker` | « choose your model », « choisir un modèle » | Escape, then × / « Not now » / « Got it » only (never picks a model) |
| `announcement` | « What's new », « Introducing », « Nouveau », « désormais disponible », « update » | Escape, then × / « Not now » / « Plus tard » / « Dismiss » / « Got it » / « Compris » / « OK », then « Continuer » |
| `unknown` | anything else | **not clicked, no Escape**. Blocking → provider paused with `popup_unknown`, its text and a screenshot. Not blocking (a popover, a toast) → logged once as `ignored` |

The × is a button labelled (text, aria-label, title or test id) close / fermer / dismiss / × / ✕, or an unlabelled icon
button within 64 px of the overlay's top-right corner. Escape is sent to the overlay (or its focused element) and counts
only if the overlay is gone 0.5 s later; it is not used for cookie banners, terms, toasts or unknown overlays.

## Never clicked

Whatever the class, a button is never pressed when (`popups.js forbidden`):

* its text, aria-label, title or test id contains: upgrade, buy, purchase, achet-, subscri-, abonn-, payment, paiement,
  pay / payer, checkout, billing, factur-, pricing, tarif, delete, supprim-, effacer, sign out, log out, déconnexion,
  déconnecter, share, partag-, trial, essai, premium, plan(s), unlock, débloqu-, install, télécharg-, download, or
  try / get / go / start / passer à + Plus / Pro / Max / Team / Business / Advanced / Ultra / SuperGrok;
* it is (inside) a link with a real `href` (anything but `#` / `javascript:`), so no link is ever followed, on or off site;
* it has `target=_blank`, or submits a form to another origin.

The buttons pressed come from closed lists (above); there is no « click the first button » fallback.

## What is recorded

* Each event: `{class, kind (dialog | cookie_banner | toast | overlay), text_snippet (200 chars), action, stage, blocking,
  url, at}` plus `reason` (paused / stuck / ignored) and `prominent` + `note` for an accepted terms update. Actions:
  `clicked "<label>"` (` (still shown)` if it stayed), `escape`, `left_for_status`, `ignored`, `paused`, `stuck`.
* **Record** (schema v8): `popups: [{class, text_snippet, action, stage}]`, everything seen while the item was asked.
* **Run**: `manifest.popups` (every event, with provider and item) → the launcher writes `popups.jsonl` in the run folder,
  and `popup_<provider>_<n>.jpg` for the screenshot of a paused provider (`provider_paused` row).
* **Live**: the launcher prints `HH:MM:SS <provider> POPUP <class> <action> « text »` (with `*** TERMS ACCEPTED ***`),
  and the usual `HEALTH popup_unknown ...` line when a provider is paused. `ffctl status` shows `[POPUP_UNKNOWN: ...]`;
  `churvey run` explains it (« showed a window churvey does not know how to close ») with what to do. The extension log
  ring has one `popup ...` line per event (driver and runner).
* After closing it by hand: `ffctl resume <provider>`, or rerun with `--chatbots <provider>`.

## Probe

`churvey probe` runs the handler on each page it opens (`probe_home`, `probe_new_chat`, `probe_temporary`) and reads the
records' `popups` from its three messages. Check `popups`: PASS when nothing was seen or everything was handled (the
detail lists them), FAIL when an overlay was left in the way or the provider was paused `popup_unknown`. Its fingerprint
is the set of `class: action` seen (`none` when nothing was), so a popup that appears, disappears or is handled
differently from last month turns the check CHANGED.

## Adding a popup

A new popup shows in `popups.jsonl` as `unknown` / `paused` with its text and a screenshot. Add its wording to the class
regex in `popups.js CLASSES` (or its button to the class's list in `chooseButton`), then a case to `test/popups/cases.js`.

## Tests

`tests/test_popups_js.py` opens `test/popups/harness.html` in a headless Firefox on a throwaway profile (no extension,
no provider page) and runs every fixture of `test/popups/cases.js` through `scan` + `handle`: the class, the button
clicked, the buttons that must not be, blocking, and the action. `harness.html` also works opened by hand in a browser.

## Measured (14 October 2026)

Fixtures (`tests/test_popups_js.py`, Firefox 157 headless): 24 cases, all pass. They include a fake « Upgrade to Pro » with
only Upgrade / Subscribe (not clicked, `stuck`, blocks), a Claude-style terms update with a « help improve Claude » switch
(not accepted, `paused`), an unknown modal (`paused`), a « Share this chat » dialog (`paused`), and a cookie banner with
only « Accept all » (not clicked, `stuck`). The never-click guard rejects Sign out, Delete all chats, Buy credits,
Partager, a link labelled Close, Passer à Plus, Se déconnecter and Start free trial, and lets Plus tard and Fermer through.
The same harness also checks that every extension script parses.

Live, `churvey probe` headless on a fresh profile signed in to nothing (no message sent):

| chatbot | seen | action |
|---|---|---|
| ChatGPT | cookie dialog « We use cookies ... Reject non-essential / Accept all » (home, new chat) | first run: `ignored` (the wording « Reject non-essential » was not in the list; fixed); second run: clicked « Reject non-essential ». The probe reported `popups` CHANGED (`cookie: ignored -> cookie: clicked "Reject non-essential"`) |
| Gemini | full-page « Before you continue to Google ... cookies » (`overlay` over the composer) | clicked « Reject all » |
| Grok | cookie dialog « Essential cookies keep the site working ... accept, reject, or manage » | clicked « Reject All » |
| Claude | nothing (signed out: /login) | - |
| Le Chat | not observed: the page goes to the sign-in host (v2.auth.mistral.ai), outside the content script | - |

Not yet exercised live: the runner's `pre_submit` / `waiting` / `stall` passes and the `popup_unknown` pause during a real
run (they need a signed-in account and a popup that shows up during a run). Their code paths parse and use the same
`handle()` as the probe.
