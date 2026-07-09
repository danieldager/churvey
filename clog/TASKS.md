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

## Study design (methodology track — parked while piloting)
- [ ] Resolve method open sub-decisions (§10): realism-subset sourcing; Fv inclusion; Phase-3 robustness; per-cell source caps

## Notes
- Scope decision: include chatbot-accuracy-on-civic-questions precedents; exclude ideological-lean/political-bias measurement literature.
- Source breadth: academic + policy/think-tank + journalism + eval benchmarks.
- Settled design forks: hybrid sampling (stratified core + firewalled realism subset); hybrid-tagged cross-language; ~120 core (5/cell) + ~24 realism.
- Precedents to improve on: AIDP (DB-source questions, add evidence validity + cross-language, fix no-IRR/no-blinding/single-run); AIDAS (borrow framing generator, drop narrative-lean scorer).
