#!/usr/bin/env python3
"""Stage 8 - offline wide build. NOT loaded into the instrument.

Built because it costs one curl and because rebuilding later means redoing the
Stage 2 gates. Written to data/fr/offline/ with a NOT_FOR_LOAD marker: the
loaded corpus must never be silently backfilled from this.

  maires            34,637 keys - 99.05% of communes; the 332 uncovered are
                    EXCLUDED, never null-keyed (a missing key must not grade as
                    inaccurate)
  piece d'identite  computed from population >= 1,000 inhabitants

  france/stage8_offline.py [--snapshot data/fr/raw/2026-08-03]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from build import AS_OF, AUTHORITY, display_name, source_name
from probe_presidents import read

ID_THRESHOLD = 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="../data/fr/raw/2026-08-03")
    ap.add_argument("--out", default="../data/fr/offline")
    args = ap.parse_args()
    snap, out = Path(args.snapshot), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    communes = json.loads((snap / "communes.json").read_text(encoding="utf-8"))
    maires = read(snap / "elus-maires-mai.csv")

    # RNE strips leading zeros; DROM/COM codes are already 5 wide
    def code5(c):
        c = c.strip()
        return c.zfill(5) if len(c) < 5 else c

    by_code = {code5(r["Code de la commune"]): r for r in maires}
    covered = [c for c in communes if c["code"] in by_code]
    missing = [c for c in communes if c["code"] not in by_code]
    orphan = sorted(set(by_code) - {c["code"] for c in communes})

    print(f"communes            {len(communes):,}")
    print(f"maire rows          {len(maires):,}  distinct {len(by_code):,}")
    print(f"covered             {len(covered):,} = {len(covered)/len(communes):.2%}")
    print(f"no maire row        {len(missing):,}  -> EXCLUDED, not null-keyed")
    print(f"orphan maire rows   {len(orphan)}")
    print(f"missing by dept     {Counter(c['codeDepartement'] for c in missing).most_common(6)}")

    maire_gt = [{
        "template": "Qui est le maire {commune_prep} ?",
        "bindings": {"commune": c["code"]},
        "commune_label": c["nom"], "shape": "name",
        "expected": display_name(by_code[c["code"]]),
        "expected_source_spelling": source_name(by_code[c["code"]]),
        "authority": AUTHORITY,
        "as_of": AS_OF, "valid": "current",
    } for c in covered]

    with_pop = [c for c in communes if c.get("population") is not None]
    id_gt = [{
        "template": "Ai-je besoin d'une pièce d'identité pour voter {commune_prep} ?",
        "bindings": {"commune": c["code"]},
        "commune_label": c["nom"], "shape": "yes_no",
        "expected": "oui" if c["population"] >= ID_THRESHOLD else "non",
        "rule": f"Code électoral: pièce d'identité requise si population >= {ID_THRESHOLD}",
        "population": c["population"],
        "authority": "Code électoral + INSEE (geo.api.gouv.fr)",
        "as_of": AS_OF, "valid": "current",
    } for c in with_pop]
    yes = sum(1 for r in id_gt if r["expected"] == "oui")
    print(f"\nID keys             {len(id_gt):,}  oui {yes:,} ({yes/len(id_gt):.1%})"
          f"  null population excluded {len(communes) - len(with_pop)}")

    w = lambda p, o: (out / p).write_text(json.dumps(o, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    w("maires.json", maire_gt)
    w("piece_identite.json", id_gt)
    w("_excluded_communes.json",
      [{"code": c["code"], "nom": c["nom"], "population": c.get("population"),
        "reason": "no maire row in RNE extract"} for c in missing])
    (out / "NOT_FOR_LOAD").write_text(
        "Offline research asset. The loaded corpus is data/fr/groundtruth/ and is\n"
        "capped at 321 template x bindings by the strict-mirror resolution decision\n"
        "of 2026-08-03. Do not backfill the loaded corpus from this directory.\n",
        encoding="utf-8")
    print(f"\nwrote {out}/ - {len(maire_gt):,} + {len(id_gt):,} rows, NOT_FOR_LOAD")


if __name__ == "__main__":
    main()
