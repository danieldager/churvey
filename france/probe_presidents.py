#!/usr/bin/env python3
"""Stage 5 probe - can the presidents of the conseils departementaux/regionaux
be derived from the RNE, or do D3/R1 leave the automatable block?

The RNE lists every councillor. The "Libelle de la fonction" column marks
executive roles, so a president is derivable in principle. Two things make the
naive count wrong, and both are handled here:

  1. LEADING ZEROS. cd/cr store departement and region codes unpadded ('1', not
     '01'). Unpadded, Guadeloupe and La Reunion look like missing regions.
  2. COLLECTIVITES TERRITORIALES UNIQUES. Corse, Martinique, Guyane and Mayotte
     have an assemblee, not a conseil regional; Corse, Paris, Alsace, Martinique
     and Guyane have no conseil departemental at all. Their absence from cd/cr is
     correct, not a gap - so the denominator is not 101/18.

Presidents of the collectivites uniques come from elus-membres-assemblee-ma.csv.

PASS if >= 95% of units that actually have the body resolve to exactly one
president. Otherwise D3+R1 leave the automatable block.

  france/probe_presidents.py [--snapshot data/fr/raw/2026-08-03]
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

# departements with no conseil departemental of their own
NO_CD = {
    "2A": "Collectivité de Corse", "2B": "Collectivité de Corse",
    "67": "Collectivité européenne d'Alsace", "68": "Collectivité européenne d'Alsace",
    "75": "Ville de Paris (Conseil de Paris)",
    "972": "Assemblée de Martinique", "973": "Assemblée de Guyane",
    # renamed Assemblée de Mayotte on 1 Jan 2026, so "conseil départemental de
    # Mayotte" names nothing. Question deferred 2026-08-04, see france/DEFERRED.md
    "976": "Assemblée de Mayotte (Département-Région de Mayotte)",
}
# regions with no conseil regional (collectivite territoriale unique)
NO_CR = {
    "94": "Collectivité de Corse", "02": "Assemblée de Martinique",
    "03": "Assemblée de Guyane", "06": "Département-Région de Mayotte",
}


def read(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def pad(code, width):
    code = code.strip()
    return code.zfill(width) if len(code) < width and code.isdigit() else code


def presidents(rows, code_col, width):
    """unit code -> list of rows whose fonction is president (not vice-)."""
    out = defaultdict(list)
    for r in rows:
        f = r["Libellé de la fonction"].strip().lower()
        if f.startswith("président") and "vice" not in f:
            out[pad(r[code_col], width)].append(r)
    return out


def report(label, universe, excluded, found):
    eligible = {c: n for c, n in universe.items() if c not in excluded}
    exact = {c for c, rs in found.items() if len(rs) == 1 and c in eligible}
    multi = {c: len(rs) for c, rs in found.items() if len(rs) > 1 and c in eligible}
    absent = sorted(c for c in eligible if c not in found)
    rate = len(exact) / len(eligible)

    print(f"\n=== {label} ===")
    print(f"universe {len(universe)}  -  structurally excluded {len(excluded)}"
          f"  =  eligible {len(eligible)}")
    print(f"exactly one president: {len(exact)}/{len(eligible)} = {rate:.1%}")
    if absent:
        print(f"NO president row ({len(absent)}): "
              + ", ".join(f"{c} {universe[c]}" for c in absent))
    if multi:
        print(f"AMBIGUOUS, >1 president row ({len(multi)}): "
              + ", ".join(f"{c} {universe[c]} x{n}" for c, n in sorted(multi.items())))
    ok = rate >= 0.95
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} (threshold 95%)")
    return ok, sorted(set(absent) | set(multi))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="data/fr/raw/2026-08-03")
    args = ap.parse_args()
    snap = Path(args.snapshot)

    deps = {d["code"]: d["nom"] for d in json.loads((snap / "departements.json").read_text())}
    regs = {r["code"]: r["nom"] for r in json.loads((snap / "regions.json").read_text())}

    cd = read(snap / "elus-conseillers-departementaux-cd.csv")
    cr = read(snap / "elus-conseillers-regionaux-cr.csv")
    ma = read(snap / "elus-membres-assemblee-ma.csv")

    d3_ok, d3_todo = report("D3 - president du conseil departemental", deps, NO_CD,
                            presidents(cd, "Code du département", 2))
    r1_ok, r1_todo = report("R1 - president du conseil regional", regs, NO_CR,
                            presidents(cr, "Code de la région", 2))

    print("\n=== collectivites uniques (elus-membres-assemblee-ma.csv) ===")
    print("columns:", list(ma[0]))
    fn = Counter(r.get("Libellé de la fonction", "").strip() for r in ma)
    for v, n in fn.most_common(6):
        print(f"  {v or '(empty)':50s} {n:4d}")

    print(f"\nSTAGE 5: D3={'PASS' if d3_ok else 'FAIL'}  R1={'PASS' if r1_ok else 'FAIL'}")
    todo = len(d3_todo) + len(r1_todo) + len(NO_CD) + len(NO_CR)
    print(f"units needing a hand-written GT row: {todo}")
    print(f"  D3 unresolved: {d3_todo}")
    print(f"  R1 unresolved: {r1_todo}")


if __name__ == "__main__":
    main()
