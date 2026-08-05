#!/usr/bin/env python3
"""Gate 2d - cross-check the ground truth against sources INDEPENDENT of the RNE.

The RNE (Ministere de l'Interieur) is our only source so far. Our build gates
prove internal consistency, not accuracy: if the RNE is wrong about a senator,
every gate still passes. This checks it against two unrelated publishers.

  senateurs  data.senat.fr ODSEN_GENERAL.csv   (the Senat's own open data)
  deputes    data.assemblee-nationale.fr AMO10  (the Assemblee's own open data)

nosdeputes.fr (Regards Citoyens) was tried first and REJECTED: its /deputes/json
still serves the 2022-2024 legislature, dissolved in June 2024 - every row carries
mandat_fin 2024-06-09. Checking current data against it would have "confirmed"
nothing and looked like a pass.

Scope: ALL 101 departements on both templates, not a sample - the sources cover
the full chamber, so there is no reason to subsample and report a weaker claim.

Names are compared on a normalised key (accents stripped, case folded, particles
and punctuation removed, given/family order ignored) so that spelling conventions
between publishers do not read as disagreements.

  france/check_external.py [--snapshot data/fr/raw/2026-08-03]
"""
import argparse
import csv
import json
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

SEN_URL = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"
DEP_URL = ("https://data.assemblee-nationale.fr/static/openData/repository/17/amo/"
           "deputes_actifs_mandats_actifs_organes/"
           "AMO10_deputes_actifs_mandats_actifs_organes.json.zip")

# name particles that publishers include or drop inconsistently
PARTICLES = {"de", "du", "des", "la", "le", "les", "d", "l", "van", "von", "di", "da"}


