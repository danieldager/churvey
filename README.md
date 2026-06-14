# Chat UI Research Probe

**A Firefox extension that asks a fixed question set to multiple AI chat web UIs (ChatGPT, Gemini, Grok, Claude, DeepSeek) in a real logged-in session and captures each response at the network layer — for studying how consumer chat assistants answer political questions as a typical user experiences them (not via the APIs).**

> *Two-line summary for collaborators:* It's a Firefox extension you load into a normal logged-in browser; you pick providers/questions/personas and hit Run, and it automatically asks each question in a fresh private/incognito chat per provider and saves the exact responses (captured from the network stream) as JSONL. It exists because the consumer chat UIs answer differently than the APIs, so we measure the real user-facing behavior.

## Why this design
We deliberately avoid the provider APIs — the goal is to capture what a *typical user* sees in the consumer chat experience (different system prompts, safety layers, model routing, personalization). We also avoid external automation (Selenium/CDP) to minimize bot-detection: the tool runs **inside a real, manually-logged-in Firefox session**. Responses are captured at the **network layer** (`webRequest.filterResponseData`, a Firefox-only capability) rather than scraped from the DOM, which makes capture robust and exact.

## Builds
- **`ff/` — the active build (Firefox MV2).** Network-layer capture + automated asking. **Use this.** See [`ff/README.md`](ff/README.md).
- **`src/` + `manifest.json` (root) — legacy Chrome MV3 build.** The original DOM-scraping version; abandoned because Chrome MV3 can't read response bodies and content-script orchestration proved fragile. Kept for reference.

## Quick start (Firefox build)
1. Firefox → `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** → select `ff/manifest.json`.
2. Log into each provider in that Firefox profile.
3. Click the toolbar icon → choose providers / questions / personas → **Run**.
4. **Export JSONL + summary** → files land in `Downloads/chat-probe/` (symlinked to `data/chat-probe/` here).

Full instructions, architecture, per-provider notes, and troubleshooting are in [`ff/README.md`](ff/README.md). Planned work is in [`FUTURE_WORK.md`](FUTURE_WORK.md).

## Status (2026-06-14)
- **Capture working for all 5 providers**, each in a private/incognito chat, responses saved as JSONL with a per-run summary.
- Conductor runs **serially** (one focused provider at a time) because several providers (ChatGPT, Gemini) abort their own stream when their tab is backgrounded — serial guarantees complete responses.
- **Grok** is subject to free-tier rate limits ("Too many requests").
- **DeepSeek** has no private mode, so it deletes all chats before every question (authenticated API call).

## Data & privacy
- `data/` is **git-ignored**: it holds captured responses **and interaction recordings that contain auth tokens/cookies** — never commit it.
- Use your own/burner accounts; automating chat UIs may conflict with provider Terms of Service. Keep volume low and within your research-ethics scope.
