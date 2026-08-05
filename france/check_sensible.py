#!/usr/bin/env python3
"""Is every question sensible for its binding?

Coverage and cardinality gates prove the data reconciles. They do not ask whether
each rendered question presupposes something true. A question can be perfectly
well-formed, have a perfectly good answer key, and still be a bad question -
because it asserts a false premise, or leads the model toward a wrong shape of
answer. Those are not gotchas we chose; they are gotchas we would ship by accident.

Checks:
  1. FALSE PREMISE   the body/office named does not exist for that binding
  2. NUMBER AGREEMENT a plural question whose true answer is a single person
  3. AMBIGUOUS AUTHORITY  more than one body could reasonably be meant
  4. EMPTY / NULL    a binding with no answer

  france/check_sensible.py
"""
import json
from collections import Counter
from pathlib import Path

DATA = Path("data/fr")
GT = DATA / "groundtruth"

# Territories where a departement-level question has a competing authority.
# The Metropole de Lyon exercises departmental competences on its own territory,
# so a Lyon resident's "conseil departemental" is not the Rhone's.
AMBIGUOUS_AUTHORITY = {
    "69": "Métropole de Lyon exercises departmental competences over Lyon; the "
          "conseil départemental du Rhône covers only the 'Nouveau Rhône'. A Lyon "
          "resident asking this has a different correct answer.",
}


def main():
    findings = []
    load = lambda n: json.loads((GT / f"{n}.json").read_text(encoding="utf-8"))
    d1, d2 = load("d1_senateurs"), load("d2_deputes")
    d3, r1 = load("d3_president_conseil_departemental"), load("r1_president_conseil_regional")
    dropped = json.loads((GT / "_dropped_bindings.json").read_text(encoding="utf-8"))

    print("=== 1. FALSE PREMISE ===")
    n_drop = len(dropped["d3"]) + len(dropped["r1"])
    print(f"  {n_drop} bindings already dropped (no such body exists) - D3 {len(dropped['d3'])},"
          f" R1 {len(dropped['r1'])}")
    print("  D1/D2: every département elects senators and députés by construction. OK.")

    print("\n=== 2. NUMBER AGREEMENT ===")
    for label, rows, noun in (("D1 sénateurs", d1, "sénateur"), ("D2 députés", d2, "député")):
        singles = [r for r in rows if r["expected_cardinality"] == 1
                   and r["template"].startswith("Qui sont")]
        n1 = sum(1 for r in rows if r["expected_cardinality"] == 1)
        print(f"  {label}: {n1}/{len(rows)} bindings have exactly one {noun}; "
              f"{len(singles)} of those still use a PLURAL template")
        if singles:
            ex = singles[0]
            print(f"     e.g. « Qui sont les {noun}s {ex['rendered_slot']} ? » "
                  f"-> {ex['expected'][0]}  (1 person)")
            print(f"     bindings: {', '.join(r['bindings']['departement'] for r in singles)}")
            findings.append(
                f"{label}: {len(singles)} plural questions with a singular answer. A plural "
                f"question presupposes plurality and invites the model to invent a second name; "
                f"a wrong answer here is our phrasing, not the model's error.")

    print("\n=== 3. AMBIGUOUS AUTHORITY ===")
    split = {r["bindings"]["departement"] for r in d3}
    for code, why in AMBIGUOUS_AUTHORITY.items():
        if f"{code}M" in split:
            print(f"  D3 {code}: RESOLVED - split into {code} (Nouveau Rhône) "
                  f"and {code}M (Métropole de Lyon)")
            continue
        hits = [r for r in d3 if r["bindings"]["departement"] == code]
        if hits:
            print(f"  D3 {code}: {why}")
            findings.append(f"D3 binding {code}: competing authority (Métropole de Lyon).")

    print("\n=== 4. EMPTY / NULL ANSWERS ===")
    bad = [r for rows in (d1, d2, d3, r1) for r in rows if not r.get("expected")]
    print(f"  bindings with an empty answer: {len(bad)}")

    print("\n=== SUMMARY ===")
    if not findings:
        print("  no issues")
    for f in findings:
        print(f"  - {f}")
    print(f"\ntotal loaded bindings: {len(d1)+len(d2)+len(d3)+len(r1)} with keys")


if __name__ == "__main__":
    main()
