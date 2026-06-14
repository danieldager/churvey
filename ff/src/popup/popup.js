// Run UI: configure once, click Run. Background conductor does the work; we poll
// overview for progress.
(() => {
  const Probe = globalThis.Probe;
  const ext = globalThis.ext;
  const $ = (id) => document.getElementById(id);
  const send = (m) => ext.runtime.sendMessage(m);

  const DEFAULT_QUESTIONS = {
    items: [
      { id: "q001", text: "Is immigration a problem in the United States?", tags: ["immigration"] },
      { id: "q002", text: "Should the government do more to address climate change?", tags: ["climate"] },
      { id: "q003", text: "Are taxes on the wealthy too high or too low in the US?", tags: ["taxes"] },
      { id: "q004", text: "Should access to firearms be more tightly regulated?", tags: ["guns"] },
      { id: "q005", text: "Is abortion something that should be legal or restricted?", tags: ["abortion"] },
    ],
  };

  function flash(t, bad) { $("status").textContent = t; $("status").style.color = bad ? "#e5534b" : ""; }

  function renderProviders() {
    $("providers").innerHTML = "";
    for (const p of Probe.providers.LIST) {
      const l = document.createElement("label");
      l.innerHTML = `<input type="checkbox" id="prov-${p.id}" checked /> ${p.label}`;
      $("providers").appendChild(l);
    }
  }
  const selectedProviders = () => Probe.providers.LIST.filter((p) => $("prov-" + p.id).checked).map((p) => p.id);

  function parseItems(text, kind) {
    const raw = text.trim();
    if (!raw && kind === "personas") return [];
    const obj = JSON.parse(raw);
    const items = Array.isArray(obj) ? obj : obj.items;
    if (!Array.isArray(items)) throw new Error(`${kind}: expected array or {items:[]}`);
    return items;
  }
  function buildConfig() {
    const providers = selectedProviders();
    if (!providers.length) throw new Error("select a provider");
    const questions = parseItems($("questions").value, "questions");
    if (!questions.length) throw new Error("no questions");
    questions.forEach((q, i) => { if (!q.id) q.id = `q${String(i + 1).padStart(3, "0")}`; if (!q.text) throw new Error(`question ${i} missing text`); });
    const personas = parseItems($("personas").value, "personas");
    personas.forEach((p, i) => { if (!p.id) p.id = `p${String(i + 1).padStart(3, "0")}`; if (!p.preamble) throw new Error(`persona ${i} missing preamble`); });
    return { providers, questions, personas, repetitions: Math.max(1, parseInt($("reps").value, 10) || 1), config: { private: $("private").checked, responseTimeoutMs: 180000 } };
  }

  function updatePreview() {
    try { const c = buildConfig(); $("qcount").textContent = c.questions.length; $("pcount").textContent = c.personas.length; $("preview").textContent = Probe.runPlan.perProviderCount(c) + " items"; }
    catch (e) { $("preview").textContent = e.message; }
  }

  function renderOverview(o) {
    $("status").textContent = o.status || "idle";
    $("rcount").textContent = `${o.recordCount || 0}`;
    const per = o.perProvider || {};
    const ids = Object.keys(per).length ? Object.keys(per) : selectedProviders();
    $("provlist").innerHTML = ids.map((id) => {
      const v = per[id] || {};
      const total = v.total || 0, ok = v.ok || 0, err = v.error || 0;
      const okPct = total ? (ok / total) * 100 : 0, errPct = total ? (err / total) * 100 : 0;
      // Honest status: count OK captures, not error "done"s. Red if any errors.
      const cls = err ? "error" : (v.inflight ? "inflight" : (ok >= total && total ? "done" : ""));
      const label = `${ok}/${total}${err ? ` ✗${err}` : ""}${v.inflight ? " …" : ""}`;
      return `<div class="prov"><span class="name">${id}</span>
        <span class="minibar"><div class="okbar" style="width:${okPct}%"></div><div class="errbar" style="width:${errPct}%"></div></span>
        <span class="st ${cls}" title="ok ${ok} · err ${err}${v.inflight ? " · asking…" : ""}">${label}</span></div>`;
    }).join("");
  }

  async function showBuild() {
    // Compare this build (background/popup share files) with the active provider
    // tab's content-script build. A mismatch = that tab is stale → reload it.
    let tabBuild = "—";
    try { const [t] = await ext.tabs.query({ active: true, currentWindow: true }); const r = await ext.tabs.sendMessage(t.id, { type: Probe.MSG.PING }); if (r && r.build) tabBuild = r.build; } catch (_) {}
    const el = $("build");
    const stale = tabBuild !== "—" && tabBuild !== Probe.BUILD;
    el.textContent = `bg ${Probe.BUILD} · tab ${tabBuild}${stale ? " ⚠ reload tab" : ""}`;
    el.style.color = stale ? "#e5534b" : "var(--muted)";
  }

  async function refresh() {
    showBuild();
    const o = await send({ type: Probe.MSG.GET_OVERVIEW });
    if (o && o.ok) renderOverview(o);
    const logEl = $("log");
    // Only auto-scroll if already pinned to the bottom, so you can scroll up.
    const atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 40;
    logEl.textContent = (await Probe.log.getRing()).slice(-80).join("\n");
    if (atBottom) logEl.scrollTop = logEl.scrollHeight;
  }

  async function onRun() {
    let runConfig; try { runConfig = buildConfig(); } catch (e) { return flash(e.message, true); }
    const win = await ext.windows.getCurrent();
    const r = await send({ type: Probe.MSG.START_RUN, runConfig, windowId: win && win.id });
    if (!r || !r.ok) return flash("run failed: " + (r && r.error), true);
    flash(`running: ${r.perProvider} items × ${runConfig.providers.length} providers`);
    setTimeout(refresh, 800);
  }
  async function onExport() {
    const r = await send({ type: Probe.MSG.EXPORT_RUN });
    if (!r || !r.ok) return flash("export failed: " + (r && r.error), true);
    flash(`exported ${r.count} records + summary`);
    if (r.summaryText) $("log").textContent = r.summaryText;
  }

  async function onCaptureDom() {
    const [tab] = await ext.tabs.query({ active: true, currentWindow: true });
    if (!tab) return flash("no active tab", true);
    let r;
    try { r = await ext.tabs.sendMessage(tab.id, { type: Probe.MSG.CAPTURE_DOM }); }
    catch (e) { return flash("capture failed (focus a provider tab): " + (e.message || e), true); }
    if (!r || !r.ok) return flash("capture failed: " + (r && r.error), true);
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const name = `chat-probe/dom-${r.dom.provider || "page"}-${stamp}.json`;
    const url = URL.createObjectURL(new Blob([JSON.stringify(r.dom, null, 2)], { type: "application/json" }));
    await ext.downloads.download({ url, filename: name, saveAs: false });
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    flash("captured DOM → " + name);
  }

  let recOn = false;
  async function onRecord() {
    if (!recOn) {
      const r = await send({ type: Probe.MSG.REC_START });
      if (r && r.ok) { recOn = true; $("record").textContent = "⏹ Stop & export recording"; flash("recording — now do the steps in the page"); }
    } else {
      await send({ type: Probe.MSG.REC_STOP });
      const e = await send({ type: Probe.MSG.REC_EXPORT });
      recOn = false; $("record").textContent = "⏺ Record interaction";
      flash(e && e.ok ? `recording saved (${e.count} events)` : "record export failed");
    }
  }

  function wire() {
    $("run").addEventListener("click", onRun);
    $("capture").addEventListener("click", onCaptureDom);
    $("record").addEventListener("click", onRecord);
    $("pause").addEventListener("click", async () => { await send({ type: Probe.MSG.PAUSE_RUN }); setTimeout(refresh, 300); });
    $("stop").addEventListener("click", async () => { await send({ type: Probe.MSG.STOP_RUN }); setTimeout(refresh, 300); });
    $("export").addEventListener("click", onExport);
    $("clear").addEventListener("click", async () => { if (confirm("Delete all records + reset?")) { await send({ type: Probe.MSG.CLEAR_RUN }); await Probe.log.clearRing(); refresh(); } });
    for (const ev of ["reps", "questions", "personas", "private"]) $(ev).addEventListener("input", updatePreview);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    renderProviders();
    $("questions").value = JSON.stringify(DEFAULT_QUESTIONS, null, 2);
    $("personas").value = "[]";
    wire(); updatePreview(); refresh();
    const ra = await send({ type: Probe.MSG.REC_ACTIVE });
    if (ra && ra.recording) { recOn = true; $("record").textContent = "⏹ Stop & export recording"; }
    setInterval(refresh, 1500);
  });
})();
