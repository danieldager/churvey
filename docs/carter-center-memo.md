# Memo — adding France to the Civic AI Audit

**To:** Civic AI Audit engineering, The Carter Center
**Date:** 2026-08-03
**Re:** A French arm of civicaiaudit.org — what we have built, what we need from you

---

## The short version

We have built the French question set and answer keys for a France arm, in your data model:
**7 templates · 119 locales · 613 questions · 613 answer keys · no gaps.** Everything is open
data and cost nothing to produce.

As far as we can tell from outside, **France needs no change to your schema**. It is a data
port: new value sets, new templates, new ground-truth rows. One open question in §4 may prove
us wrong, and it is the first thing we would want your read on.

We need four things from you (§7). Only the first blocks us.

The hard date is the **French Senate election of 27 September 2026** — candidacies are filed
7–11 September, and the interesting capture window is the fortnight before the vote.

---

## 1. Scale, and why the France arm is deliberately smaller

We mirrored the **resolution** you chose rather than the administrative names, and that
distinction turned out to matter.

Your value sets are 51 states and 436 congressional districts. Counties has 0 members and
`{city}` is unpopulated — you fan nothing below the congressional district. Our first pass
mirrored French administrative levels *by name* and arrived at ~45,000 bindings, which is a
different study, not a replication. Population per unit settles it:

| Unit | Mean population |
|---|---|
| U.S. state | 6,568,627 |
| **U.S. congressional district** | **768,349** |
| French région | 3,830,719 |
| **French département** | **632,596** |
| French commune | 1,972 |

The **département is the population-match for a congressional district**, not for a state. So
France is 18 régions + 101 départements, with no commune tier — mirroring your empty `{city}`.

| | You | France | |
|---|---|---|---|
| Templates | 20 | **7** | 35% |
| Distinct locales | 487 | **119** | 24% |
| Questions (template × binding) | ~1,484 | **613** | 41% |
| Answer-key rows | 3,761 | **613** | 16% |
| Captures at 22 active targets | 32,648 full crossing | **13,486** | 41% |

We hold the full national commune-level keys offline (34,637 mayors, 34,963 voter-ID keys) as
a research asset. They are flagged not-for-load and are **not** part of this port.

## 2. The seven templates

| ID | Question | Shape | Bindings | Transposes |
|---|---|---|---|---|
| **D1** | Qui représente {dep_article} au Sénat ? | `list` (1–12) | 101 | *Who are my U.S. senators in {state}?* |
| **D2** | Qui représente {dep_article} à l'Assemblée nationale ? | `list` (1–20) | 101 | *Who is my U.S. representative in {district}?* |
| **S3** | Combien y a-t-il de sénateurs {dep_prep} ? | `number` | 101 | — |
| **S1** | Le siège de sénateur {dep_prep} est-il renouvelé en septembre 2026 ? | `yes_no` | 101 | — |
| **S2** | Combien de sièges de sénateur {dep_prep} seront renouvelés le 27 septembre 2026 ? | `number` | 101 | — |
| **D3** | Qui est le président du conseil départemental {dep_prep} ? | `name` | 94 | *Who is the governor of {state}?* |
| **R1** | Qui est le président du conseil régional {reg_prep} ? | `name` | 14 | ” |

S1, S2 and S3 have no U.S. counterpart and exist because the September election makes them
live. **S1 and S2 must be retired or rewritten after 27 September** — the tense and the meaning
both change; they are not merely refreshable.

**Two value sets**, in the shape of your jurisdiction queries:

| Set | Members | Per-member fields |
|---|---|---|
| `fr_departement` | 101 | code, label, `label_with_preposition`, `label_with_article`, region_code, n_senateurs, n_circonscriptions, has_conseil_departemental |
| `fr_region` | 18 | code, label, `label_with_preposition`, has_conseil_regional |


## 3. Sources and precedence

