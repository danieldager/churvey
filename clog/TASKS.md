# Tasks

## Research question selection (study design)
- [x] Literature review: LLMs & misinformation, evidence/citation accuracy, hallucination, current-events/knowledge-cutoff failures, chatbot-accuracy-on-civic-questions precedents (US + France focus) → `docs/lit-review.md`
- [x] Derive question-selection methodology from lit review findings → `docs/question-selection-method.md`
- [x] Deep-dive AIDP primary sources + recover codebook (resolves lit-review Open Q#3)
- [x] Fold in AIDAS framing-variation methodology
- [x] HTML POC explaining the design → `docs/design-poc.html`

## Michigan pilot — ground-truth answer key
- [x] Build ground-truth answer key for all 16 topics → `docs/michigan_answer_key.html` (verbatim quotes + official citations; 85 dated source snapshots in `source_cache/`)
- [x] Jina cache infra + reusable helper (`scripts/fetch_source.sh`)
- [ ] RE-VERIFY volatile items just before the run: candidate rosters (T6), McMorrow/Nesbitt suspensions, sitting SOS (T15.2), updated challenger/poll-watcher manual (T5), early-voting local dates (T10)
- [ ] Pick/combine the ~96 split questions down to the pilot set before running
- [ ] (later) Generalize methodology beyond the pilot: 120-item stratified core + 24 realism subset; France arm

## Response-analysis pipeline (scoring the models' answers)
- [x] Design draft → `docs/response-analysis-pipeline.md` (spec v0.2) + `analysis/sample_responses.jsonl` (labeled fixtures)
- [x] Map the sibling factcheck loop we're adapting (`verify.verify`, `eval/ace.py`, 4-class + Likert)
- [x] Scoring model pivot → points-based per-question rubrics (drop 1–5/4-class/Likert); headline deferred
- [x] Procedural rubrics P1–P8 + graded available fixtures → `analysis/procedural_rubrics.md`
- [x] Sample responses for all 8 procedural questions (P1–P8) authored + hand-graded
- [x] Candidate-position rubrics (16.2–16.8) → `analysis/candidate_rubrics.md`
- [x] Candidate fixtures with citations (16.2/16.3/16.4/16.6/16.7/16.8) → `analysis/sample_responses.jsonl` (14 total)
- [x] Draft LLM grader prompts (procedural + candidate) → `analysis/grader_prompts.md`
- [x] Grader dry-run preview (simulated LLM output over all 14 fixtures) → `docs/grader_preview.html` (published artifact)
- [x] Pick the judge model → **DeepSeek-V4-Flash** on DeepInfra (~$2.03 for ~7,500 calls; matches sibling; use json_schema strict + prompt caching)
- [ ] Decide P5 canonical scoring (rubric 0/5 vs table 1/6 — the "acknowledges EV exists" partial-credit item)
- [x] Validate grader on the 14 synthetic fixtures → 99% item agreement (74/75), 14/14 criticals, thinking mode (`analysis/validate_grader.py`, gold in `analysis/fixtures_gold.json`); verdict scheme now correct/partial/missing/wrong; machine rubrics → `analysis/rubrics.json`
- [ ] Add a 16.5 fixture (immigration); optional
- [ ] Wire the two code-side checks: citation existence (URL resolve) + deep support (scrape/NLI via sibling `_summarise_one`)
- [x] Load the 15 pilot questions into the FF capture tool (popup DEFAULT_QUESTIONS + `analysis/pilot_questions.json`); default reps→10; confirmed round-robin ordering (750 = 15×10×5)
- [ ] (later) Adapt `verify.verify()` for the candidate/residual-claim pass; open decisions: judge model · import-vs-vendor · framing variants

## Pilot run — capture + grading (ACTIVE)
- [x] ChatGPT + Claude capture complete: `data/chat-probe/pilot_full.jsonl` (120 records, 4 reps × 15q × 2 models; ChatGPT delta_encoding + DeepSeek patch-stream parser bugs found & fixed, texts recovered)
- [x] Grade pass 1 (thinking, single pass) → `data/chat-probe/grades_pass1.jsonl` ($0.09): ChatGPT 74% / misinfo 4/60, Claude 72% / misinfo 6/60, zero criticals; audit via `analysis/audit_grades.py`
- [x] Review doc → `docs/grade_review.html` (published claude.ai artifact, all 120 cards)
- [ ] User reviews grade_review.html → note grader disagreements (this is the REAL-data validation; the 99% was synthetic fixtures)
- [x] **Verify P5 F2 rubric criterion** ("assigned early-voting site") against answer key → **CRITERION IS WRONG.** Ann Arbor city voters may use ANY of the 4 city sites (no per-address assignment; "assigned" only applies to the 23 county-coordinated townships). Grader mis-scored P5 both ways: 3 false positives (chatgpt rep2/rep3, claude rep3 flagged wrong for correctly saying "any of 4") AND 3 false negatives (claude rep0/rep1/rep2 hallucinated "3021 Miller Rd Election Center" — a tabulation site, not a casting site — unflagged). See clog 110726.md.
- [x] **Reword P5 F2 + regrade P5** → done. rubrics.json F2 rewritten; P5 regraded via new `analysis/regrade.py P5` → `grades_pass1_v2.jsonl`. Corrected headline: ChatGPT misinfo 7%→3% (4→2/60), Claude 10%→8% (6→5/60); means unchanged (74%/72%); criticals 0. Reusable `regrade.py <qid...>` kept; one-off deleted. See clog 110726.md.
- [x] Set P5 F2 `crit:true` (wrong early-voting site = critical). Refreshed critical_error flags deterministically via new `analysis/set_criticals.py grades_pass1_v2.jsonl` (no re-grade). Now: ChatGPT 1 critical (P5 rep1, county sites for city voter), Claude 3 criticals (P5 rep0/1/2, "3021 Miller Rd" hallucination); audit consistency holds.
- [x] Rebuilt `grade_review.html` from `grades_pass1_v2.jsonl` + republished the artifact in place (same URL 30e523d9, label "pass1_v2 P5-corrected").
- [ ] Resume the 3-provider run (gemini/grok/deepseek, paused at Grok limits, 106/135 ok): load extension build **2026-07-11-e** → Import `data/chat-probe/run_2026-07-11T12-21-35-319Z.run.json` (import opens in a TAB — FF/macOS closes the popup on file dialogs) → Resume missing (29 gaps: 8 gemini, 15 grok, 6 deepseek). NEW: providers run in parallel (one window each); per-provider ⏸/▶ for grok account swaps (resume clears backoff)
- [ ] First parallel run: watch for stream aborts on unfocused windows (tripwire warnings in log) — if a provider misbehaves in parallel mode, special-case it
- [ ] QA the completed 3-provider run (parsers, citations, tripwire warnings)
- [x] Grade Gemini + DeepSeek (resumed run …319Z(1).jsonl, 45/45 each) + merge onto corrected pilot → `grades_4models.jsonl` (210 recs; chatgpt/claude/gemini/deepseek). Via new `analysis/grade_records.py`. Grok excluded (40/45, incomplete).
- [x] 4-model collaborator summary → `docs/pilot_summary.html` (new `build_summary_html.py`), published artifact 9c555eee. Results: Gemini 80% / ChatGPT 74% / Claude 72% / DeepSeek 55% (abstains on candidate Qs → low acc, low misinfo).
- [x] Expanded pilot_summary.html to **3 tabs**: (1) Results — now with per-card proc/cand split; (2) Questions & key — each Q + plain-language correct answer + collapsible rubric; (3) Examples — 1–2 instructive graded answers/question (strong + a revealing error), verdict dots + grader reason. Verified all tabs via headless-FF (per-tab pre-activated variants). Same artifact URL.
- [x] **P3 IS STATELESS — invalid as a Michigan measure** (found by user). As-sent text ("What kinds of ID are accepted at the polls for the August 4 primary…") names no state, sent as a fresh one-shot chat (no context carryover — confirmed: models guessed different states). Models guessed: ChatGPT→Florida (0%×4), DeepSeek→VA/MO (0%), Claude→asked "which state?" (0/20/70/20), Gemini→Michigan (100/100/80). Grading these vs the MI rubric measured the guess + penalized Claude's ideal clarifying behavior. Scope: ONLY P3 (16.2 also cue-less but all 4 correctly inferred the MI Senate race; every other Q names MI/Ann Arbor).
- [x] FIX (user chose "exclude now + re-run later"): P3 held out of ALL accuracy metrics in `build_summary_html.py` (HELD_OUT set) → 14 scored Qs. New headline: ChatGPT 79% / Claude 75% / Gemini 79% / DeepSeek 59%; procedural ~84-89% all; hardest now 16.6/16.2/16.5. P3 kept on Examples tab reframed as a prompt-ambiguity illustration (4 mini-cards showing each model's state guess), caveated on Questions&key, explained in "how to read". Artifact 9c555eee updated in place.
- [x] ~~Re-run P3 with the state named~~ → SUPERSEDED: user chose to **drop P3 entirely** (question set being revised next run anyway). P3 stays HELD_OUT/illustrative in the summary; not re-captured. Resume file rebuilt to 14 Qs.
- [ ] METHODOLOGY: audit every question set for a self-contained jurisdiction cue before running (questions are sent as independent one-shot chats — no context carryover).
- [ ] **Resume gemini/grok/deepseek to 56 each** (4 reps × 14 Qs — P3 DROPPED per user): import `data/chat-probe/resume_to56.run.json` → Resume missing (asks 47: gemini rep3 ×14, deepseek rep3 ×14, grok rep2's 16.4-16.8 + rep3 = 19). 56 = chatgpt/claude's non-P3 count, so all 4 symmetric. Then export, grade via `grade_records.py … --merge grades_4models.jsonl`, rebuild summary.
- [x] Cleaned `data/chat-probe/`: kept 4 essentials (resume_to60.run.json, pilot_full.jsonl, run_…319Z(1).jsonl, grades_4models.jsonl); archived 69 other files → `_archive_pre60_2026-07-12.tgz` (recoverable). 39M→7M.
- [ ] Decide the headline-aggregation formula
- [ ] Optional: 3-pass majority-vote grading to firm the numbers
- [ ] Boss email: use the honest rewrite draft (synthetic-fixture validation stated plainly)
- [ ] Popup UI: awaiting user feedback on v2 macOS redesign — iterate via `ff/dev/shoot.sh` (headless FF screenshots; no Node on this machine)

## Grader / capture bugs found 14 Jul (fixed, but note for future runs)
- [x] **DeepInfra `response_format: json_schema` CORRUPTS the judge in reasoning mode.** It isn't enforced, and the model copies the JSON-Schema's own `items.items` nesting into its output → unbalanced JSON. Measured 1/6 vs **6/6** clean parses with it removed (68/87 records had failed). Removed from `grade_pilot.py` (do NOT re-add). Also added tolerant `parse_grade()` (strips fences, unwraps double-nested items, `strict=False` for control chars).
- [x] `grade_records.py --only-new` treated `grade: null` rows as done → would silently leave failures ungraded forever. Now only non-null grades count as done.
- [x] **ff/ grok parser leaked `<grok:render …>` citation-widget markup** into responseText (36% of grok's text; all 59/59 records). Root cause: `parseGrok` only stripped `<xai:tool_usage_card>` on the token-joined *fallback* path — the `modelResponse.message` path (which almost always wins) returned the message unstripped. FIXED: new `stripGrokMarkup()` applied to BOTH paths (BUILD 2026-07-14-a). Validated against all 59 real captures — reproduces the cleaned text exactly, 0 markup surviving. Data already cleaned post-hoc (originals in `responseTextRaw` + `.jsonl.bak`).
- [x] Regraded all 297 under ONE judge/day/config on cleaned text → `grades_5models_v2.jsonl` (297/297, 0 retries). Grok 94% / Gemini 80% / ChatGPT 79% / Claude 74% / DeepSeek 54%. Deltas vs old ≤1.3pt → Grok's 94% is REAL. Canonical grades file.

## Study design (methodology track — parked while piloting)
- [ ] Resolve method open sub-decisions (§10): realism-subset sourcing; Fv inclusion; Phase-3 robustness; per-cell source caps

## Notes
- Scope decision: include chatbot-accuracy-on-civic-questions precedents; exclude ideological-lean/political-bias measurement literature.
- Source breadth: academic + policy/think-tank + journalism + eval benchmarks.
- Settled design forks: hybrid sampling (stratified core + firewalled realism subset); hybrid-tagged cross-language; ~120 core (5/cell) + ~24 realism.
- Precedents to improve on: AIDP (DB-source questions, add evidence validity + cross-language, fix no-IRR/no-blinding/single-run); AIDAS (borrow framing generator, drop narrative-lean scorer).
