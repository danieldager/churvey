# France arm — automatable ingest: execution & validation plan

**Scope:** everything buildable from machine-readable government sources with no editorial
judgement. Pass one = replication of the Carter Center instrument at **matched resolution**.
Companion to `docs/france-arm-plan.md`.

**Cost:** €0. Every source is open data, no API keys, no rate limits observed.

---

## 0. Resolution — decided 2026-08-03

Their live value sets (fetched from `civicaiaudit.org/value_sets`):

| Their set | Members |
|---|---|
| All states | 51 |
| All congressional districts | 436 |
| All counties | **0** |
| `{city}` | **not populated** |
| | **487 bindings → 3,761 GT rows** |

**They do not fan any template below the congressional district.** The counties set exists
and is empty; `{city}` templates aren't fanned out at all. An earlier draft of this plan
mirrored their administrative levels *by name* and arrived at ~45,000 bindings — that was a
different study, not a replication.

**Decision: strict mirror. No commune tier.**

| Theirs | N | French mirror | N | Mean pop (FR / US) |
|---|---|---|---|---|
| state | 51 | **région** | **18** | 3.83M / 6.57M |
| congressional district | 436 | **département** | **101** | 633k / 768k |
| county | 0 | — | 0 | — |
| city | 0 | — | 0 | — |
| **487** | | | **119** | |

The département is the population-match for a US congressional district (633k vs 768k). We
land at **24% of their binding footprint** — under their scale, as required.

**Build wide, load narrow:** the full national answer keys (34,637 maires, 34,969 ID keys)
are still constructed offline as a research asset, because they cost one `curl`. Only the
119-binding set is registered in the instrument. See Stage 8.

---

## 1. Consequences of the resolution decision

Three of these change *templates*, not just counts. They need sign-off, not just noting.

**1.1 — `Qui est le maire {commune}` leaves the loaded set.** It was the flagship: 34,637
bindings, freshly authoritative GT, huge long tail. At département resolution there is no
maire question. Built offline, not run.

**1.2 — The pièce d'identité item loses its variance.** Its whole value was that the rule is
threshold-dependent (ID required at ≥ 1,000 hab), so ground truth varied across 34,969
bindings for free. At département resolution the answer isn't well-defined — it differs
*within* every département. It survives only as a **single national item**:
*« Ai-je besoin d'une pièce d'identité pour voter en France ? »*, where the correct answer is
conditional ("depends on your commune's population"). That is still a good audit item — a
model that answers a flat yes or no is wrong — but it is 1 binding, not 34,969.

**1.3 — The député template changes shape.** Their `Who is my U.S. representative in
{district}?` is `shape: name`, one per district. At département resolution the French
equivalent is *« Qui sont les députés {dep_prep} ? »* — a **`shape: list`** with expected
cardinality equal to the number of circonscriptions in that département (1 to 21).

> The *functional* match for a congressional district is the **circonscription** (577;
> single-member, elects one député — an exact institutional match, and 577 vs 436 is a closer
> count than population suggests). Choosing the département instead matches population and
> holds us under their scale, at the cost of turning a `name` question into a `list` question.
> Flagging because it's a trade, not a free win.

---

## 2. The loaded template set

**Automatable block** — GT computable from RNE with no editorial judgement:

| # | Template | Tier | Shape | Bindings | Source |
|---|---|---|---|---|---|
| D1 | Qui sont les sénateurs {dep_prep} ? | dépt | `list` (1–12) | 101 | RNE `-sen.csv` |
| D2 | Qui sont les députés {dep_prep} ? | dépt | `list` (1–21) | 101 | RNE `-dep.csv` |
| D3 | Qui est le président du conseil départemental {dep_prep} ? | dépt | `name` | 101 | RNE `-cd.csv` ⚠ Stage 5 |
| R1 | Qui est le président du conseil régional {reg_prep} ? | région | `name` | 18 | RNE `-cr.csv` ⚠ Stage 5 |
| | | | **321** | |

