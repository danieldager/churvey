# ROADMAP

Where we are going and what is queued. Detail lives in `clog/TASKS.md` and the daily logs;
this file is the ordering and the blocking relationships.
`- [x]` done · `- [ ]` open · `→` in progress.

---

## France arm — procedural questions for the présidentielle 2027

**DIRECTION CHANGED 2026-08-04.** Daniel's boss wants the France arm to **reuse the
procedural questions from the Michigan pilot**, translated and adapted to France and aimed at
the **présidentielle of 18 April / 2 May 2027**. That is a different instrument from what was
built. The Michigan pilot asks a voter's own questions ("where do I register", "what ID do I
need") and grades them against a points rubric. The France arm as built asks factual
per-département questions ("who represents l'Ain in the Senate") and grades them by exact
name match. Almost nothing carries over except the method and the tooling.

### STEP 1 — decide which questions to ask. Reshaped twice on 2026-08-04.

- [x] Read the 15 pilot questions and the 16-topic long bank
- [x] Classify all 15 by French referent, scope and sourceability
- [x] **Ported set rejected as US-centric** (Daniel, 2026-08-04). Porting Michigan's questions
      imports Michigan's assumptions about what confuses a voter. Several things a French
      voter is actually confused by have no US analogue, so porting could never surface them
- [x] **Shape changed: every question must have one short checkable answer** (Daniel,
      2026-08-04). No compound questions, no points rubric, nothing needing a paragraph of
      model output. This moves the arm away from `analysis/procedural_rubrics.md` and back
      toward the parked roster instrument's match-the-answer grading, which already exists
      in `france/`. **Cost: cross-arm comparison with Michigan weakens.** Live tension with
      the boss's original "reuse the pilot questions" instruction
- [x] 32 atomic candidates drafted, A1–A32, in `analysis/france_questions_draft.json`.
      Reasoning in `docs/france-procedural-questions.md`. 10 yes/no, 11 single-value,
      9 one-clause, 2 needing rewrite (A19, A32)
- [x] FR4 and FR5 dropped by Daniel under the trap-questions rule. 16.2–16.8 skipped
- [x] **Daniel's selection.** National block asked once per surface: **A1, A3, A6, A8, A22**
      (A23 and A27 dropped 2026-08-05 for sharing the answer "Le Conseil constitutionnel"). Commune block asked per surface per commune: **A4, A11**, plus
      **where to register** and **where to vote**. A4 and A11 were confined to the commune
      block and their national versions dropped
- [x] **Locality tier resolved: commune, sampled not enumerated. N=200** (Daniel), drawn with
      **geographic spread** so the front-end map is not empty. Rule written before the draw,
      seeded and reproducible: `france/sample_communes.py`, seed 20270418. Frame is
      metropolitan + 5 DROM = **34 875 communes over 101 départements**. Snapshot pinned at
      `data/fr/raw/2026-08-04/geo_communes.json` sha256 `8b603792…`. Sample in
      `data/fr/sample/communes_sample_draft.json`
- [x] Coverage achieved: **101/101 départements, 18/18 régions, 83 of the ~90 one-degree cells
      metropolitan France spans.** Method is farthest-point spatial spread within size strata
      plus a département-coverage repair pass, since pure distance-optimisation skips
      départements that are small in area but dense in people
- [ ] **The sample is NOT proportionally representative** and must not be reported as if it
      were. 40% is under 1 000 hab against 71% of the frame, and DROM are 5% against 0.37%.
      Both deliberate, for threshold discrimination and map coverage. Any headline needs
      reweighting to the frame

### Locality block — BUILT 2026-08-04. `data/fr/answers/locality_answers.json`

Three questions, approved by Daniel. Builder `france/build_locality_answers.py`, gated.
**642 answerable locality prompts + 5 national = 647 per surface.**

- [x] **L_ID** — Faut-il presenter une piece d'identite pour voter a {COMMUNE} ?
      **200/200.** Oui 121, Non 79. 12 rows within 100 hab of the 1 000 threshold, flagged
- [x] **L_MAIRIE** — Ou s'inscrire sur les listes electorales ? **242/242.**
      197 communes + **45 arrondissements**, because Paris, Lyon and Marseille register at the
      mairie d'arrondissement. Asked per arrondissement (Paris 20, Lyon 9, Marseille 16), not
      per mairie, so it also tests the merges: **Paris 1er–4e all answer Paris Centre** (merged
      2020) and **each Marseille secteur covers two arrondissements**
- [x] **L_MAIRE** — Qui est le maire de {COMMUNE} ? **200/200 by construction.** RNE refreshed
      2026-05-05, mandates start 2026-03-22, so it is a **recency probe**: Paris is Emmanuel
      Grégoire, Grenoble is Laurence Ruffin. Models trained before March 2026 answer Hidalgo
      and Piolle
