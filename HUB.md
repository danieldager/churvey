# Chat UI Research Probe — Hub

> Firefox extension that asks a fixed question set to 5 AI chat web UIs (ChatGPT, Gemini, Grok, Claude, DeepSeek) in a real logged-in session and captures each response at the network layer as JSONL — to study how consumer chat assistants answer political questions as a *typical user* sees them (not via the APIs). · Status: capture working for all 5 providers (docs dated 2026-06-14); research/analysis phase not started. · Refresh with /hub.

## 🧭 Navigate

| Concern | Where |
|---|---|
| Project guide / why this design | [README.md](README.md) |
| Active build (Firefox MV2): architecture, per-provider notes, troubleshooting | [ff/README.md](ff/README.md) |
| Structure / repo map | _(no REPO_MAP.md)_ — see "Architecture" in [ff/README.md](ff/README.md); `ff/` = active, `src/` + root [manifest.json](manifest.json) = legacy Chrome MV3 |
| Backlog / planned work | [FUTURE_WORK.md](FUTURE_WORK.md) |
| History | `git log` (2 commits; no clog/) |
| Docs | [ff/README.md](ff/README.md) (per-provider endpoints, data format) — no `docs/` dir |
| Captured data | `data/` (git-ignored symlink → iCloud devsync; contains auth tokens — never commit) |
| Eval / analysis results | _(coming — research phase + analysis tooling not built)_ |
| Cross-project knowledge | vault → projects/tools |

## 📌 Status at a glance

- **Two builds.** `ff/` is the **active** Firefox MV2 build — use this. `src/` + root `manifest.json` is the **legacy Chrome MV3** DOM-scraping version, abandoned (MV3 can't read response bodies) and kept for reference only.
- **Capture working for all 5 providers** (ChatGPT, Gemini, Grok, Claude, DeepSeek), each in a fresh private/incognito chat, responses saved as JSONL + a per-run summary (per-provider capture rate, latency, model labels, blocked flags).
- **Network-layer capture** via Firefox-only `webRequest.filterResponseData` — records the exact response stream, no DOM scraping or "did it finish?" guessing. Runs inside a real, manually-logged-in session (no Selenium/CDP) to minimize bot-detection.
- **Conductor is serial** (one focused provider at a time): ChatGPT and Gemini abort their own stream when their tab is backgrounded, so holding focus guarantees complete captures.
- **Known constraints:** Grok hits free-tier rate limits; DeepSeek has no private mode so it deletes all chats before every question (authenticated delete-all API + recorded UI fallback); model labels captured only for some providers.
- **Research phase not started.** Persona-priming infra is wired (`personas.json`, records store `personaId`/`promptSent`) but the study design + analysis/scoring tooling are still TODO.

## 🔬 Open questions

From [FUTURE_WORK.md](FUTURE_WORK.md) — "The key open research/engineering question":

- Does running a provider **backgrounded/throttled change the answer itself** (model routing, truncation, "lite" responses), not just whether capture succeeds? This determines how far the serial conductor can be safely parallelized without biasing the data. FUTURE_WORK proposes a controlled foreground-vs-background, N-reps test per provider.

## 🤖 For agents

Start at [README.md](README.md) → [ff/README.md](ff/README.md) (active build; the "Reloading reliably" section matters). Work the [FUTURE_WORK.md](FUTURE_WORK.md) backlog. No clog/ or TASKS.md in this repo; history lives in `git log`. Never commit `data/` (auth tokens). Shared cross-project concepts live in the vault at `projects/tools`.
