// React-aware input injection (ported). Verifies via read-back.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("injector");

  const isField = (el) => el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && /text|search/i.test(el.type));
  const readBack = (el) => (isField(el) ? el.value : el.innerText) || "";
  const norm = (s) => s.replace(/\s+/g, " ").trim();

  function focusEnd(el) {
    el.focus();
    if (isField(el)) { try { el.setSelectionRange(el.value.length, el.value.length); } catch (_) {} return; }
    const sel = window.getSelection(); const r = document.createRange();
    r.selectNodeContents(el); r.collapse(false); sel.removeAllRanges(); sel.addRange(r);
  }
  function setNative(el, v) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const d = Object.getOwnPropertyDescriptor(proto, "value");
    if (d && d.set) d.set.call(el, v); else el.value = v;
  }
  function clear(el) {
    if (isField(el)) { setNative(el, ""); el.dispatchEvent(new Event("input", { bubbles: true })); return; }
    el.focus(); document.execCommand("selectAll", false, null); document.execCommand("delete", false, null);
  }

  const STRATEGIES = [
    ["nativeSetter", (el, t) => { if (!isField(el)) return false; focusEnd(el); setNative(el, t); el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); return true; }],
    ["execCommand", (el, t) => { focusEnd(el); return document.execCommand("insertText", false, t); }],
    ["inputEvent", (el, t) => { focusEnd(el); el.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, cancelable: true, inputType: "insertText", data: t })); el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: t })); return true; }],
    ["paste", (el, t) => { focusEnd(el); const dt = new DataTransfer(); dt.setData("text/plain", t); el.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt })); return true; }],
  ];

  async function type(el, text, { retries = 1 } = {}) {
    const want = norm(text);
    for (let a = 0; a <= retries; a++) {
      for (const [name, fn] of STRATEGIES) {
        try {
          clear(el); fn(el, text);
          await Probe.cadence.sleep(80);
          const got = norm(readBack(el));
          if (got === want || (got.includes(want) && got.length <= want.length + 4)) { log.info(`typed via ${name}`); return name; }
        } catch (e) { log.warn(`strategy ${name} threw`, e?.message || e); }
      }
      await Probe.cadence.sleep(150);
    }
    throw new Error(`injector: could not verify typed text (got "${norm(readBack(el)).slice(0, 60)}")`);
  }

  Probe.injector = { type, readBack, clear, isField };
})();
