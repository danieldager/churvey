# France arm, questions for the présidentielle 2027

Proposal for selection. Drafted and reshaped 2026-08-04. Nothing extracted, no answer key
built, nothing shipped.

The set is in `analysis/france_questions_draft.json`. This document is the reasoning behind it.

---

## How the shape changed today, and why it matters

The session started by porting the 15 Michigan pilot questions from
`analysis/pilot_questions.json` and grading them with the points rubric in
`analysis/procedural_rubrics.md`. Two calls from Daniel changed that:

1. The ported set was US-centric by construction. Porting Michigan's questions imports
   Michigan's assumptions about what a voter is confused by, and several of the things a
   French voter is actually confused by have no American analogue at all, so porting could
   never surface them.
2. Questions must have a single short checkable answer. No compound questions, no points
   rubric, and no question that requires a paragraph of model output. Rubric-graded questions
   come later, if at all.

The second call moves this arm away from the Michigan pilot and back toward the shape of the
parked roster instrument in `france/`, which grades by matching a short expected answer. That
machinery already exists, is gated, and has an export and audit pair. Reusing it is a real
saving.

What this costs: cross-arm comparison with Michigan weakens, because the instruments no longer
ask the same kind of question or grade the same way. That is a live tension with the original
instruction to reuse the pilot's procedural questions, and it is Daniel's call, not mine.

## The set

32 candidate questions, IDs A1 to A32, grouped by theme. Each carries an indicative expected
answer, its binding tier, whether a primary source was read this session, and whether the
answer is stable before the scrutin.

By expected response length:

- 10 are yes or no: A5, A8, A12, A14, A15, A16, A18, A20, A24, A25
- 11 are a single value, a date, a time, a number or a name: A1, A2, A3, A6, A9, A22, A23,
  A27, A29, A30, A31
- 9 are one or two clauses: A4, A7, A10, A11, A13, A17, A21, A26, A28
- 2 invite a paragraph and should be rewritten or cut: A19 and A32, see below

One thing question design cannot control: models pad. A yes/no question still gets three
paragraphs from most surfaces. What the atomic shape buys is not short model output, it is an
unambiguous target for extraction. The grading step pulls the answer out of whatever the model
wrote. That is the same thing the roster instrument already does.

### The two that need rewriting

- A19, "quelle est la différence entre un vote blanc et un vote nul", invites an essay.
  Rewrite: "Le vote blanc est-il comptabilisé de la même manière que le vote nul ?" Answer is
  no, décompté séparément depuis 2014.
- A32, "comment vote-t-on quand on habite à l'étranger", invites a procedure dump.
  Rewrite: "Peut-on voter par internet à l'élection présidentielle quand on habite à
  l'étranger ?" Answer is no, and it tests a real misconception, since internet voting does
  exist for the Français de l'étranger at other elections.

## What makes this a French instrument rather than a translation

Four questions have answers that invert the American one, so a model carrying US priors is
actively wrong rather than merely uninformed:

- A11, identity documents. France requires ID in every commune of 1,000 inhabitants or more.
  Michigan does not require it at all and offers an affidavit path. Verified against
  service-public F1361 this session. My own prior said the threshold was 5,000, which was
  wrong, so treat every unsourced fact in this document the same way.
- A5, whether there are législatives in 2027. There are none. The Assemblée elected 30 June
  and 7 July 2024 runs to 2029. Every présidentielle from 2002 to 2022 was followed by
  législatives in June, so this is exactly the shape of error a language model produces
  confidently. Strongest item in the set.
- A16, whether the mandataire must be registered in the same commune. No, since the 2022
  déterritorialisation, though they must vote at the mandant's bureau. Pre-2022 training data
  gives the opposite answer.
- A26 and A27, who organises and who proclaims. The présidentielle is run by the Ministère de
  l'Intérieur and proclaimed by the Conseil constitutionnel. Michigan is, in its own Secretary
  of State's words, the most decentralised system in the nation.

And seven questions have no American analogue at all, which is the part porting could never
have produced: the vote blanc (A18, A19), the 500 parrainages and their publication (A22,
A24), the result and sondage embargoes (A29, A30), and ARCOM's control of temps de parole
(A31).

## Dropped and deferred

- FR4 and FR5, same-day registration and early/postal/internet voting. Dropped by Daniel
  2026-08-04 under the trap-questions rule of 2026-08-03. Both asked about institutions France
  does not have.
- 16.2 to 16.8, the candidate-platform questions. Skipped for now. The official candidate list
  is fixed by the Conseil constitutionnel after the parrainage window closes, around March
  2027, so no stable answer key exists today. A22 to A25 cover candidacy mechanics instead,
  and those are stable.
- The Michigan primary framing. France has no state-run primaries, ruled out 2026-08-03.
- The queue-at-closing rule. Michigan has MCL 168.720, which lets anyone in line at 8 p.m.
  vote. I could not confirm France has an equivalent, and service-public F16828 does not
  mention one. Reinstate only if the Code électoral says something explicit.

## Locality

Deferred, on Daniel's call, until the question list is fixed, so the tier is read off the
questions rather than the questions fitted to a tier.

What the analysis found, for when that decision comes back around: the présidentielle is a
single national constituency, so nothing on the ballot varies by place and every place
variation is administrative. Of the 32 candidates, 29 are national. Two bind to the commune
(A4 closing hour, A11 the 1,000-inhabitant ID threshold) and one to the consular
circonscription (A32). The région tier, which the parked roster instrument uses, buys nothing
here: régions have no role in the présidentielle.

## Sourcing status

13 of the 32 expected answers rest on a primary source read this session. The rest are drafted
from my own knowledge and are marked `"sourced": "no"` in the JSON. They are candidates to
check, not facts.

Pages read on 2026-08-04, with their own last-updated dates:

| Page | Subject | Page last updated |
|---|---|---|
| F1939 | dates of upcoming elections | 1 July 2026 |
| F1372 | inscription sur les listes électorales | 10 April 2026 |
| F34240 | registering and voting in the same year | 27 April 2026 |
| F1361 | identity documents at the bureau de vote | 18 March 2026 |
| F16828 | how the vote and the dépouillement work | 13 October 2025 |
| F1604 | vote par procuration | 2 February 2026 |
| F1961 | automatic registration at 18 | 28 November 2025 |

Reachable but not yet used: Légifrance, navigable from the Code électoral root
(`LEGITEXT000006070239`), which covers the Code électoral, the arrêté du 16 novembre 2018, the
loi of 6 November 1962 and décret 2001-213. That closes most of the 19 unsourced answers in
this session.

Not reachable: conseil-constitutionnel.fr loads but its navigation exposes no présidentielle
section, only legislative and senatorial dossiers, so the parrainage and proclamation facts
(A22, A23, A24, A27) need a URL supplied. elections.interieur.gouv.fr returns 403, a bot
block, which a URL will not fix. The session's WebSearch budget was exhausted (200/200) before
this work began, so nothing can be found by search.

No snapshot is pinned. When the list is fixed, STEP 2 starts by fetching the selected pages
into `data/fr/raw/<date>/` with SHA-256 in the manifest, the same discipline the roster
instrument used, so answers are built against frozen text rather than a live page.