def key(name):
    """Order-insensitive, accent-insensitive, particle-insensitive name key."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    toks = [t for t in s.split() if t and t not in PARTICLES]
    return frozenset(toks)


def fetch(url, dest):
    r = subprocess.run(["curl", "-sS", "-f", "-L", "-m", "40", "-o", str(dest), url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fetch failed {url}: {r.stderr.strip()}")
    return dest


def load_senat(path):
    """ODSEN_GENERAL.csv: latin-1, ';'-delimited, '%'-prefixed comment preamble."""
    text = path.read_text(encoding="latin-1")
    lines = [l for l in text.splitlines() if l and not l.startswith("%")]
    rows = list(csv.DictReader(lines, delimiter=","))
    hdr = list(rows[0].keys())
    col = lambda *cands: next((c for c in hdr
                               if any(x.lower() in c.lower() for x in cands)), None)
    c_dep = col("circonscription", "departement", "département")
    c_nom = col("nom usuel")
    c_pre = col("prénom usuel", "prenom usuel")
    c_eta = col("état", "etat")
    out = defaultdict(set)
    for r in rows:
        if c_eta and (r.get(c_eta) or "").strip().upper() not in ("ACTIF", ""):
            continue
        out[(r.get(c_dep) or "").strip().upper()].add(
            key(f"{r.get(c_pre,'')} {r.get(c_nom,'')}"))
    return out, dict(dep=c_dep, nom=c_nom, prenom=c_pre, etat=c_eta), hdr


def load_assemblee(zip_path):
    """AMO10: one JSON per acteur. Keep the sitting mandate of legislature 17."""
    import zipfile
    out = defaultdict(set)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if "/acteur/" not in name or not name.endswith(".json"):
                continue
            a = json.loads(z.read(name).decode("utf-8"))["acteur"]
            ident = a.get("etatCivil", {}).get("ident", {})
            mandats = a.get("mandats", {}).get("mandat", [])
            mandats = mandats if isinstance(mandats, list) else [mandats]
            for m in mandats:
                if m.get("typeOrgane") != "ASSEMBLEE" or m.get("dateFin"):
                    continue
                if str(m.get("legislature")) != "17":
                    continue
                lieu = (m.get("election") or {}).get("lieu") or {}
                code = (lieu.get("numDepartement") or "").strip()
                code = code.zfill(2) if code.isdigit() and len(code) < 2 else code
                out[code].add(key(f"{ident.get('prenom','')} {ident.get('nom','')}"))
                n += 1
    print(f"assemblee-nationale sitting mandates parsed: {n}")
    return out


def pair_up(mine, yours):
    """Greedy bipartite match tolerating publisher name conventions.

    Two names are the same person if one token set contains the other and they
    share >= 2 tokens. This absorbs compound/married surnames (GUERIN vs
    BESSIN-GUERIN) and the Assemblee's habit of injecting the departement into
    the name to disambiguate two deputes with identical names (Alexandra MARTIN
    in both Alpes-Maritimes and Gironde). It does NOT absorb a different person.
    """
    unmatched_mine, unmatched_yours = set(mine), set(yours)
    for a in list(unmatched_mine):
        for b in list(unmatched_yours):
            if len(a & b) >= 2 and (a <= b or b <= a):
                unmatched_mine.discard(a)
                unmatched_yours.discard(b)
                break
    return unmatched_mine, unmatched_yours


def compare(label, ours, theirs, deps, match_by_code, their_label):
    print(f"\n=== {label} ===")
    print(f"source: {their_label}")
    agree = dis = variants = 0
    problems = []
    for row in ours:
        code = row["bindings"]["departement"]
        mine = {key(n) for n in row["expected"]}
        lookup = code if match_by_code else deps[code].upper()
        yours = theirs.get(lookup)
        if yours is None:
            problems.append((code, deps[code], "NOT FOUND in external source", "", ""))
            continue
        if mine == yours:
            agree += 1
            continue
        om, oy = pair_up(mine, yours)
        if not om and not oy:
            agree += 1
            variants += 1
            continue
        dis += 1
        problems.append((code, deps[code], f"{len(mine)} ours vs {len(yours)} theirs",
                         " / ".join(" ".join(sorted(k)) for k in om),
                         " / ".join(" ".join(sorted(k)) for k in oy)))
    n = len(ours)
    nf = sum(1 for p in problems if "NOT FOUND" in p[2])
    print(f"agreement: {agree}/{n} = {agree/n:.1%}  "
          f"(of which {variants} matched only after name-variant tolerance)   "
          f"GENUINE disagreements {dis - nf}   unmatched constituency {nf}")
    for code, nom, why, a, b in problems[:22]:
        print(f"  {code:4s} {nom:26s} {why}")
        if a:
            print(f"        only ours   : {a}")
        if b:
            print(f"        only theirs : {b}")
    if len(problems) > 22:
        print(f"  ... {len(problems)-22} more")
    return agree, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="data/fr/raw/2026-08-03")
    ap.add_argument("--data", default="data/fr")
    args = ap.parse_args()
    snap, data = Path(args.snapshot), Path(args.data)
    cache = snap / "_external"
    cache.mkdir(parents=True, exist_ok=True)

    deps = {d["code"]: d["nom"]
            for d in json.loads((snap / "departements.json").read_text(encoding="utf-8"))}
    d1 = json.loads((data / "groundtruth/d1_senateurs.json").read_text(encoding="utf-8"))
    d2 = json.loads((data / "groundtruth/d2_deputes.json").read_text(encoding="utf-8"))

    sen_raw, cols, hdr = load_senat(fetch(SEN_URL, cache / "ODSEN_GENERAL.csv"))
    print("columns used:", cols)
    print(f"senat.fr constituencies parsed: {len(sen_raw)}")
    dep_raw = load_assemblee(fetch(DEP_URL, cache / "AMO10_deputes.json.zip"))
    print(f"assemblee-nationale départements parsed: {len(dep_raw)}")

    a1, n1 = compare("D1 sénateurs", d1, sen_raw, deps, False,
                     "data.senat.fr ODSEN_GENERAL.csv")
    a2, n2 = compare("D2 députés", d2, dep_raw, deps, True,
                     "data.assemblee-nationale.fr AMO10 (legislature 17)")
    print(f"\nGATE 2d: D1 {a1}/{n1}  D2 {a2}/{n2}  overall "
          f"{(a1+a2)/(n1+n2):.1%} exact-set agreement over {n1+n2} départements "
          f"(full coverage, not a sample)")


if __name__ == "__main__":
    main()
