// The question-set editor. Holds the open set in `cur`, edits it in place, saves with PUT /api/sets/<name>.
// The server validates with the same rules as `churvey questions validate` and returns readable errors.
(() => {
  const LANG = new URLSearchParams(location.search).get("lang") || "en";
  let S = {}, BOTS = [], cur = null, loadedName = null, dirty = false;
  const $ = (id) => document.getElementById(id);
  const t = (k) => S[k] || k;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function api(method, path, body) {
    const r = await fetch("/api/" + path, { method, headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    return { ok: r.ok, data: await r.json() };
  }

  function setDirty(v) {
    dirty = v;
    $("status").textContent = v ? t("q_unsaved") : t("q_saved");
  }

  function showErrors(errs) {
    $("errors").hidden = !errs || !errs.length;
    $("errors").innerHTML = errs && errs.length ? `${esc(t("q_errors"))}<ul>${errs.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : "";
  }

  async function loadList() {
    const { data } = await api("GET", "sets");
    $("sets").innerHTML = data.map((s) => `<li data-name="${esc(s.name)}" class="${cur && s.name === loadedName ? "on" : ""}">
      <span>${esc(s.name)}</span><span class="n">${s.count == null ? "!" : s.count}</span></li>`).join("");
    $("empty").hidden = data.length > 0 || !!cur;
    return data;
  }

  function open(qs, name, isDirty) {
    cur = qs;
    loadedName = name;
    cur.defaults = cur.defaults || {};
    $("editor").hidden = false;
    $("empty").hidden = true;
    $("f-name").value = cur.name || "";
    $("f-language").value = cur.language || "";
    $("f-description").value = cur.description || "";
    $("f-repeat").value = cur.defaults.repeat || 1;
    $("f-private").checked = cur.defaults.private !== false;
    const on = new Set(cur.defaults.chatbots || []);
    $("f-bots").innerHTML = BOTS.map((b) => `<label><input type="checkbox" value="${b.id}" ${on.has(b.id) ? "checked" : ""}> ${esc(b.label)}</label>`).join("");
    renderRows();
    showErrors(null);
    setDirty(!!isDirty);
    loadList();
  }

  function renderRows() {
    $("rows").innerHTML = cur.questions.map((q, i) => `<tr data-i="${i}">
      <td class="num">${i + 1}</td>
      <td class="c-id"><input type="text" data-f="id" value="${esc(q.id)}"></td>
      <td><textarea data-f="text" rows="${Math.max(2, Math.ceil((q.text || "").length / 34))}">${esc(q.text)}</textarea></td>
      <td class="c-tags"><input type="text" data-f="tags" value="${esc((q.tags || []).join(", "))}"></td>
      <td class="c-group"><input type="text" data-f="group" value="${esc(q.group)}"></td>
      <td class="c-meta"><textarea data-f="meta" rows="2">${esc(q.meta ? JSON.stringify(q.meta) : "")}</textarea></td>
      <td class="ops"><button data-op="up" title="${esc(t("q_move_up"))}">↑</button><button data-op="down" title="${esc(t("q_move_down"))}">↓</button><button data-op="rm" title="${esc(t("q_remove"))}">✕</button></td>
    </tr>`).join("");
  }

  // Reads every field back into `cur`. Meta that is not valid JSON stays as text so the server reports it.
  function collect() {
    cur.name = $("f-name").value.trim();
    cur.description = $("f-description").value;
    const lang = $("f-language").value.trim();
    if (lang) cur.language = lang; else delete cur.language;
    cur.defaults = { chatbots: [...$("f-bots").querySelectorAll("input:checked")].map((x) => x.value),
                     repeat: parseInt($("f-repeat").value, 10) || 1, private: $("f-private").checked };
    const bad = [];
    [...$("rows").children].forEach((tr, i) => {
      const q = cur.questions[i], get = (f) => tr.querySelector(`[data-f="${f}"]`).value;
      const id = get("id").trim(), tags = get("tags").split(",").map((x) => x.trim()).filter(Boolean), group = get("group").trim(), meta = get("meta").trim();
      q.text = get("text");
      if (id) q.id = id; else delete q.id;
      if (tags.length) q.tags = tags; else delete q.tags;
      if (group) q.group = group; else delete q.group;
      if (meta) { try { q.meta = JSON.parse(meta); } catch (_) { bad.push(`question ${i + 1}: extra data is not valid JSON`); } } else delete q.meta;
    });
    return bad;
  }

  async function save() {
    const bad = collect();
    if (bad.length) return showErrors(bad);
    const { ok, data } = await api("PUT", "sets/" + encodeURIComponent(loadedName || cur.name), cur);
    if (!ok) return showErrors(data.errors || [data.error]);
    open(data, data.name, false);
  }

  $("rows").addEventListener("input", () => setDirty(true));
  $("editor").addEventListener("change", () => setDirty(true));
  $("rows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-op]");
    if (!b) return;
    collect();
    const i = +b.closest("tr").dataset.i, qs = cur.questions;
    if (b.dataset.op === "rm") qs.splice(i, 1);
    if (b.dataset.op === "up" && i > 0) [qs[i - 1], qs[i]] = [qs[i], qs[i - 1]];
    if (b.dataset.op === "down" && i < qs.length - 1) [qs[i + 1], qs[i]] = [qs[i], qs[i + 1]];
    renderRows();
    setDirty(true);
  });
  $("add-btn").addEventListener("click", () => {
    collect();
    cur.questions.push({ text: "" });
    renderRows();
    setDirty(true);
    $("rows").lastElementChild.querySelector("textarea").focus();
  });
  $("sets").addEventListener("click", async (e) => {
    const li = e.target.closest("li");
    if (!li || (dirty && !confirm(t("q_unsaved") + " — discard?"))) return;
    const { ok, data } = await api("GET", "sets/" + encodeURIComponent(li.dataset.name));
    if (ok) open(data, li.dataset.name, false); else { showErrors(data.errors); }
  });
  $("new-btn").addEventListener("click", async () => {
    const name = prompt(t("q_name"), "my-questions");
    if (!name) return;
    const { data } = await api("POST", "new", { name });
    open(data, data.name, false);
  });
  $("upload-btn").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", async () => {
    const f = $("file").files[0];
    if (!f) return;
    const { ok, data } = await api("POST", "import", { filename: f.name, content: await f.text() });
    $("file").value = "";
    if (!ok) { $("editor").hidden = !cur; return showErrors(data.errors); }
    open(data, null, true);   // not saved yet: Save writes it
  });
  $("save-btn").addEventListener("click", save);
  $("download-btn").addEventListener("click", () => {
    collect();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(cur, null, 2) + "\n"], { type: "application/json" }));
    a.download = (cur.name || "questions") + ".json";
    a.click();
  });
  $("delete-btn").addEventListener("click", async () => {
    if (!loadedName || !confirm(t("q_confirm_delete"))) return;
    await api("DELETE", "sets/" + encodeURIComponent(loadedName));
    cur = null; loadedName = null;
    $("editor").hidden = true;
    loadList();
  });
  window.addEventListener("beforeunload", (e) => { if (dirty) e.preventDefault(); });

  (async () => {
    const all = (await api("GET", "strings")).data;
    S = all[LANG] || all.en;
    BOTS = (await api("GET", "chatbots")).data;
    document.querySelectorAll("[data-s]").forEach((el) => { el.textContent = t(el.dataset.s); });
    $("title").textContent = t("questions_title");
    $("new-btn").textContent = t("q_new");
    $("upload-btn").textContent = t("q_upload");
    $("save-btn").textContent = t("q_save");
    $("download-btn").textContent = t("q_download");
    $("delete-btn").textContent = t("q_delete_set");
    $("add-btn").textContent = "+ " + t("q_add_row");
    $("empty").textContent = t("q_empty");
    const sets = await loadList();
    const want = new URLSearchParams(location.search).get("set") || (sets[0] && sets[0].name);
    if (want) { const { ok, data } = await api("GET", "sets/" + encodeURIComponent(want)); if (ok) open(data, want, false); }
  })();
})();
