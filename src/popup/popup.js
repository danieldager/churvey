// Popup: pre-run configuration + run control. All run logic lives in the SW and
// content scripts; the popup just builds a runConfig, sends commands, and renders
// the overview from the SW.
(() => {
  const Probe = globalThis.Probe;
  const $ = (id) => document.getElementById(id);

  function sendToSW(message) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (resp) => {
        resolve(
          chrome.runtime.lastError
            ? { ok: false, error: chrome.runtime.lastError.message }
            : resp || { ok: false, error: "no response" }
        );
      });
    });
  }

  async function currentWindowId() {
    const w = await chrome.windows.getCurrent();
    return w ? w.id : undefined;
  }

  async function sendToActiveTab(message) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return { ok: false, error: "no active tab" };
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id, message, (resp) => {
        resolve(
          chrome.runtime.lastError
            ? { ok: false, error: chrome.runtime.lastError.message }
            : resp || { ok: false, error: "no response" }
        );
      });
    });
  }

  // --- output folder via File System Access API (handle persisted in IndexedDB) ---
  const IDB = { name: "probe-fs", store: "handles", key: "outDir" };
  function idb() {
    return new Promise((res, rej) => {
      const r = indexedDB.open(IDB.name, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(IDB.store);
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function idbSet(val) {
    const db = await idb();
    return new Promise((res, rej) => {
      const tx = db.transaction(IDB.store, "readwrite");
      tx.objectStore(IDB.store).put(val, IDB.key);
      tx.oncomplete = () => res();
      tx.onerror = () => rej(tx.error);
    });
  }
  async function idbGet() {
    const db = await idb();
    return new Promise((res, rej) => {
      const tx = db.transaction(IDB.store, "readonly");
      const g = tx.objectStore(IDB.store).get(IDB.key);
      g.onsuccess = () => res(g.result || null);
      g.onerror = () => rej(g.error);
    });
  }

  async function getWritableDir() {
    const handle = await idbGet();
    if (!handle) throw new Error("no output folder set — click 'Set output folder…'");
    let perm = await handle.queryPermission({ mode: "readwrite" });
    if (perm !== "granted") perm = await handle.requestPermission({ mode: "readwrite" });
    if (perm !== "granted") throw new Error("permission to write to folder denied");
    return handle;
  }

  async function writeFile(dirHandle, name, text) {
    const fh = await dirHandle.getFileHandle(name, { create: true });
    const w = await fh.createWritable();
    await w.write(text);
    await w.close();
  }

  async function showDirName() {
    const h = await idbGet();
    $("dirname").textContent = h ? h.name : "none";
  }

  // --- config parsing ---

  function selectedProviders() {
    return Probe.providers.LIST.filter((p) => $("prov-" + p.id).checked).map((p) => p.id);
  }

  function parseItems(text, kind) {
    const raw = text.trim();
    if (!raw && kind === "personas") return [];
    const obj = JSON.parse(raw);
    const items = Array.isArray(obj) ? obj : obj.items;
    if (!Array.isArray(items)) throw new Error(`${kind}: expected an array or {items:[...]}`);
    return items;
  }

  function parseQuestions() {
    const items = parseItems($("questions").value, "questions");
    if (!items.length) throw new Error("no questions");
    items.forEach((it, i) => {
      if (!it.id) it.id = `q${String(i + 1).padStart(3, "0")}`;
      if (!it.text) throw new Error(`question ${i} missing text`);
    });
    return items;
  }

  function parsePersonas() {
    const items = parseItems($("personas").value, "personas");
    items.forEach((it, i) => {
      if (!it.id) it.id = `p${String(i + 1).padStart(3, "0")}`;
      if (!it.preamble) throw new Error(`persona ${i} missing preamble`);
    });
    return items;
  }

  function buildConfig() {
    const providers = selectedProviders();
    if (!providers.length) throw new Error("select at least one provider");
    const questions = parseQuestions();
    const personas = parsePersonas();
    const repetitions = Math.max(1, parseInt($("reps").value, 10) || 1);
    const tabsPerProvider = Math.max(1, Math.min(6, parseInt($("tabs").value, 10) || 1));
    return {
      providers,
      questions,
      personas,
      repetitions,
      tabsPerProvider,
      config: { responseTimeoutMs: 150000, cadence: {}, private: $("private").checked },
    };
  }

  function updatePreview() {
    try {
      const cfg = buildConfig();
      $("qcount").textContent = String(cfg.questions.length);
      $("pcount").textContent = String(cfg.personas.length);
      $("preview").textContent = `${Probe.runPlan.queueLength(cfg)} items`;
      $("preview").classList.remove("bad");
    } catch (e) {
      $("preview").textContent = e.message;
      $("preview").classList.add("bad");
    }
  }

  // --- rendering ---

  function renderOverview(o) {
    $("reccount").textContent = `${o.recordCount || 0} records`;
    const list = $("provlist");
    list.innerHTML = "";
    const per = o.perProvider || {};
    const ids = Object.keys(per).length ? Object.keys(per) : selectedProviders();
    for (const id of ids) {
      const v = per[id] || {};
      const total = v.total || 0;
      const done = v.done || 0;
      const status = v.status || "—";
      const row = document.createElement("div");
      row.className = "prov";
      row.innerHTML = `
        <span class="name">${id}</span>
        <span class="minibar"><div style="width:${total ? (done / total) * 100 : 0}%"></div></span>
        <span class="st ${status}">${done}/${total}</span>`;
      const detail = `ok ${v.ok || 0} · trunc ${v.truncated || 0} · err ${v.error || 0} · ${status}`;
      row.querySelector(".st").title = detail;
      row.querySelector(".name").title = detail;
      list.appendChild(row);
    }
  }

  async function refresh() {
    const o = await sendToSW({ type: Probe.MSG.GET_OVERVIEW });
    if (o.ok) renderOverview(o);
    $("log").textContent = (await Probe.log.getRing()).slice(-60).join("\n");
    $("log").scrollTop = $("log").scrollHeight;
  }

  function flash(msg, bad) {
    $("preview").textContent = msg;
    $("preview").classList.toggle("bad", !!bad);
  }

  // --- actions ---

  async function onStart() {
    let runConfig;
    try {
      runConfig = buildConfig();
    } catch (e) {
      return flash(e.message, true);
    }
    const windowId = await currentWindowId();
    const r = await sendToSW({ type: Probe.MSG.START_RUN, runConfig, windowId });
    if (!r.ok) return flash("start failed: " + r.error, true);
    flash(`started: ${r.queueLen} items x ${runConfig.providers.length} providers`);
    setTimeout(refresh, 800);
  }

  async function onResume() {
    const windowId = await currentWindowId();
    const r = await sendToSW({ type: Probe.MSG.RESUME_RUN, windowId });
    if (!r.ok) return flash("resume failed: " + r.error, true);
    flash(`resumed: ${(r.resumed || []).join(", ") || "none"}`);
    setTimeout(refresh, 800);
  }

  async function onExport() {
    const r = await sendToSW({ type: Probe.MSG.EXPORT });
    if (!r.ok) return flash("export failed: " + r.error, true);
    flash(`exported ${r.count} → ${r.filename}`);
    if (r.summaryText) $("log").textContent = r.summaryText;
  }

  async function onClear() {
    if (!confirm("Delete all saved records AND reset run progress?")) return;
    await sendToSW({ type: Probe.MSG.CLEAR_RECORDS });
    setTimeout(refresh, 300);
  }

  function downloadText(name, text, mime) {
    const blob = new Blob([text], { type: mime || "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  async function onPickDir() {
    try {
      const handle = await window.showDirectoryPicker({ mode: "readwrite" });
      await idbSet(handle);
      await showDirName();
      flash("output folder: " + handle.name);
    } catch (e) {
      if (e && e.name === "AbortError") return; // user cancelled
      flash("pick folder failed: " + e.message, true);
    }
  }

  async function onSaveDir() {
    try {
      const dir = await getWritableDir();
      const records = await Probe.storage.getAllRecords();
      const cfg = await Probe.storage.getRunConfig();
      const runId = (cfg && cfg.runId) || "run";
      const jsonl = records.map((r) => JSON.stringify(r)).join("\n");
      const summary = Probe.summary.build(records, cfg);
      const summaryText = Probe.summary.formatText(summary);
      await writeFile(dir, runId + ".jsonl", jsonl);
      await writeFile(dir, runId + ".summary.json", JSON.stringify(summary, null, 2));
      await writeFile(dir, runId + ".summary.txt", summaryText);
      flash(`saved ${records.length} + summary → ${dir.name}/`);
      $("log").textContent = summaryText;
    } catch (e) {
      flash("save failed: " + e.message, true);
    }
  }

  async function onCapture() {
    const r = await sendToActiveTab({ type: Probe.MSG.DIAGNOSE });
    if (!r.ok) return flash("capture failed: " + r.error + " (focus a provider tab)", true);
    const d = r.diagnostics;
    const json = JSON.stringify(d, null, 2);
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const name = `diagnostics-${d.provider || "page"}-${stamp}.json`;
    try {
      const dir = await getWritableDir();
      await writeFile(dir, name, json);
      flash(`captured → ${dir.name}/${name}`);
    } catch (_) {
      downloadText(name, json);
      flash(`captured → downloaded ${name}`);
    }
  }

  // --- init ---

  function renderProviderChecks() {
    const wrap = $("providers");
    wrap.innerHTML = "";
    for (const p of Probe.providers.LIST) {
      const lbl = document.createElement("label");
      lbl.innerHTML = `<input type="checkbox" id="prov-${p.id}" checked /> ${p.label}`;
      wrap.appendChild(lbl);
      lbl.querySelector("input").addEventListener("change", updatePreview);
    }
  }

  async function loadDefaults() {
    try {
      const q = await (await fetch(chrome.runtime.getURL("src/config/questions.json"))).text();
      $("questions").value = q.trim();
    } catch (_) {
      $("questions").value = '{ "items": [ { "id": "q001", "text": "" } ] }';
    }
    try {
      const p = await (await fetch(chrome.runtime.getURL("src/config/personas.json"))).json();
      $("personas").value = JSON.stringify(p.items || [], null, 2);
    } catch (_) {
      $("personas").value = "[]";
    }
  }

  function wire() {
    $("start").addEventListener("click", onStart);
    $("resume").addEventListener("click", onResume);
    $("pause").addEventListener("click", async () => {
      await sendToSW({ type: Probe.MSG.PAUSE_ALL });
      setTimeout(refresh, 400);
    });
    $("stop").addEventListener("click", async () => {
      await sendToSW({ type: Probe.MSG.STOP_ALL });
      setTimeout(refresh, 400);
    });
    $("export").addEventListener("click", onExport);
    $("clear").addEventListener("click", onClear);
    $("refresh").addEventListener("click", refresh);
    $("pickdir").addEventListener("click", onPickDir);
    $("savedir").addEventListener("click", onSaveDir);
    $("capture").addEventListener("click", onCapture);
    $("clearlog").addEventListener("click", async () => {
      await Probe.log.clearRing();
      $("log").textContent = "";
    });
    $("reps").addEventListener("input", updatePreview);
    $("questions").addEventListener("input", updatePreview);
    $("personas").addEventListener("input", updatePreview);
    $("autocycle").addEventListener("change", (e) =>
      Probe.storage.set("autoCycle", e.target.checked)
    );

    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && (msg.type === Probe.MSG.STATUS || msg.type === Probe.MSG.PROGRESS)) refresh();
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    renderProviderChecks();
    wire();
    await loadDefaults();
    updatePreview();
    $("autocycle").checked = await Probe.storage.get("autoCycle", true);
    await showDirName();
    await refresh();
  });
})();
