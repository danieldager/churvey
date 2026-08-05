#!/usr/bin/env python3
"""Stage 0 - pin the French ground-truth sources to an immutable dated snapshot.

Fetches once into data/fr/raw/<YYYY-MM-DD>/ and writes manifest.json recording
url, sha256, bytes and row count per file. Never re-fetches in place: a later
run with the same date refuses to overwrite, so a build can always be traced to
the exact bytes it was built from.

Sources:
  RNE (Repertoire National des Elus, Ministere de l'Interieur, data.gouv.fr)
      dataset 5c34c4d1634f4173183a64f1, refreshed QUARTERLY
  geo.api.gouv.fr (INSEE COG mirror), refreshed annually

  france/fetch_sources.py [--date YYYY-MM-DD]
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RNE = "https://static.data.gouv.fr/resources/repertoire-national-des-elus-1"

SOURCES = {
    # loaded set
    "elus-senateurs-sen.csv": f"{RNE}/20260505-152040/elus-senateurs-sen.csv",
    "elus-deputes-dep.csv": f"{RNE}/20260505-152059/elus-deputes-dep.csv",
    "elus-conseillers-departementaux-cd.csv": f"{RNE}/20260505-151941/elus-conseillers-departementaux-cd.csv",
    "elus-conseillers-regionaux-cr.csv": f"{RNE}/20260505-151954/elus-conseillers-regionaux-cr.csv",
    # collectivites territoriales uniques (Corse, Martinique, Guyane, Mayotte) have an
    # assemblee, not a conseil regional - their presidents are only in this file
    "elus-membres-assemblee-ma.csv": f"{RNE}/20260505-152008/elus-membres-dune-assemblee-ma.csv",
    "departements.json": "https://geo.api.gouv.fr/departements",
    "regions.json": "https://geo.api.gouv.fr/regions",
    # offline wide build only (Stage 8) - NOT loaded into the instrument
    "elus-maires-mai.csv": f"{RNE}/20260505-152119/elus-maires-mai.csv",
    "communes.json": "https://geo.api.gouv.fr/communes?fields=nom,code,population,codeDepartement",
}

# published figures, asserted at fetch time so a truncated download fails loud
EXPECTED_ROWS = {
    "elus-senateurs-sen.csv": 348,
    "elus-deputes-dep.csv": 577,
    "departements.json": 101,
    "regions.json": 18,
    "communes.json": 34969,
    "elus-maires-mai.csv": 34637,
}
TOLERANCE = 0.01


def rows(path):
    if path.suffix == ".json":
        return len(json.loads(path.read_text(encoding="utf-8")))
    with path.open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh, delimiter=";"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()

    out = Path("data/fr/raw") / args.date
    if out.exists():
        sys.exit(f"{out} already exists - snapshots are immutable, pick another --date")
    out.mkdir(parents=True)

    manifest, failures = {}, []
    for name, url in SOURCES.items():
        dest = out / name
        # curl, not urllib: this project's python hits SSL: CERTIFICATE_VERIFY_FAILED
        r = subprocess.run(
            ["curl", "-sS", "-f", "-L", "-D", "-", "-o", str(dest), url],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            failures.append(f"{name}: curl failed - {r.stderr.strip()}")
            continue
        http_date = next(
            (ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines()
             if ln.lower().startswith("date:")), None)
        n = rows(dest)
        manifest[name] = {
            "url": url,
            "http_date": http_date,
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "bytes": dest.stat().st_size,
            "rows": n,
        }
        expected = EXPECTED_ROWS.get(name)
        flag = ""
        if expected and abs(n - expected) / expected > TOLERANCE:
            failures.append(f"{name}: {n} rows, expected ~{expected}")
            flag = "  <-- OUT OF TOLERANCE"
        print(f"{name:42s} {n:6d} rows  {manifest[name]['bytes']:>9,} B{flag}")

    (out / "manifest.json").write_text(
        json.dumps({"fetched": args.date, "files": manifest}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    if failures:
        sys.exit("\nGATE 0 FAILED:\n  " + "\n  ".join(failures))
    print(f"\nGATE 0 PASSED - {len(manifest)} files pinned to {out}")


if __name__ == "__main__":
    main()