- [x] **Frame eligibility applied BEFORE the draw** (Daniel, rather than swapping communes out
      afterwards). A commune enters the frame only if **every** question can be answered from
      an official source. Excluded, **324 of 34 875 (0.93%)**, frame now **34 551**:
      **305** with no RNE maire row (conseil municipal recorded, maire function not);
      **7** with no lannuaire mairie record at all;
      **12** whose mairie does not resolve to one record — 3 communes nouvelles whose name
      concatenates the former communes so neither mairie matches (Meaulne-Vitray,
      Luitré-Dompierre, Le Rousset-Marizy) and 9 for which lannuaire lists only an annexe or
      a mairie déléguée. Coverage held at **101/101 départements, 18/18 régions, 83 of ~90
      cells**. Stated bias: slightly against communes nouvelles and places with poor RNE
      data entry
- [x] Whole-key value check re-run: 8 lannuaire label differences (all Cedex suffixes or postal
      variants), 1 RNE spelling variant, **0 wrong-commune joins**, 0 answers failing to name
      their own commune or city
- [x] **Zero exceptions.** Every one of the 642 rows has an answer from an official source.
      The Le Rousset-Marizy siège question dissolved: it is outside the frame
- [x] **Duplicate audit, 2026-08-04.** Found and fixed a real defect: **Saint-Denis (93) and
      Saint-Denis (974) were both in the sample**, producing identical question text with
      different answers. More broadly **16 of the 200 share their name with another French
      commune** (Saint-Julien 6 ways, Thil 5, L'Épine 4, Montreuil, Anglès, Saint-Sylvain…).
      Those 16 now carry the département in parentheses (Daniel):
      `J'habite a Saint-Denis (Seine-Saint-Denis).` The other 184 stay phrased as a voter
      would actually ask. **48 rows disambiguated (16 per question type)**
- [x] The parenthetical needs only the bare département name, so it **avoids
      `france/prepositions.py` entirely** — including the unaudited `DEPARTEMENT_LOC`
      (`LOC_AUDITED = False`) and the unreviewed rows in `DEPARTEMENT_ARTICLE`. Names from
      `geo.api.gouv.fr/departements`, pinned at `data/fr/raw/2026-08-04/geo_departements.json`
      sha256 `f793a3df…`, 101 rows
- [x] Final audit clean: **0 duplicate INSEE codes, 0 duplicate item ids, 0 duplicate question
      texts anywhere in the 642**, 200 distinct communes, 45 distinct arrondissements

### Not in the locality block, and why

- [ ] **Closing hours.** The best per-commune question. Blocked: the décret de convocation
      (~Feb 2027) and the 101 arrêtés préfectoraux (~Mar/Apr 2027) do not exist yet.
      **Revisit spring 2027**
- **Where to vote.** Depends on the voter's street address, not the commune. ~70 000 bureaux
- **Registration deadline.** Answer is national, so it lives in the national block as A6
- **2022 results by commune.** Built and working (200/200, winners spread Le Pen 83 /
  Macron 80 / Mélenchon 36 / Jadot 1) but **rejected 2026-08-04 as backward-looking**
- **Procuration office.** lannuaire has 3 065 gendarmeries but none list the communes they
  serve. Any mapping would be our inference, not an official answer
- **Mairie opening hours, mairie contact.** Judged too weak

### Two join traps found the hard way, both reported clean counts while being wrong

- The results file codes DROM as ZA/ZB/ZC/ZD/ZM **and** carries **ZZ, the consular/foreign
  bureau list**, which naively maps into the same 97x range. Terre-de-Bas silently took
  Marrakech's results, Fort-de-France took Tel Aviv's, Grand'Rivière took Tirana's
- The **RNE stores commune codes unpadded for départements 01-09**, so 01001 appears as 1001.
  Cost 14 communes silently
- Both are now asserted against in the builder. **Third and fourth time in two days that a
  structural check passed while values were wrong**

### STEP 2 — answer key. **The rubric port is OFF.**

Superseded 2026-08-04 by the simple-checkable-answer rule. `analysis/procedural_rubrics.md`
is no longer the method for this arm. Grading is a match against a short expected answer,
the same shape the roster instrument already uses.

- [ ] One short expected answer per question, plus accepted variants. 13 of the 32 are already
      sourced from service-public pages read 2026-08-04; the other 19 are Claude's knowledge
      and are marked `"sourced": "no"` in the JSON
- [ ] French primary sources replace michigan.gov/vote and MCL: **service-public.gouv.fr**
      (reachable, page IDs known), the **Code électoral** on Légifrance (reachable, navigate
      from `LEGITEXT000006070239`), **conseil-constitutionnel.fr** (loads, but its nav exposes
      no présidentielle section — needs a URL from Daniel for A22/A23/A24/A27),
      **elections.interieur.gouv.fr** (403 bot block, a URL will not fix it)
- [ ] Pin every source page into `data/fr/raw/<date>/` with SHA-256 in the manifest before
      writing any answer, same discipline as the roster instrument
- [ ] **Session constraint:** WebSearch budget exhausted, 200/200. WebFetch works, so known
      URLs are reachable but nothing can be found by search

### STEP 3 — extraction, redone

- [ ] The existing `france/` pipeline extracts elected-official rosters. Procedural answers
      are **law and administrative procedure, not rosters**, so `build.py`, `chambers.py`,
      `probe_presidents.py` and the RNE CSVs are mostly irrelevant to the new set
- [ ] What survives and should be reused: the **gate pattern** (build fails, nothing written,
      on a failed assertion), the **pinned-snapshot + SHA-256 manifest** discipline in
      `data/fr/raw/<date>/manifest.json`, `render.py` and the export/audit pair
      (`export_package.py` + `check_export.py`)
- [ ] Most procedural questions are **national, 1 binding**. If any bind per place, the
      grammar tables in `france/prepositions.py` are already signed off and reusable

### What was built and is now parked, not deleted

7 templates · 119 locales · **612 questions · 612 answer keys**, in
`data/fr/export/CAA_france_2026-08-03.json` (496 KB). All gates green, all 40 export checks
pass. €0 spent, all open data. Code in `france/`, data in `data/fr/`.

- [x] Resolution decision: mirror their value sets. 18 régions + 101 départements, no commune
      tier. Population match is the département to a congressional district, 633k vs 768k
- [x] D1/D2 sénateurs and députés, D3/R1 council presidents, S1/S2/S3 senate seats
- [x] Native-speaker sign-off on the 119-row preposition table
- [x] Single-file export + a 40-check audit that reads only the emitted JSON
- [x] Explainer page for Cameron:
      https://claude.ai/code/artifact/c210c006-767d-4a23-8503-f143b77aa786

**Decide before doing anything with it:** does the 612-question set still go to the Carter
Center, or is it shelved? It is finished and correct. The email, memo and methodology were
written around it. Nothing has been sent.

- [ ] If it still ships: propagate 612 / D3 93 / no precedence / no Mayotte into
      `docs/carter-center-memo.md` and `docs/france-methodology.md`, which still say 613 and
      still carry a precedence section. Daniel's email draft says 613 too, but that is his
- [ ] If it is shelved: say so here, and leave the export where it is

### Still true regardless of direction

- [ ] **Their import format** — CSV, JSON, DB seed, admin CRUD? The only thing genuinely
      blocked on Cameron. Our data is format-agnostic JSON; a thin adapter once known
- [ ] **Can value-set members carry arbitrary per-member fields?** French needs
      `label_with_preposition` on the member. If yes it is free, if no it is a migration
- [ ] **A French IP for the runner** would be better than not. Their Insight #3 found four of
      five surfaces answering from the asker's geolocated state. Never measured for French
- [ ] **Add Mistral Le Chat** as a target. Main French consumer surface
- [ ] 45 Loiret: answer is Marc Gaudet, corroborated by fr.wikipedia but undated past 2017.
      Searched 2026-08-04, nothing newer exists. Needs a fresh source, not a re-check
- [ ] 43 Haute-Loire: a 2026 org chart exists, only its index title was read
- [ ] Locative grammar table unsigned (`prepositions.py:LOC_AUDITED = False`), 119 rows.
      No current question uses it. Approval sheet:
      https://claude.ai/code/artifact/7c344508-e42b-4611-afcc-d8522af88cf3

### Ruled out, do not re-tread

- **Primaries as a question.** France has no state-run primaries, but parties have run their
  own (2011, 2016, 2017, 2022). Whether any party runs one for 2027 is unknown. Contested and
  evolving, so it cannot have a stable answer key. Ruled out 2026-08-03, and the pivot does
  not revive it.
- **Trap / adversarial questions.** Dropped 2026-08-03. This project asks what a citizen would
  plausibly ask. The U.S. arm does not build adversarial probes either.
- **Commune tier.** ~34,900 communes, no matching resolution on the U.S. side.
- **Deriving the Senate série from RNE mandate dates.** Measured, does not work: 165 seats
  across 60 départements against the official 178. By-election replacements inherit the série
  but carry a later mandate start. The Sénat's live endpoint carries `serie` directly.
- **nosdeputes.fr as a source.** Its /deputes/json still serves the 2022–2024 legislature,
  dissolved June 2024. It would have "confirmed" our data and looked like a pass.

---

## Other workstreams (untouched this session)

The monthly question aggregator, the Michigan pilot, and the response-analysis pipeline are all
in `clog/TASKS.md` and were not worked on. The France arm has been the whole focus since
2026-07-31.
