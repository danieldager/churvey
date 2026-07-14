# Chat UI Research Probe — Hub

> Two halves: a **Firefox extension** that asks a fixed question set to 5 consumer AI chat UIs (ChatGPT, Claude, Gemini, Grok, DeepSeek) in a real logged-in session and captures each answer at the network layer — and a **grading pipeline** that scores those answers against an official ground-truth answer key. First study: the **Michigan Aug 4, 2026 primary**. · Status: **5-model pilot complete and graded** (350 answers); report published. · Refresh with `/hub`.

## 🧭 Navigate

| Concern | Where |
|---|---|
| Project guide / why this design | [README.md](README.md) |
| **Harvest** — capture tool (Firefox MV2): architecture, per-provider notes, troubleshooting | [ff/README.md](ff/README.md) |
| **Grade** — analysis pipeline (grading, regrading, report build) | [analysis/](analysis/) |
| Machine-readable rubrics (one per question) | [analysis/rubrics.json](analysis/rubrics.json) |
| The pilot questions as sent | [analysis/pilot_questions.json](analysis/pilot_questions.json) |
| Ground-truth answer key (Michigan) | [docs/michigan_answer_key.html](docs/michigan_answer_key.html) · 102 dated snapshots in `source_cache/` |
| **Report** — 5-model pilot results (3 tabs) | [docs/pilot_summary.html](docs/pilot_summary.html) |
| Study design / method | [docs/question-selection-method.md](docs/question-selection-method.md) · [docs/response-analysis-pipeline.md](docs/response-analysis-pipeline.md) · [docs/lit-review.md](docs/lit-review.md) |
| Backlog (read this first) | [clog/TASKS.md](clog/TASKS.md) |
| History (daily logs) | [clog/](clog/) — latest [120726.md](clog/120726.md) |
| Captured data + grades | `data/` (git-ignored symlink → iCloud devsync; **contains auth tokens — never commit**) |
| Legacy Chrome MV3 build | `src/` + root `manifest.json` — abandoned (MV3 can't read response bodies), reference only |
| Cross-project knowledge | vault → projects/tools |

## 📌 Status at a glance

- **Pipeline is end-to-end:** harvest (`ff/`) → grade (`analysis/grade_records.py`) → report (`analysis/build_summary_html.py` → `docs/pilot_summary.html`). Grades live in `data/chat-probe/grades_5models_v3.jsonl`.
- **Michigan pilot complete:** 5 models × 14 questions × 5 reps = **350 graded answers**, all judged in one batch.
  **Grok 94% · Gemini 81% · ChatGPT 80% · Claude 75% · DeepSeek 53%.**
- **Read the ranking carefully.** Mean accuracy measures *completeness*, not truthfulness. Grok leads because it writes ~5× more and searches harder, satisfying more rubric checks — but **ChatGPT makes the fewest false claims** (1/70). DeepSeek's low score is *abstention*, not error (it declines the candidate questions rather than guess).
- **Judge = DeepSeek-V4-Flash** (DeepInfra, `reasoning_effort: high`). Two hard-won rules: **never send `response_format: json_schema`** (unenforced in reasoning mode, and the model copies the schema's own nesting into its output → unparseable JSON), and **grade a dataset in ONE batch** — a hosted judge can drift between runs (proved: identical records + config graded fine on Jul 10, then failed 0/6 on Jul 14).
- **Known-bad — Gemini's numbers are inflated.** Its driver never started a new chat, so every question ran in one growing conversation and saw the previous Q&As. Fixed in **BUILD 2026-07-14-b**; the existing Gemini records need a re-run before that number is trustworthy.
- **P3 (voter ID) dropped from the study** — it was sent without naming the state, so each model answered about a different one (ChatGPT→Florida, Grok→Kansas, Gemini→Michigan). Questions are sent as independent one-shot chats with **no context carryover**, so every question needs a self-contained jurisdiction cue.

## 🔬 Open questions

From [clog/TASKS.md](clog/TASKS.md):

- **Re-run Gemini** on BUILD 2026-07-14-b to replace the context-contaminated set.
- **Does the rubric reward verbosity?** Grok's 94% is coverage-driven. Worth stating plainly, or re-weighting, before anyone reads it as "most truthful".
- **Misinfo counts are noisy** (small-n, single pass — a re-grade moved DeepSeek 2→6). A 3-pass majority vote would firm them up; the means are stable (≤1.7pt).
- **Code-side citation checks** not yet wired: URL existence + deep support (scrape/NLI).
- Does backgrounding/throttling a provider change the *answer content* (not just capture)? — gates parallelizing the conductor ([FUTURE_WORK.md](FUTURE_WORK.md)).

## 🤖 For agents

Read [clog/TASKS.md](clog/TASKS.md) first, then this hub. Capture lives in [ff/README.md](ff/README.md) (load via `about:debugging` → `ff/manifest.json`; **check the BUILD stamp** in `ff/src/shared/namespace.js`). Grading lives in `analysis/`: `grade_records.py` grades any capture file (`--only-new`, `--skip-questions`), `regrade.py` re-grades questions after a rubric fix, `set_criticals.py` recomputes critical flags with no LLM call. Log significant work to `clog/DDMMYY.md`. **Never commit `data/`** (auth tokens). Cross-project concepts live in the vault at `projects/tools`.
