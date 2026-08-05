# How the French questions and answer keys were built

**Purpose:** enough detail to rebuild this corpus from nothing, or to update it, without
talking to whoever made it. Every number here is reproducible from the code in `france/`.

**State at 2026-08-03:** 7 templates · 119 locales · **613 questions, 613 answer keys, 0 gaps.**

---

## 1. What exists, and where

| Path | What |
|---|---|
| `france/fetch_sources.py` | Stage 0 — pins every source to a dated, checksummed snapshot |
| `france/chambers.py` | The Sénat and Assemblée registers — **primary** source for parliamentarians |
| `france/prepositions.py` | The French grammar tables (`de` form, bare+article, locative) + their audit flags |
| `france/verified.py` | External confirmations with citations · operator-filled rows · the volatility register |
| `france/build.py` | Stages 1–2 — value sets and answer keys, with every gate |
| `france/render.py` | Renders each question to the literal prompt string |
| `france/export_package.py` | **The deliverable** — the whole corpus as one JSON in the Carter Center's shape |
| `france/check_export.py` | Audits that JSON before it is sent to anyone (40 checks) |
| `france/check_external.py` | Cross-check against independent publishers |
| `france/check_sensible.py` | Is each question sensible for its binding? |
| `france/check_councils.py` | **Monthly cross-check of the council rows** — the only automatic check they have |
| `france/name_matching.py` | The name-normalisation spec + its test suite |
| `france/check_volatility.py` | **What is due for re-checking** |
| `france/probe_presidents.py` | Diagnostic for the council-president data |
| `data/fr/raw/<date>/` | The immutable snapshot + `manifest.json` (URL, SHA-256, bytes, rows) |
| `data/fr/valuesets/` · `groundtruth/` | The deliverable |

**To rebuild from scratch:**

```
python france/fetch_sources.py --date $(date +%F)
python france/build.py --snapshot data/fr/raw/<date> --out data/fr
python france/render.py --data data/fr
python france/check_external.py && python france/check_sensible.py
python france/check_councils.py      # cross-check D3/R1 against fr.wikipedia
python france/check_volatility.py
python france/export_package.py --out data/fr/export     # the file we send them
python france/check_export.py data/fr/export/*.json      # never send one that fails this
```

Everything is open data. **Total cost: €0.** No API keys.

---

## 2. The seven templates

| ID | Question | Shape | Bindings | Source |
|---|---|---|---|---|
| **D1** | Qui représente {dep_article} au Sénat ? | `list` (1–12) | 101 | Sénat live register |
| **D2** | Qui représente {dep_article} à l'Assemblée nationale ? | `list` (1–20) | 101 | Assemblée AMO10 |
| **S3** | Combien y a-t-il de sénateurs {dep_prep} ? | `number` | 101 | derived from D1 |
| **S1** | Le siège de sénateur {dep_prep} est-il renouvelé en septembre 2026 ? | `yes_no` | 101 | `serie` field |
| **S2** | Combien de sièges de sénateur {dep_prep} seront renouvelés le 27 septembre 2026 ? | `number` | 101 | `serie` field |
| **D3** | Qui est le président du conseil départemental {dep_prep} ? | `name` | 94 | RNE + operator |
| **R1** | Qui est le président du conseil régional {reg_prep} ? | `name` | 14 | RNE |

D1 and D2 are phrased so they presuppose no number: 7 départements elect one sénateur and 2
elect one député, and the plural would be a leading question there. See §5.2.

---

## 3. Locales

| Value set | Members |
|---|---|
| `fr_departement` | **101** — code, label, `label_with_preposition`, `label_with_article`, region, n_senateurs, n_circonscriptions, has_conseil_departemental |
| `fr_region` | **18** — code, label, `label_with_preposition`, has_conseil_regional |

**Why this resolution.** The U.S. arm's value sets stop at the congressional district —
counties has 0 members and `{city}` is unpopulated. Matching *administrative names* would
have given ~45,000 bindings; matching **population per unit** gives the département:

| U.S. state | 6,568,627 | French région | 3,830,719 |
|---|---|---|---|
| **U.S. congressional district** | **768,349** | **French département** | **632,596** |
| | | French commune | 1,972 |

So: région ↔ state, département ↔ congressional district, no commune tier.

---

## 4. Sources and precedence

| Population | Source | Precedence | Cadence | Worst-case staleness |
|---|---|---|---|---|
| Sénateurs | `senat.fr/api-senat/senateurs.json` | 100 | live, 120 s cache | ~24 h |
| Députés | `data.assemblee-nationale.fr` AMO10 legislature 17 | 100 | nightly, 23:00–02:00 UTC | ~24 h |
| Council présidents | **RNE only** — `-cd.csv`, `-cr.csv`, `-ma.csv` | 94 | **quarterly** | ⚠ **~10 months, unevenly** — see below |
| Externally verified rows | `france/verified.py` | **110** (operator) | manual | see volatility register |

**Why the chambers outrank the RNE.** Measured on 2026-08-03: the two disagreed on 9 of 202
bindings. Causes, all verified: **4** snapshot staleness (ceased sitting after the file date),
**3** corrupt rows in the published RNE, **1** ingestion lag, **1** *phantom record* — "Sophie
Danet", a senator who does not exist, standing where Daniel Fargeot should be. The chambers
were right in all nine.

> **A hypothesis we recorded and then refuted.** We first believed the RNE lists the
> *titulaire* while the chambers list whoever is *sitting*. It does not. Of the 13 deputies
> who entered the Lecornu II government on 2025-10-12, **13 of 13 are absent from the RNE and
> 12 of their 13 suppléants are present**, all dated 2025-11-13 — the statutory one-month
> date under Ordonnance 58-1099 art. 1 and Code électoral art. LO176. The RNE records
> substitutions correctly. Only 1 of the 9 mismatches (Stéphanie Rist) is a genuine
> titulaire-vs-sitting lag. **The precedence decision is right; the original reason was not.**

**Rejected sources.** `nosdeputes.fr` / `nossenateurs.fr` (Regards Citoyens) — abandoned after
the June 2024 dissolution; `/deputes/json` still serves the dead legislature (every row
`mandat_fin: 2024-06-09`) and stamps *today's* date in the filename. It would have "confirmed"
our data and looked like a pass. Also dead: AMO50 (frozen July 2024) and the data.gouv.fr
mirror of the deputy data (still pointing at legislature 15, 2022). Always hit
`data.assemblee-nationale.fr` directly.

**Independent cross-check.** Wikidata `Q126471296` (17th legislature) returns 576 of 577
deputies — the only genuine third publisher. **There is no usable independent check for
senators, and none at all for council présidents.**

---

## 5. The five things that are not obvious

### 5.1 French slot interpolation needs grammatical agreement, per value

English `"in {state}"` works everywhere. French does not: *du Nord* · *de l'Ain* · *des
Landes* · *de la Somme* · *de Paris* · *d'Eure-et-Loir*. No rule derives it from the name.

Every value-set member carries **`label_with_preposition`**, and templates consume that field,
never the bare label. The 119-row table in `france/prepositions.py` was signed off by a native
speaker on 2026-08-03 with 0 corrections; `render.py` **refuses** to emit runnable prompts
while `AUDITED` is `False`.

An ungrammatical prompt is not a noisier probe of a chatbot — it is a *different* one, so the
capture is invalid rather than merely noisy, and it cannot be repaired afterwards.

**This constrains phrasing.** Each table holds **one** grammatical case, and a template needing
another needs its own table. There are three cases in play and we have audited two:

| Case | Field | Example | Used by | Status |
|---|---|---|---|---|
| `de` form | `label_with_preposition` | *de l'Ain*, *du Nord*, *des Landes* | S1, S2, S3, D3, R1 | signed off 2026-08-03, 119 rows, 0 corrections |
| bare + article | `label_with_article` | *l'Ain*, *le Nord*, *les Landes* | D1, D2 | 86 rows derived from the `de` table, **15 written by Claude** — see §5.2 |
| locative | `DEPARTEMENT_LOC` | *dans l'Ain*, *en Gironde*, *à Paris* | nothing | `LOC_AUDITED = False`, unused |

S2 is *« Combien de sièges de sénateur… seront renouvelés ? »* rather than *« Combien de
sénateurs seront élus {dep_prep} ? »* precisely to avoid the locative: "élus de l'Ain" is
ungrammatical, and the locative table has never been signed off.

### 5.2 Number agreement — a plural question is a leading question

7 départements elect exactly one sénateur (04, 05, 09, 2A, 2B, 48, 90) and 2 elect one député
(23, 48). Asking *« Qui sont les sénateurs… ? »* there presupposes plurality and invites the
model to invent a second name — a wrong answer would be **our phrasing, not the model's
error**.

**First fix (2026-08-03), superseded:** those 9 bindings got a singular template and
`shape: name`. That worked but left D1 and D2 with two question texts each, and — a bug found
on 2026-08-04 — `shape: name` rows whose `expected` was still a one-element **list**, so any
consumer reading `shape` to decide how to parse `expected` broke on exactly those 9 rows.

**Current fix (2026-08-04):** phrase the question so no number is presupposed at all —
*« Qui représente {dep_article} au Sénat ? »* and *« … à l'Assemblée nationale ? »*. One text
per template, all 101 bindings, `shape: list` throughout, cardinality carried on the row.