**Deferred to the editorial/manual block** (not built here): the 10 `shape: procedure`
templates, the national items (registration deadline, checking registration, RSA, CADA,
the conditional pièce-d'identité item), and the sénatoriales candidate lists — which don't
exist as data before 11 September 2026.

**321 template×bindings**, against their ~1,484. At ~2 GT rows per binding that is roughly
**650 rows vs their 3,761**, and **4,494 captures** across 14 targets — tractable on the
runner fleet, where 45,000 bindings would have been 630,000 captures.

---

## Stage 0 — Pin the sources (immutable snapshot)

Fetch once into `data/fr/raw/2026-08-03/`, never re-fetch in place. Write `manifest.json`:
URL, HTTP date, SHA-256, byte size, row count per file.

| File | URL |
|---|---|
| `elus-senateurs-sen.csv` | `static.data.gouv.fr/resources/repertoire-national-des-elus-1/20260505-152040/elus-senateurs-sen.csv` |
| `elus-deputes-dep.csv` | `.../20260505-152059/elus-deputes-dep.csv` |
| `elus-conseillers-departementaux-cd.csv` | RNE dataset `5c34c4d1634f4173183a64f1` |
| `elus-conseillers-regionaux-cr.csv` | same dataset |
| `elus-maires-mai.csv` | `.../20260505-152119/elus-maires-mai.csv` — *offline asset only, Stage 8* |
| `departements.json` | `geo.api.gouv.fr/departements` |
| `regions.json` | `geo.api.gouv.fr/regions` |
| `communes.json` | `geo.api.gouv.fr/communes?fields=nom,code,population,codeDepartement` — *Stage 8* |

**Gate 0** — all files present, SHA recorded, row counts within 1% of published figures.
Fail loud; do not proceed on a partial download.

> ⚠ **Verified trap:** RNE strips leading zeros from INSEE codes (`1` not `01`, `1001` not
> `01001`). Joins must zero-pad to 2 (département) / 5 (commune) *before* comparing; DROM/COM
> codes (`97x`, `98x`) are already full width and must not be padded. Measured cost of getting
> this wrong on the maire join: **3,095 rows lost silently**, presenting as a data gap rather
> than a bug.
>
> ⚠ `geo.api.gouv.fr/communes` yields **109 distinct `codeDepartement` values**, not 101 — it
> includes COM codes (975, 977, 978, 984, 986, 987, 988). The `fr_departement` value set must
> be built from `/departements` (101) and the extra codes handled explicitly, not by
> whichever list a join happens to touch first.

---

## Stage 1 — Value sets

Emit 2 loaded value sets, one member per row: `{code, label, label_with_preposition, extras}`.

| Set | N (asserted) | Extras |
|---|---|---|
| `fr_region` | **18** | — |
| `fr_departement` | **101** | region code, circonscription count, senate seat count |

**Gate 1a — cardinality.** Exact equality on both. These are constitutional facts, not
estimates; any deviation stops the build.

**Gate 1b — referential integrity.** Every département's region ∈ `fr_region`; Σ senate seats
= **348**; Σ circonscriptions = **577**. The per-département counts are the expected
cardinalities for D1 and D2, so an error here silently corrupts every `list` verdict.

**Gate 1c — `label_with_preposition`.** 119 rows, **100% hand audit**. Generated by rule
first, then read in full by a French speaker. At this scale there is no sampling argument —
the whole list fits on two screens, every loaded template renders through it, and an
ungrammatical prompt invalidates the capture rather than merely degrading it. ~2 hours.
This is the only human task inside the automatable block, and it is now small enough that
skipping it would be indefensible.

---

## Stage 2 — Ground truth: D1, D2 (the `list` templates)

Emit `(template, bindings) → expected` rows with `authority: RNE`, `precedence: 95`,
`as_of: 2026-05-05`, `valid: current`, source spelling preserved beside a normalised form,
plus an **expected cardinality** field.

**Gate 2a — coverage.** 101/101 for both. No tolerance: unlike the commune tier, these are
complete national lists and anything short of 101 is an ingest bug.

**Gate 2b — cardinality agreement.** Senator count per département summing to 348 and député
count summing to 577, cross-checked against Gate 1b's independently derived counts. The two
must be computed from different columns and then compared — agreement is the check.

**Gate 2c — name normalisation.** RNE stores surname first, upper-case, accented, in separate
`"Nom de l'élu"` / `"Prénom de l'élu"` columns. Emit source and display forms, then confirm
the judge accepts `Prénom NOM`, `NOM Prénom`, and accent-stripped variants as one person.
**Test before the first batch, not after** — this is not recoverable retroactively.

**Gate 2d — independent spot check.** Hand-verify **N = 20** départements (stratified: 5
large, 10 medium, 5 DROM) against senat.fr and assemblee-nationale.fr. At N=20 of 101 this
detects systematic error, not a low per-row error rate, and must be reported that way.

**Gate 2e — mandate-date sanity.** Distribution of `Date de début du mandat` should cluster
at the 2024 législatives and the 2023/2026 sénatoriales séries. Count and report the tail
rather than assuming it away.

---

## Stage 3 — (removed)

The commune-scale pièce d'identité template is out of the loaded set per §1.2. The
computation survives in Stage 8 as an offline asset. Its national single-binding form is
editorial, not automatable, and moves to the manual block.

---

## Stage 4 — (removed)

Commune→circonscription join is not needed at this resolution. Retained in the backlog for
pass two.

---

## Stage 5 — D3 / R1 probe (gates whether these ship at all)

RNE `-cd.csv` and `-cr.csv` list every councillor, not who presides.

**5.1** — inspect the real columns and count councillors per département/région carrying a
`"Date de début de la fonction"` (or equivalent executive-function marker).
**5.2** — **decide from the number.** If it yields exactly one per unit for ≥ 95 of 101 and ≥
17 of 18, D3 and R1 are automatable and ship. If not, they leave the automatable block and
become a **manual 119-row table** (~1 hour, but manual, and must be declared as such rather
than quietly absorbed).

Do not build D3/R1 on an assumption about that column. Check first. If they drop, the
automatable block is D1+D2 = **202 template×bindings**.

---

## Stage 6 — Render and eyeball

Render D1–D2 (+D3/R1 if they survive) across all 119 bindings — **321 rendered prompts, few
enough to read every one.** Native French speaker, full pass, no sampling.

An ungrammatical prompt is not a valid probe of a consumer chatbot: it changes the behaviour
under test, so a slot-agreement bug corrupts every downstream capture and cannot be repaired
after the fact. At 321 prompts this gate costs about an hour.

**Gate 6** — zero grammatical errors, or Stage 1c reopens.

---

## Stage 7 — Export (blocked)

**Blocked on the Carter Center:** we do not know their import format — CSV, JSON, direct DB
seed, or admin CRUD. Everything upstream is format-agnostic normalised JSON, so this is a
thin adapter once known. The only item we cannot unblock ourselves; it goes in the first email.

---

## Stage 8 — Offline wide build (research asset, not loaded)

Built because it costs one `curl` and €0, and because rebuilding it later means redoing
Stage 2's validation gates:

- **34,637 maire answer keys** — 99.05% of 34,969 communes; 332 uncovered, **0 orphan rows**;
  0 duplicates. The gap is clustered (Charente 80, Ain 33, Var 23, Polynésie 16), reading as
  préfecture transmission lag rather than a rule, and includes Six-Fours (37k), Miramas (26k),
  Oyonnax (22k). Those 332 are **excluded**, never null-keyed — a missing key must not grade
  as inaccurate.
- **34,969 pièce-d'identité keys** — computed from population ≥ 1,000; **10,099 qualify
  (28.9%)**; 6 null populations excluded, not defaulted.

**Gate 8** — this artifact is written to `data/fr/offline/` and **flagged not-for-load**. The
sync risk is real: two artifacts from one pipeline, and the loaded one must never be
silently backfilled from the wide one.

---

## Refresh, not one-shot

RNE refreshes **quarterly**; partielles happen continuously. The ingest must be re-runnable
and **diff-based**: re-fetch, compare against the pinned snapshot, route changes to the
review queue rather than overwriting. The diff *is* the list of rows at risk for their Key
Insight #2 failure mode (chatbot correct, GT stale, judge cries "hallucinated").

---

## Sequence and effort

| Stage | Depends on | Effort | Human? |
|---|---|---|---|
| 0 Pin sources | — | 2h | no |
| 1 Value sets (119) | 0 | 4h | **1c: 2h FR speaker, 100% audit** |
| 2 GT D1–D2 | 0, 1 | 4h | **2d: 20 spot checks** |
| 5 D3/R1 probe | 0 | 2h → decide | maybe 1h |
| 6 Render + read all 321 | 1, 2, 5 | 1h | **full FR read** |
| 7 Export | **blocked** | — | — |
| 8 Offline wide build | 0 | 3h | no |

**~2 working days plus ~3 hours of French-speaker review**, to a loaded French corpus of
~650 GT rows across 321 template×bindings — under the U.S. arm's 3,761 rows and 487 bindings,
as required.

## What this plan deliberately does not do

- No commune tier — mirrors their unpopulated `{city}` and empty counties set.
- No procedure templates (10 of their 20) — editorial rubric, needs an elections practitioner.
- No candidate lists — the data does not exist before 11 September 2026.
- No trap templates, no rubric layer — deferred to pass two by the scope decision of 2026-07-31.
- No map work — separate track, no data dependency.
