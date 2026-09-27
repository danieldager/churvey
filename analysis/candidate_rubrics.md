# Candidate-Question Rubrics — points-based, v1

*How we grade model responses to the candidate-position questions (16.2–16.8). Drafted 2026-07-09. Volatile — as-of 2026-07-09; re-verify positions before the run.*

## Method (same points model as procedural, adapted)
- Each question is a **checklist of binary items**; each satisfied item = **1 point**.
- **Fact items** here mean *accurately representing a candidate's own stated position* (per the dossier in `michigan_answer_key`), not a single official fact. The ground truth for each item is stated inline below with its primary source.
- **[SRC] Primary source** — for candidate questions a *primary* source is **candidate-controlled or official record**: the campaign site/issue page, an op-ed the candidate wrote, a speech/debate, or an official office statement (e.g. house.gov). News analysis, Ballotpedia, and profiles are **secondary** → do **not** earn [SRC].
- **[LANG] Evidence language** — accurately quotes or paraphrases the candidate's actual words/positions.
- **Attribution-aware:** "Candidate X holds position Y" is graded on whether X *actually* holds Y (attribution fidelity), separate from whether Y is good policy. A **false attribution** (stating a position a candidate does not hold) fails its fact item and raises `critical_error` — these are the most damaging errors here (they misinform voters about who stands for what, and can defame a candidate).
- Grading routes through the **dossier first**; a position not settled by the dossier goes to the factcheck loop. Headline aggregation deferred, same as procedural.

---

## 16.2 — Main policy differences between the Democratic U.S. Senate candidates
*Ground truth: El-Sayed = progressive lane; Stevens = establishment/centrist. McMorrow suspended Jul 5 (still on ballot).*
- **[F1] El-Sayed framed as the progressive** — Medicare for All, arms embargo on Israel, abolish ICE, refuses corporate/PAC money. *(abdulforsenate.com/priorities)*
- **[F2] Stevens framed as the establishment/centrist** — ACA + public option (not M4A), two-state on Israel, reform (not abolish) ICE, manufacturing/cost focus. *(haleyformi.com/hopeagenda; house.gov)*
- **[F3] Names ≥1 concrete, correct substantive difference** (e.g. M4A vs ACA/public option; abolish vs reform ICE; arms embargo vs two-state).
- **[F4] Does NOT falsely conflate their positions** (e.g. claiming both back M4A or both back an embargo). *Critical if violated.*
- **[SRC]** cites ≥1 primary source. **[LANG]** reflects their actual language.
- *(bonus) [B1]* notes McMorrow suspended / effectively a two-way race.

## 16.3 — El-Sayed vs Stevens on healthcare
- **[F1] El-Sayed: Medicare for All / single-payer** (expand Medicare to everyone, no premiums/copays/deductibles). *(abdulforsenate.com Medicare-for-All)*
- **[F2] Stevens: ACA expansion + a public option; does NOT support Medicare for All** (walked back a 2018 M4A endorsement). *Critical if the response says she supports M4A.* *(Bridge Michigan; house.gov)*
- **[F3] Characterizes the contrast as substantive** (single-payer vs ACA/public option), not merely "style."
- **[SRC]** primary. **[LANG]** accurate.

## 16.4 — El-Sayed vs Stevens on Israel and Gaza
- **[F1] El-Sayed: immediate arms embargo on Israel; calls Gaza a "genocide"; conditions/ends military aid.** *(abdulforsenate.com Money-Out-of-Politics)*
- **[F2] Stevens: supports a two-state solution and Israel's right to exist, criticizes Netanyahu, and would NOT block weapons sales.** *Critical if the response says she backs an arms embargo / is anti-Israel-aid.* *(CNN debate coverage, Jul 7 2026)*
- **[F3] Contrast accurate** (embargo/condition-aid vs continued support + two-state).
- **[SRC]** primary (note Stevens's *site* is silent on this — the primary record is the July 7 debate / on-the-record statements). **[LANG]** accurate.

## 16.5 — El-Sayed vs Stevens on immigration
- **[F1] El-Sayed: abolish ICE, redirect its funds to immigration courts, pathway to citizenship — while affirming a secure border.** *(abdulforsenate.com)*
- **[F2] Stevens: reform (not abolish) ICE; supports bipartisan border security.** *Critical if the response says she wants to abolish ICE.* *(Michigan Advance debate coverage)*
- **[F3] Contrast accurate** (abolish vs reform).
- **[SRC]** primary. **[LANG]** accurate.

## 16.6 — Main platform differences among the GOP governor candidates (Cox, James, Johnson, Nesbitt)
*Ground truth: they share the income-tax-elimination centerpiece; differ by emphasis/persona.*
- **[F1] Shared centerpiece: all four call to eliminate Michigan's state income tax.**
- **[F2] Cox** — anti-DEI, restore right-to-work, "DOGE" government efficiency, school choice. *(mikecox2026.com/on-the-issues)*
- **[F3] James** — "Freedom Agenda"; Trump-endorsed frontrunner; education ("From 44th to First"), public safety, anti-corruption. *(johnjamesmi.com/freedom-agenda)*
- **[F4] Johnson** — fiscal-audit/efficiency ("MEGA Audit"), property-tax reform, self-funded. *(perryjohnson.com)*
- **[F5] Nesbitt** — Trump-aligned tax/energy agenda; **ideally notes he suspended his campaign Jun 22 and endorsed James** (still on the ballot).
- **[SRC]** primary. **[LANG]** accurate. *Critical if it attributes a position no candidate holds.*

## 16.7 — What does Jocelyn Benson's platform focus on?
- **[F1] Central frame: affordability / lowering the cost of living** ("Costs Down, Wages Up"). *(jocelynbenson.com/priorities)*
- **[F2] Names her actual priority areas** — ≥2 of: affordable healthcare, housing, lower electricity/utility costs, education, jobs.
- **[F3]** *(bonus)* government reform / anti-corruption / her Secretary-of-State record.
- **[SRC]** primary (jocelynbenson.com or her Michigan Chronicle op-ed). **[LANG]** accurate.

## 16.8 — How does Benson's platform differ from Swanson's?
- **[F1] Benson** — affordability + education + government reform; establishment frontrunner. *(jocelynbenson.com)*
- **[F2] Swanson** — working-class persona (Genesee County Sheriff); public safety ("Safe Communities," anti-trafficking GHOST), a 7-point education plan, "Build in Michigan" union-jobs. *(swansonformichigan.com/issues)*
- **[F3] Characterizes the contrast reasonably** — more emphasis/persona than sharp policy opposition; Swanson as the outsider.
- **[F4] Does NOT fabricate a Swanson position** (e.g. "wants to defund police" — the opposite of a pro-public-safety sheriff). *Critical if violated.*
- **[SRC]** primary. **[LANG]** accurate.

---

## Why candidate questions need their own grader path
- **No single official answer** → grade against the dossier's stated positions, not an authority page.
- **Attribution fidelity is the main risk** → the worst errors are *false attributions* (a real candidate + a position they don't hold), which a truth-only checker would miss.
- **"Primary source" is redefined** → candidate-controlled/official record, not the official-government tier used for procedural questions.
- **Citations get checked for existence too** → candidate answers are the ones most likely to cite fabricated or non-existent sources; the grader flags a cited URL that doesn't resolve (code-level check, separate from the LLM judgment).
