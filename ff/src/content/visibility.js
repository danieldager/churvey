// Makes every provider page believe it is on screen and focused, whatever the window is really doing (covered,
// minimised, on another Space, headless). Chat apps pause or abort streams on `visibilitychange`, throttle
// their render loop on a hidden tab, and some stop polling when `document.hasFocus()` is false; none of that
// should ever cost an answer.
//
// Runs at document_start in the extension's content-script world and edits the PAGE's objects through
// `wrappedJSObject` + `exportFunction`: an inline <script> would be blocked by these sites' CSP.
// Idempotent; every step is individually guarded (a failed override must not stop the others).
(() => {
  const w = window.wrappedJSObject;
  if (!w || w.__probeVisible) return;
  const tryDo = (fn) => { try { fn(); } catch (_) {} };
  const getter = (obj, prop, value) => tryDo(() => Object.defineProperty(obj, prop, {
    configurable: true, enumerable: true, get: exportFunction(() => value, w),
  }));

  // 1. The state itself. Defined on the prototype and on the instance (pages sometimes cache `document`).
  for (const target of [w.Document.prototype, w.document]) {
    getter(target, "hidden", false);
    getter(target, "webkitHidden", false);
    getter(target, "visibilityState", "visible");
    getter(target, "webkitVisibilityState", "visible");
  }
  tryDo(() => { w.Document.prototype.hasFocus = exportFunction(() => true, w); });
  tryDo(() => { w.document.hasFocus = exportFunction(() => true, w); });

  // 2. The events that announce a change: swallowed before any page listener sees them (capture phase,
  // registered first, at document_start). `blur`/`focus` are left alone: composers need real focus events.
  const stop = (e) => { e.stopImmediatePropagation(); };
  for (const t of [window, document]) {
    for (const type of ["visibilitychange", "webkitvisibilitychange", "freeze"]) tryDo(() => t.addEventListener(type, stop, true));
  }

  // 3. requestAnimationFrame is throttled to ~0 in a hidden or occluded window. Keep the page's own rAF, but make
  // sure each callback fires within ~50ms regardless (once: whichever of the two comes first wins).
  tryDo(() => {
    const raf = w.requestAnimationFrame.bind(w), caf = w.cancelAnimationFrame.bind(w);
    const pending = new Map();
    w.requestAnimationFrame = exportFunction(function (cb) {
      let done = false, timer = 0;
      const run = (t) => { if (done) return; done = true; clearTimeout(timer); pending.delete(id); cb(typeof t === "number" ? t : performance.now()); };
      const id = raf(exportFunction(run, w));
      timer = setTimeout(() => run(performance.now()), 50);
      pending.set(id, () => { done = true; clearTimeout(timer); });
      return id;
    }, w);
    w.cancelAnimationFrame = exportFunction(function (id) {
      const stopFn = pending.get(id); if (stopFn) { stopFn(); pending.delete(id); }
      caf(id);
    }, w);
  });

  tryDo(() => { Object.defineProperty(w, "__probeVisible", { value: true }); });
})();
