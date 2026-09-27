// React-aware input simulation. Direct textContent/value writes do NOT update
// React/ProseMirror/Lexical/Quill state, so we go through real input events and
// always read the DOM back to verify before allowing a submit.
(() => {
  const Probe = (globalThis.Probe ||= {});
  const log = Probe.log.make("injector");

  function isTextField(el) {
    const tag = el.tagName;
    return tag === "TEXTAREA" || (tag === "INPUT" && /text|search/i.test(el.type));
  }

  function focusEnd(el) {
    el.focus();
    if (isTextField(el)) {
      const len = el.value.length;
      try {
        el.setSelectionRange(len, len);
      } catch (_) {}
      return;
    }
    // contenteditable: collapse selection to end
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function readBack(el) {
    return (isTextField(el) ? el.value : el.innerText) || "";
  }

  // Normalize whitespace for verification; editors may collapse newlines/spaces.
  function norm(s) {
    return s.replace(/\s+/g, " ").trim();
  }

  function clear(el) {
    if (isTextField(el)) {
      setNativeValue(el, "");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    el.focus();
    document.execCommand("selectAll", false, null);
    document.execCommand("delete", false, null);
  }

  function setNativeValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
  }

  // --- strategies, tried in order ---

  function viaNativeSetter(el, text) {
    if (!isTextField(el)) return false;
    focusEnd(el);
    setNativeValue(el, text);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function viaExecCommand(el, text) {
    focusEnd(el);
    // insertText triggers the same path as real typing for most rich editors.
    return document.execCommand("insertText", false, text);
  }

  function viaInputEvent(el, text) {
    focusEnd(el);
    const before = new InputEvent("beforeinput", {
      bubbles: true,
      cancelable: true,
      inputType: "insertText",
      data: text,
    });
    el.dispatchEvent(before);
    const after = new InputEvent("input", {
      bubbles: true,
      cancelable: false,
      inputType: "insertText",
      data: text,
    });
    el.dispatchEvent(after);
    return true;
  }

  function viaPaste(el, text) {
    focusEnd(el);
    const dt = new DataTransfer();
    dt.setData("text/plain", text);
    const evt = new ClipboardEvent("paste", {
      bubbles: true,
      cancelable: true,
      clipboardData: dt,
    });
    el.dispatchEvent(evt);
    return true;
  }

  const STRATEGIES = [
    ["nativeSetter", viaNativeSetter],
    ["execCommand", viaExecCommand],
    ["inputEvent", viaInputEvent],
    ["paste", viaPaste],
  ];

  /**
   * Type `text` into `el`, verifying via read-back. Throws if no strategy lands.
   * @returns {Promise<string>} name of the strategy that worked
   */
  async function type(el, text, { retries = 1 } = {}) {
    const want = norm(text);
    for (let attempt = 0; attempt <= retries; attempt++) {
      for (const [name, fn] of STRATEGIES) {
        try {
          clear(el);
          fn(el, text);
          // Give the framework a tick to reconcile.
          await Probe.cadence.sleep(80);
          const got = norm(readBack(el));
          // Accept if the field now holds essentially the wanted text. Editors
          // sometimes add/trim a trailing char, so allow near-equality.
          const ok = got === want || (got.includes(want) && got.length <= want.length + 4);
          if (ok) {
            log.info(`typed via ${name} (attempt ${attempt})`);
            return name;
          }
        } catch (e) {
          log.warn(`strategy ${name} threw`, e?.message || e);
        }
      }
      await Probe.cadence.sleep(150);
    }
    throw new Error(
      `input-injector: could not verify typed text (wanted ${want.length} chars, got "${norm(readBack(el)).slice(0, 60)}...")`
    );
  }

  Probe.injector = { type, readBack, clear, isTextField };
})();
