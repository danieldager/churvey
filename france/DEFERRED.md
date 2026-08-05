# Deferred decisions

Things taken out of the shipped corpus on purpose, with enough detail to put them back.
Nothing here is a bug. Each entry is a case we understand and chose not to carry in pass one.

---

## 976 Mayotte, D3 — question dropped 2026-08-04

**What happened.** On 1 January 2026, under the loi de programmation of 11 August 2025,
Mayotte became the *Département-Région de Mayotte* and its conseil départemental became the
*Assemblée de Mayotte*, holding both departmental and regional competences.

**Why it was a problem.** D3 asks « Qui est le président du conseil départemental … ? ». For
Mayotte that names a body which no longer exists under that name, so any answer would be
wrong for a reason we created rather than a reason about the model. The fix in place until
2026-08-04 was a per-binding reworded template, « Qui est le président de l'Assemblée de
Mayotte ? », with no slot at all. That made 976 the only row in 613 whose text was written
rather than generated, which breaks the one-text-per-template assumption for any consumer.

**Decision (Daniel, 2026-08-04).** Drop the question and the binding. Not worth the schema
complication in pass one.

**To restore.** The answer was verified on 2026-08-03:

- expected: `Ben Issa OUSSENI`, in office since 2021-07-01
- confirmed to 2 June 2026. mayotte.fr threw ECONNRESET, so currency rested on indexed
  pages plus French Wikipedia
- https://www.mayotte.fr/le-conseil-departemental/assemblee-departementale/le-president
- rename source: https://la1ere.franceinfo.fr/mayotte/le-conseil-departemental-devient-assemblee-de-mayotte-1658792.html

The mechanism that carried it, `verified.TEMPLATE_OVERRIDES` plus Gate 2m in `build.py`, is
still in place and empty. Re-adding the dict entry restores the row.

Note 976 is still a member of `fr_departement` and still carries D1, D2, S1, S2 and S3.
Only the D3 binding is gone.

---

## 16 Charente, D3 — grading rule deferred 2026-08-04

**The situation.** Jérôme Sourisseau was elected président on 16 September 2025 (3rd round,
18 of 38) after Philippe Bouty resigned on 1 September 2025 following three budget rejections
and a prefectoral takeover. Since a co-governance charter of December 2025, Nicole Bonnefoy
(PS senator) is styled *co-présidente* on the département's own site. The CGCT recognises
only one président, and that is Sourisseau.

**Decision (Daniel, 2026-08-04).** Sourisseau is the answer. The full grading rule he wants,
once graders are more than exact match:

- Sourisseau alone: correct
- Sourisseau and Bonnefoy: correct, no points lost
- Bonnefoy alone: wrong
- Sourisseau plus someone who is not Bonnefoy: wrong

**What ships now.** `expected` is `Jérôme SOURISSEAU` and nothing else. The `also_accept`
list and the open-decision entry are removed, because a two-name answer key that no grader
yet reads is complication without benefit. This supersedes the 2026-08-03 decision to flag
the row as ELABORATE and accept either name.

The row stays in `verified.VOLATILE` and is re-checked monthly, since the charter could
change what is true.

---

## Precedence — field removed from the export 2026-08-04

The exported rows used to carry `precedence`: 110 for a human-verified answer, 100 for a
chamber register, 95 for the Interior Ministry register. Daniel's call: it obfuscates, and
`authority` already says where the answer came from in words.

The ordering itself is still real and still enforced in `build.py`: for D1 and D2 the chamber
is consulted first and any name the Interior Ministry lists that the chamber does not is
rejected into `_superseded_by_chamber.json`. That decision now lives in code and comments
rather than in a number on every row.