| Population | Source | Precedence | Cadence | Worst-case staleness |
|---|---|---|---|---|
| Sénateurs | `senat.fr/api-senat/senateurs.json` | 100 | live, 120 s cache | ~24 h |
| Députés | `data.assemblee-nationale.fr` AMO10, legislature 17 | 100 | nightly | ~24 h |
| Council présidents | **RNE only** (Ministère de l'Intérieur) | 94 | **quarterly** | ⚠ **~10 months** — see §8 |
| Externally verified rows | operator | **110** | manual | monthly review |

**We do not use the RNE for parliamentarians**, and the reason is worth your attention. On
2026-08-03 the RNE and the chambers disagreed on **9 of 202** bindings. Verified causes: 4
snapshot staleness, 3 **corrupt rows in the published RNE file**, 1 ingestion lag, and 1
**phantom record** — a senator named "Sophie Danet" who does not exist, occupying the slot of
Daniel Fargeot, who is absent from the file entirely. The chambers were right in all nine.

Concretely: the published RNE deputy file has **577 rows but only 572 distinct constituency
codes**. Our build re-detects this on every refresh and fails if it worsens.

**Independent cross-check.** Wikidata (`Q126471296`) covers 576 of 577 deputies. **There is
none for senators.** For council présidents there is no second *authority*, but we built a
disagreement detector against French Wikipedia article infoboxes (`france/check_councils.py`) —
it reads the article's revision date as well as the name, so an article too old to testify about
a recent change is reported as such rather than counted as confirmation. On 2026-08-04 it found
**0 disagreements across 107 of 109 rows**, and it independently reproduces both errors we had
found by hand. Agreement does not make a row verified — both sources can be stale in the same
direction — but it makes monthly re-checking tractable.

## 4. The one thing that may need a change on your side

**French slot interpolation requires grammatical agreement, per value.** English `"in {state}"`
works for every value. French does not:

> *du Nord* · *de l'Ain* · *des Landes* · *de la Somme* · *de Paris* · *d'Eure-et-Loir*

No rule derives this from the name. A template rendering *"Qui sont les sénateurs Ain ?"* is
ungrammatical, and an ungrammatical prompt is not a weaker probe of a chatbot — it is a
*different* one, so the capture is invalid rather than merely noisy, and it cannot be repaired
afterwards.

Our solution adds **`label_with_preposition`** to each value-set member and phrases templates to
consume that field rather than the bare label. **Whether this needs work on your side depends
on something we cannot see:** if your importer passes arbitrary per-member fields through, it
works as-is; if value-set members are a fixed shape, it is a migration. Cheap now, expensive
after 10,000 captures.

Each table holds **one grammatical case**, and a template needing another case needs another
table. `fr_departement` carries two: `label_with_preposition` (*de l'Ain*, for "les sénateurs
___") and `label_with_article` (*l'Ain*, for "Qui représente ___"). Both are per-member fields,
so if your importer passes fields through, two costs no more than one.

## 5. Design decisions you should know we made

**`shape: name` does not hold for the Senate.** A U.S. state has exactly two senators; a French
département has **1 to 12**, and contains 1 to 20 constituencies. D1 and D2 are therefore
`shape: list` with an **expected cardinality** on the row. If your grader can check "the right
number of names, and the right ones", nothing changes. If cardinality is implicit in your `list`
shape, we should talk — grading a 12-name answer against a 2-name assumption produces nonsense.

**D1 and D2 presuppose no number, and that cost a second grammar table.** 7 départements elect
one sénateur and 2 elect one député. Asking *« Qui sont les sénateurs… ? »* there presupposes
plurality and invites the model to invent a second name — a wrong answer would be our phrasing,
not the model's error. Phrasing it *« Qui représente {dep_article} au Sénat ? »* removes the
presupposition and lets one text cover all 101, but it needs the bare name **with its article**
(*l'Ain*, *le Nord*, *les Landes*, *Paris*) rather than the *de* form, which is a different
grammatical case. So `fr_departement` members carry **two** grammar fields, not one.

**11 bindings are dropped, not answered.** Seven départements have no conseil départemental
(Corsica ×2, Alsace ×2, Paris, Martinique, Guyane) and four régions have no conseil régional
(collectivités territoriales uniques). *« Qui est le président du conseil départemental de
Paris ? »* asserts something false. We are not asking questions with false premises.

**The Rhône answer is scoped, and the Métropole de Lyon is deliberately absent.** The Métropole
replaced the département inside its perimeter in 2015; the "Nouveau Rhône" continues with its
own conseil. So the answer for `69` is the président of that conseil, and the row carries a
`scope_note` saying so. The Métropole itself is neither a département nor a région, and these
value sets are exactly those two tiers, so it is not a binding.

## 6. What your grader needs to do with names

The RNE writes `NOM Prénom` upper-case; the chambers write `Prénom Nom`. **We publish
`Prénom NOM` as canonical**, and every row carries `accepted_forms` listing each acceptable
spelling — **877 variants** across the corpus.

Our matching spec is in `france/name_matching.py`, with a 9-case test suite it passes:
normalise (strip accents, case-fold, split on punctuation, drop nobiliary particles), then
compare token **sets** — equal, or one containing the other with ≥2 shared tokens, allowing one
adjacent-token merge. That absorbs married/compound surnames (*Guérin* / *Bessin-Guérin*),
punctuation inside a surname (*K/Bidi* / *KBIDI*), and your-style disambiguation suffixes
(*Alexandra Martin (Gironde)* — there are two deputies of that name).

It deliberately does **not** absorb a substitution: *Buffet → Vidal* share nothing, so a stale
answer can never be graded correct.

**Comparison is order-insensitive by design.** We expect models to answer given-name-first, but
we do not rely on it — French official registers really do write surname-first, so a model that
has read them may echo that order. Making the comparison order-insensitive costs nothing;
being wrong about the assumption would mark correct answers inaccurate.

**Two policy questions are yours, not ours** — they are judgements about what "accurate" means:

- **A.** Is a surname-only answer accurate? *"Vigier"* for *"Jean-Pierre Vigier"*. Our
  suggestion: accept for `name`, reject inside a `list` where members may share a surname.
- **B.** Must a `list` answer be complete? A département with 11 députés — is naming 8 of them
  `partially_accurate` or `inaccurate`? `expected_cardinality` is on every row, so either
  policy is implementable.

One name resists every rule: the deputy for Haute-Loire is **Jean-Pierre Vigier**, whom the RNE
records as **"Peter" Vigier** — a usage nickname distinguishing him from *his father, also
Jean-Pierre Vigier*. It is carried as an explicit alias, not matched by rule.

## 7. What we need from you

| | Ask | Blocks | Your effort |
|---|---|---|---|
| **1** | **What format does your importer take?** CSV, JSON, DB seed, admin CRUD? Our data is format-agnostic JSON; this is a thin adapter once we know. | Everything | One reply |
| **2** | **Do value-set members carry arbitrary per-member fields?** We need `label_with_preposition` (§4). | The grammar fix | One reply, possibly a migration |
| **3** | **Runner egress must be French.** Your own Insight #3 showed IP geolocation drives answers; French questions answered from a U.S. IP measure something else. | Validity of every capture | Runner hosting |
| **4** | **Add Mistral Le Chat as a target.** A French arm without the main French surface is a conspicuous gap. | Completeness | One target config |

We would also value a sanity check on our reading of your model — the precedence ladder, the
operator override, `shape: list` semantics. We inferred all of it from public admin views and
have never seen the importer.

## 8. Honest limitations

- **The council-president block is the weakest part of this corpus, and we would rather say so
  than have you find it.** 87 of 94 rows have no second source — no publisher but the Interior
  Ministry lists them, and that is the file that produced a senator who does not exist. Worse,
  its presidency data is **~10 months stale, not the 90 days its file date implies**: the most
  recent change recorded anywhere in it is 2025-10-06. We swept it externally on 2026-08-03 and
  found **2 outright wrong answers** (Aisne, Tarn-et-Garonne) and **1 binding naming a body that
  no longer exists** (Mayotte's conseil départemental became the Assemblée de Mayotte on
  1 January 2026). All three are corrected, at operator precedence. We would not describe the
  remaining 85 as verified, and we would understand a decision to hold D3 out of a first batch.
- **No independent cross-check exists for senators.** Wikidata covers deputies only.
- **The French grammar table had one reviewer, not two.**
- **Our RNE corruption detection catches only collisions**, so 5 corrupt rows is a lower bound.
- **Five of seven templates derive from the same senate register**, so they share a single point
  of failure. S3 is not independent coverage of D1; it is a second view of the same key.
- **A ~1-month legal window makes some answers genuinely indeterminate.** A parliamentarian
  appointed to government keeps the seat for one month (Ord. 58-1099 art. 1; Code électoral
  LO176) before the suppléant takes it. During that month the sources legitimately disagree. We
  suggest excluding any seat that changed hands within ~35 days.

## 9. Keeping it current

The corpus is refreshed **monthly**, and a refresh is a **diff, never an overwrite**: re-fetch
into a new dated snapshot, rebuild, compare, and route changes to review. That diff is also the
list of rows at risk for your Key Insight #2 failure mode — chatbot right, ground truth stale,
judge reports a hallucination.

Items are registered as needing more than a refresh, including two where the answer is
genuinely contested. In the **Charente**, a December 2025 co-governance charter styles Nicole
Bonnefoy *co-présidente* on the département's own website, while the law recognises only Jérôme
Sourisseau. In **Tarn-et-Garonne**, Jean-Claude Bertelli won a 15–15 tie on age seniority and
then lost all nine vice-presidencies 15–14, leaving a right-wing president with a left-wing
executive — naming Valérie Rabault is defensible. Both carry every acceptable answer plus the
legal position.

One finding may matter for your grading generally: **several web sources that a model has
plausibly ingested are wrong right now.** Aggregators claiming 2026 update dates still serve
2021 data — one lists eight superseded departmental presidents, including a man who died in
January 2025 — and the French government's own directory names a president superseded six days
after its last edit. A model answering with those names is repeating a live source rather than
inventing one. That is a different failure mode from hallucination, and it may be worth
distinguishing in the verdict enum. We log the known-stale sources alongside the answer keys.

**Annexes:** `docs/france-methodology.md` (full reconstruction and update procedure) · value
sets and answer keys (JSON) · source manifest with SHA-256 · `france/name_matching.py`.
