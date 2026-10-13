// The setup checklist. Renders /api/state (polled), one row per chatbot. All text comes from strings.json.
(() => {
  const LANG = new URLSearchParams(location.search).get("lang") || "en";
  let S = {}, BOTS = {}, last = "", connected = false;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const t = (k) => S[k] || k;
  const GREEN = new Set(["ok", "rate_limited"]);
  const PILL = { ok: "ok", rate_limited: "warn", challenge: "bad", logged_out: "bad", not_open: "", loading: "" };

  async function api(path, body) {
    const r = await fetch("/api/" + path, body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    return r.json();
  }

  function rowHtml(c) {
    const info = BOTS[c.id] || {};
    const state = c.skipped ? "skipped" : c.state;
    const label = c.skipped ? t("skipped") : t("status_" + c.state);
    const hint = c.skipped ? "" : (S["status_hint_" + c.state] || "");
    const banner = c.text && (c.state === "rate_limited" || c.state === "challenge") ? ` <span class="hint">« ${esc(c.text.slice(0, 140))} »</span>` : "";
    return `<div class="row${c.skipped ? " skipped" : ""}" data-id="${c.id}">
      <div>
        <div class="name">${esc(c.label)} <span class="pill ${PILL[state] || ""}">${esc(label)}</span></div>
        <div class="hint">${esc(hint)}${banner}</div>
      </div>
      <div class="actions">
        <a class="btn primary" href="${esc(c.site)}" target="_blank" rel="noopener">${esc(t("open_site"))}</a>
        <button class="link" data-recheck="1">${esc(t("recheck"))}</button>
        <button class="link" data-skip="${c.skipped ? "undo" : "skip"}">${esc(c.skipped ? t("unskip") : t("skip"))}</button>
      </div>
      <div class="detail">
        <ol>${(info.steps || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        ${info.unsure ? `<div class="note">⚠ ${esc(info.unsure)}</div>` : ""}
        ${info.limits ? `<div class="note"><b>${esc(t("free_plan"))}:</b> ${esc(info.limits.replace(/^Free plan:\s*/, ""))}</div>` : ""}
      </div>
    </div>`;
  }

  function render(st) {
    const key = JSON.stringify(st);
    if (key === last) return;
    last = key;
    connected = st.connected;
    $("rows").innerHTML = st.chatbots.map(rowHtml).join("");
    const active = st.chatbots.filter((c) => !c.skipped);
    const anyGreen = st.connected && active.some((c) => GREEN.has(c.state));
    const running = st.test.state === "running";
    const passed = Object.values(st.test.results || {}).some((r) => r.verdict === "ok");
    $("test-btn").disabled = !anyGreen || running || st.saved;
    $("done-btn").disabled = st.test.state !== "done" || !passed || st.saved;
    $("test-state").textContent = running ? t("test_running") : (!anyGreen && st.test.state === "idle" ? t("test_waiting") : "");
    const res = st.test.results || {};
    $("results").innerHTML = Object.entries(res).map(([id, r]) => {
      const lab = (st.chatbots.find((c) => c.id === id) || {}).label || id;
      const cls = r.verdict === "ok" ? "ok" : r.verdict === "rate_limited" ? "warn" : r.verdict === "skipped" ? "" : "bad";
      return `<li><span class="who">${esc(lab)}</span><span class="pill ${cls}">${esc(t("verdict_" + r.verdict))}</span><span class="why">${esc((r.detail || "").slice(0, 160))}</span></li>`;
    }).join("");
    if (st.saved) {
      $("done-panel").hidden = false;
      $("next").textContent = [t("next_import"), t("next_run"), t("next_export")].join("\n");
    }
  }

  async function tick() {
    try { render(await api("state")); } catch (_) { /* server gone: setup finished */ }
  }

  $("rows").addEventListener("click", async (e) => {
    const o = e.target.closest("a.btn");
    if (o && connected) {   // let the extension open or focus the tab: no popup blocker, no duplicate tabs
      e.preventDefault();
      await api("open", { id: o.closest(".row").dataset.id });
      return;
    }
    const rc = e.target.closest("[data-recheck]");
    if (rc) { render(await api("recheck", { id: rc.closest(".row").dataset.id })); return; }
    const b = e.target.closest("[data-skip]");
    if (!b) return;
    const id = b.closest(".row").dataset.id;
    render(await api("skip", { id, undo: b.dataset.skip === "undo" }));
  });
  $("test-btn").addEventListener("click", async () => render(await api("test", {})));
  $("done-btn").addEventListener("click", async () => render(await api("done", {})));

  (async () => {
    const all = await api("strings");
    S = all[LANG] || all.en;
    BOTS = (all.chatbots && (all.chatbots[LANG] || all.chatbots.en)) || {};
    const st = await api("state");
    $("title").textContent = st.mode === "login" ? t("login_title") : t("setup_title");
    $("intro").textContent = t("setup_intro") + " " + t("row_note_private");
    $("test-title").textContent = t("test_title");
    $("test-intro").textContent = t("test_intro");
    $("test-btn").textContent = t("test_button");
    $("done-btn").textContent = t("done_button");
    $("done-title").textContent = t("done_title");
    $("done-text").textContent = t("done_text");
    render(st);
    setInterval(tick, 1500);
  })();
})();