The cost is a second grammar table. *« représente »* takes the bare name with its article
(*l'Ain*, *le Nord*, *les Landes*, *Paris*), not the *de* form, and the two are not
inter-derivable for every value: 86 of the 101 reverse exactly (`de l'`→`l'`, `du`→`le`,
`des`→`les`, `de la`→`la`) and inherit Gate 1c's sign-off, but 15 cannot, because French drops
the article after *de* for those names and the *de* form therefore does not record what the bare
form takes. Those 15 are written out in `prepositions.py:_ARTICLE_EXPLICIT` and listed by
`ARTICLE_REVIEWED_ROWS`:

- the compound *X-et-Y* départements, where the article returns: 28 *l'Eure-et-Loir*,
  35 *l'Ille-et-Vilaine*, 37 *l'Indre-et-Loire*, 41 *le Loir-et-Cher*, 47 *le Lot-et-Garonne*,
  49 *le Maine-et-Loire*, 54 *la Meurthe-et-Moselle*, 71 *la Saône-et-Loire*,
  77 *la Seine-et-Marne*, 82 *le Tarn-et-Garonne*
- Corsica, feminine: 2A *la Corse-du-Sud*, 2B *la Haute-Corse*
- genuinely article-less, or the article is part of the proper name: 75 *Paris*,
  974 *La Réunion*, 976 *Mayotte*

⚠ **Those 15 rows were written by Claude, not by the Gate 1c reviewer.** Daniel authorised that
on 2026-08-04 rather than block on a second sign-off. They are the only unreviewed grammar
judgement in the corpus, and they are the rows to look at first if a capture reads oddly.

### 5.3 Questions must not presuppose a body that does not exist

**11 bindings are dropped, not answered.** Seven départements have no conseil départemental
(2A, 2B — Collectivité de Corse; 67, 68 — Collectivité européenne d'Alsace; 75 — Ville de
Paris; 972, 973 — assemblées) and four régions have no conseil régional (02, 03, 06, 94 —
collectivités territoriales uniques). *« Qui est le président du conseil départemental de
Paris ? »* asserts something false. That is a gotcha, and this project does not ask those.

**The Rhône answer is scoped; the Métropole de Lyon is not a binding.** The Métropole replaced
the département inside its perimeter on 1 Jan 2015; the "Nouveau Rhône" continues with its own
conseil (cantons cut 54 → 13). Binding `69` answers with the président of that conseil and
carries a `scope_note`. The Métropole is a collectivité à statut particulier — neither a
département nor a région — and the value sets here are exactly those two tiers, so it is
excluded by the same rule that excludes the communes. Decided 2026-08-04; it was a binding
until then.

A *« président de la Collectivité de X »* template would be the honest way to cover the 11
dropped units. Parked — note that Corse and Martinique each have **two** presidents (of the
assembly and of the executive council), so it is a decision, not a lookup.

### 5.4 Identifier traps in the French data

- **The RNE strips leading zeros** from INSEE codes (`1001` not `01001`, `1` not `01`).
  Un-normalised, the mayor join loses **3,095 rows** and presents as a data gap, not a bug.
  Zero-pad to 2 (département) / 5 (commune) before comparing — but overseas codes (`97x`,
  `98x`) are already full width and must **not** be padded.
- **101 départements do not cover either chamber.** Sénat 348 = 328 territorial + 12 Français
  établis hors de France + 8 collectivités. Assemblée 577 = 558 + 11 + 8. Non-territorial
  constituencies are partitioned off and counted, never dropped.
- **Martinique and Guyane file their senators under a *collectivité* code with an empty
  département field.** Without a remap, two départements and four seats vanish.
- **`geo.api.gouv.fr/communes` yields 109 distinct département codes**, not 101 — it includes
  COM codes. Build the value set from `/departements`.
- **The published RNE deputy file is corrupt in 5 rows**: 577 rows, 572 distinct
  circonscription codes (collisions on 102, 2505, 5706, 5917, 8001). `build.py` re-detects this
  on every refresh and fails if it worsens. *Detection only catches collisions — rows wrong in
  a non-colliding way are invisible.*

### 5.5 Name spellings: accept both, but never merge two people

The RNE stores `NOM Prénom` upper-case; the chambers use `Prénom Nom`. Every answer row carries
`accepted_forms` mapping the canonical name to every acceptable spelling — **877 variants**.

Matching is two-pass. Strict: one token set contains the other **and** they share ≥ 2 tokens.
Loose (only when exactly one name is unmatched on each side): a shared token of ≥ 5 characters.
The loose pass is a heuristic and every hit is written to `_review_name_variants.json` for
human confirmation — it is allowed to be wrong somewhere a human will see it.

Three were confirmed as one person, all verified:

| Binding | Forms | Why |
|---|---|---|
| 43 | Jean-Pierre Vigier / Peter VIGIER | "Peter" is a usage nickname distinguishing him from **his father, also Jean-Pierre Vigier**, whom he succeeded as maire in 2008 |
| 974 | Émeline K/Bidi / Emeline KBIDI | The slash is genuine — Breton abbreviation of the prefix *Ker-*. The RNE strips it because its surname field will not take `/` |
| 57 | Khalifé Khalifé / Khalifé KHALIFÉ | Given name and surname are genuinely both "Khalifé" |

**What is never merged:** a person replaced by another. Nine RNE names are `superseded`, not
accepted — Buffet, Danet, Duparay, Boudié, Taite, Rist, Parmentier-Lecocq, A. Martin, Bellamy.
Accepting those would mark a stale answer correct.

---

## 6. Gates

The build **writes nothing** if a gate fails.

| Gate | Checks |
|---|---|
| 0 | every source downloaded, SHA recorded, row counts within 1% of published |
| 1a | cardinality exactly 101 and 18 — constitutional facts, not estimates |
| 1b | referential integrity; Σ senate seats 348; Σ circonscriptions 577 |
| 1c | preposition coverage 119/119, and the native-speaker sign-off flag |
| 2a | coverage per template; **zero** orphan rows |
| 2b | per-binding counts re-derived from a different column and compared |
| 2f | no number presupposed — D1/D2 use one text each, neither naming a count |
| 1d | article coverage 101/101, and how many rows are not derived from the audited table |
| 2h | externally verified rows still match what the pipeline produces |
| 2i | no binding is asked without an answer key |
| 2j | no département splits across senate séries |
| — | RNE integrity: circonscription-code collisions ≤ 5 |

Plus `check_sensible.py` (false premise · number agreement · ambiguous authority · empty
answers) and `check_external.py` (independent cross-check).

---

## 7. Updating

### ⚠ The registry's presidency data is far staler than its file date

The RNE file is dated 2026-05-05, but the most recent presidency change recorded
*anywhere* in it is **2025-10-06**. It is patchy rather than cut off: Charente's change of
16 September 2025 is missing entirely while Aube's of 6 October is present. **Treat the
council-president block as roughly ten months stale, not ninety days.**

This breaks the refresh model for D3 specifically: re-downloading a file that is not being
updated changes nothing. **That block needs external verification on a cycle, not a re-fetch.**

### What the 2026-08-03 verification sweep found

Two passes, and the difference between them is the lesson:

- **Triage on the registry's own dates** — 13 départements whose president took office after
  the 2021 general renewal. Result: **13 of 13 still in office, no elaborate cases.**
- **Open sweep for anomaly classes** — co-governance, interim presidents, prefectoral tutelle,
  annulled elections, post-*municipales* resignations. Result: **2 wrong answers** (02 Aisne,
  82 Tarn-et-Garonne) and **1 renamed body** (976 Mayotte).

**The triage could not have found the errors.** It filters on changes the source already knows
about; our wrong answers were changes made *after* the snapshot, invisible by construction.
When re-verifying, sweep for anomalies — do not triage on the source's own dates.

**Models will echo stale web sources, not hallucinate.** Several aggregators that claim 2026
update dates still serve 2021 data — `regions-et-departements.fr` lists eight superseded
presidents including one who died in January 2025; the government's own `lannuaire` names a
Haute-Saône president superseded six days after its last edit; French Wikipedia's summary list
is stale on two départements and omits both 2026 changes. These are logged in
`verified.py:KNOWN_STALE_SOURCES`. A model answering "Pichery" for the Aube is repeating a live
source. That is a different failure from invention, and the judge should be able to tell them
apart.

### Can the council presidents be verified automatically? PARTLY — and my first answer was wrong

**Recorded as a correction, because the wrong answer was written down first.** On 2026-08-03 I
tested Wikidata's *structured* statements and concluded verification was "irreducibly manual".
That was a half-test. Wikidata is indeed useless here:

| Wikidata attempt | Result |
|---|---|
| `P1308` (officeholder) on the département item | 0 rows |
| person → `P39` position, class-anchored | 1 of 101 |
| any current officeholder for a French département | 4,499 rows → 16 presidencies → **5 of 101** |

But the per-collectivity **Wikipedia articles** carry the president in an infobox, follow a
uniform title pattern, and expose a machine-readable last-revision timestamp. That is enough to
build a **disagreement detector** — `france/check_councils.py`.

**What it is.** It fetches all 109 council articles, extracts the président, and compares against
our answer key using the `name_matching` rule. It reads the *revision date* as well as the name:
an article last revised before a change happened cannot testify about it, so those are reported
as `agree-but-stale` rather than allowed to look like confirmation.

Three markup variants have to be handled, and missing any of them produces false disagreements:
`| président = Name`, `| président = {{Lien par élément|Q123}}` (a Wikidata item id that must be
resolved to a label), and `| leader1_type = Président` + `| leader1 = Name` on région articles.

**Result, 2026-08-04:** **0 disagreements across 107 of 109 rows** — 68 agreeing against an
article revised within 120 days, 39 agreeing against an older one, 2 unparsed (Vaucluse has no
article at the expected title; the Occitanie article has no président field). It independently
reproduces both errors that were found by hand (02 Aisne, 82 Tarn-et-Garonne).

**What it is NOT.** Wikipedia is not an authority, and agreement does not make a row verified —
both sources could be stale in the same direction, which is exactly what happened before the
March 2026 changes. It converts "manually re-check 100 rows every month" into "investigate the
handful where two independent sources disagree", which is a different and much cheaper job.
Run it monthly; treat any disagreement as work, and treat a long run of `agree-but-stale` as a
prompt to spot-check by hand.

### Cadence

**Monthly.** `france/check_volatility.py` reports what is due and flags a full rebuild once the
corpus is 30 days old. Run it monthly **and before every capture batch**.

A refresh is a **diff**, never an overwrite: re-fetch into a new dated snapshot, rebuild, and
compare against the previous one. Changes go to a review queue. The diff is also the list of
rows at risk for the "chatbot right, ground truth stale, judge cries hallucination" failure.

### Rows that need more than a refresh

Registered in `verified.py:VOLATILE`:

| Binding | Kind | Why |
|---|---|---|
| **d3/16 Charente** | **ELABORATE ANSWER** | Two people are defensibly nameable. Sourisseau is the legal président (CGCT recognises one). Since a Dec 2025 co-governance charter, **Nicole Bonnefoy** is styled *co-présidente* on the département's own site. A model naming Bonnefoy is not simply wrong. **Open decision: accept both, or Sourisseau only?** |
| d3/69 Rhône | DATED TRIGGER | Guilloteau reported to be seeking a Senate seat on 27 Sept 2026 — may change inside the capture window |
| s1/* s2/* | DATED TRIGGER | Every answer is about the 27 Sept 2026 renewal. **After the vote these must be retired or rewritten, not refreshed** — the tense and the meaning both change |
| d3/26 Drôme | WEAK SOURCE | ladrome.fr blocked on TLS; currency rests on Wikipedia FR |
| d3/976 Mayotte | WEAK SOURCE | mayotte.fr threw ECONNRESET; confirmed only to 2 June 2026 |
| **d3/\* (85 rows)** | **SINGLE SOURCE** | No publisher but the RNE lists conseil présidents — **no independent cross-check exists**, and the RNE is the file that produced a phantom senator. Highest-risk block in the corpus |
| **d3/89 Yonne** | **WEAK SOURCE** | No 2026-dated source names Grégory Dorte; rests on an undated official élus page. Weakest single row in D3 |
| d3/82 Tarn-et-Garonne | ELABORATE ANSWER | Bertelli won a 15–15 tie on age seniority, then lost all nine vice-presidencies 15–14. Right-wing president, left-wing executive. Naming Valérie Rabault is defensible |
| d3/80 Somme · d3/971 Guadeloupe | DISTRACTOR | One correct name, but a model is unusually likely to give another — a convicted predecessor still sitting as a councillor (80), a contested start date (971) |

### Adding a template

1. Decide the grammatical case. If it is not the `de` form, it needs a **new agreement table
   and a new native-speaker audit** (§5.1). Prefer a phrasing that reuses the audited column.
2. Check the question is sensible for every binding — does the body exist? does number agree?
   is the authority unambiguous? (§5.2, §5.3)
3. Add a cardinality/coverage gate. Write nothing if it fails.
4. Render every prompt and read them.
5. Register anything volatile in `verified.py:VOLATILE`.

---

## 8. Known weaknesses

- **87 of 94 council-president rows have no second source.** This is the weakest block, and the
  registry behind it has already produced a person who does not exist.
- **No independent cross-check for senators.** Wikidata covers deputies only; HATVP is a
  declarations register, not a roster.
- **The preposition table had one reviewer, not two.**
- **RNE corruption detection catches collisions only** — the true corrupt-row count is a lower
  bound.
- **Five of seven templates derive from the same senate register** (D1, S1, S2, S3 and D1's
  variants), so they share a single point of failure. S3 is not independent coverage of D1;
  it is a second view of the same key.
- **A ~1-month legal window makes some answers genuinely indeterminate.** A parliamentarian
  appointed to government keeps the seat for one month (Ord. 58-1099 art. 1) before the
  suppléant takes it. During that month sources legitimately disagree. Consider excluding any
  seat that changed hands within ~35 days.
