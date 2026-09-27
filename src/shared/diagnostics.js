// On-demand page diagnostics. Captures which selectors matched (and their HTML),
// any open dialogs/modals, and visible buttons — enough to fix selector drift or
// identify a blocking dialog without the operator hand-extracting DOM.
(() => {
  const Probe = (globalThis.Probe ||= {});

  function matchInfo(selectors) {
    for (const sel of selectors || []) {
      const nodes = document.querySelectorAll(sel);
      if (nodes.length) {
        const el = nodes[nodes.length - 1];
        return { matched: sel, count: nodes.length, outerHTML: clip(el.outerHTML, 700) };
      }
    }
    return { matched: null, count: 0, tried: selectors || [] };
  }

  function clip(s, n) {
    s = s || "";
    return s.length > n ? s.slice(0, n) + "…[+" + (s.length - n) + "]" : s;
  }

  function dialogs() {
    const sels = ['[role="dialog"]', '[aria-modal="true"]', "dialog[open]", ".modal"];
    const out = [];
    const seen = new Set();
    for (const s of sels) {
      document.querySelectorAll(s).forEach((d) => {
        if (seen.has(d)) return;
        seen.add(d);
        out.push({
          via: s,
          text: clip(d.innerText || "", 500),
          buttons: Array.from(d.querySelectorAll("button")).map((b) => ({
            text: clip(b.innerText || "", 60),
            aria: b.getAttribute("aria-label"),
            testid: b.getAttribute("data-testid"),
          })),
          outerHTML: clip(d.outerHTML, 2500),
        });
      });
    }
    return out;
  }

  function visibleButtons() {
    // Include role="button" divs — some apps (e.g. DeepSeek) use no <button>.
    return Array.from(document.querySelectorAll('button, [role="button"]'))
      .filter((b) => b.offsetParent !== null)
      .slice(0, 60)
      .map((b) => ({
        tag: b.tagName.toLowerCase(),
        text: clip(b.innerText || "", 50),
        aria: b.getAttribute("aria-label"),
        testid: b.getAttribute("data-testid"),
        cls: clip(b.className || "", 80),
      }));
  }

  function capture(adapter) {
    const selectors = (adapter && adapter.SELECTORS) || {};
    const selOut = {};
    for (const k of Object.keys(selectors)) selOut[k] = matchInfo(selectors[k]);
    let ready = null;
    try {
      ready = adapter ? adapter.isReady() : null;
    } catch (e) {
      ready = "error: " + e.message;
    }
    return {
      url: location.href,
      title: document.title,
      ts: new Date().toISOString(),
      provider: adapter ? adapter.id : null,
      ready,
      selectors: selOut,
      dialogs: dialogs(),
      visibleButtons: visibleButtons(),
    };
  }

  Probe.diag = { capture, matchInfo, dialogs };
})();
