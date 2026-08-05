#!/usr/bin/env python3
"""The chambers' own membership data - PRIMARY source for D1 and D2.

  senateurs  data.senat.fr ODSEN_GENERAL.csv                 (Senat)
  deputes    data.assemblee-nationale.fr AMO10 legislature 17 (Assemblee nationale)

Source decision (2026-08-03): for parliamentarians the chamber beats the
RNE. The RNE lists the *titulaire*; a member appointed to government is replaced
by their suppleant, and the chamber records whoever is actually sitting. The
correct answer to "who is my depute" is the sitting member, not the person on
leave to be a minister. The chambers also publish continuously, where the RNE
refreshes quarterly.

This does NOT extend to D3/R1: no source but the RNE publishes the presidents of
the conseils departementaux and regionaux, so those rows stay on the RNE.

REJECTED as a source: nosdeputes.fr (Regards Citoyens). Its /deputes/json still
serves the 2022-2024 legislature, dissolved June 2024 - every row carries
mandat_fin 2024-06-09. It would have "confirmed" our data and looked like a pass.
"""
import csv
import json
import subprocess
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

SEN_API = "https://www.senat.fr/api-senat/senateurs.json"   # live, 348 sitting, 120s cache
SEN_URL = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"  # nightly export
DEP_URL = ("https://data.assemblee-nationale.fr/static/openData/repository/17/amo/"
           "deputes_actifs_mandats_actifs_organes/"
           "AMO10_deputes_actifs_mandats_actifs_organes.json.zip")

PARTICLES = {"de", "du", "des", "la", "le", "les", "d", "l", "van", "von", "di", "da"}


def key(name):
    """Order-, accent-, particle- and punctuation-insensitive name key."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return frozenset(t for t in s.split() if t and t not in PARTICLES)


def slug(name):
    """Loose place-name key: the Senat writes 'Alpes de Haute-Provence' where
    INSEE writes 'Alpes-de-Haute-Provence'."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return "".join(c for c in s if c.isalnum())


def same_person(a, b):
    """True if two name keys are spelling variants of one person.

    One token set contains the other AND they share >= 2 tokens. Absorbs
    compound/married surnames (GUERIN / BESSIN-GUERIN), punctuation inside a
    surname (KBIDI / K/BIDI) and the Assemblee's habit of appending the
    departement to disambiguate two members with identical names. Does NOT
    absorb two different people - that distinction is what separates a spelling
    variant from a titulaire/suppleant substitution.
    """
    return len(a & b) >= 2 and (a <= b or b <= a)


def probable_variant(a, b):
    """Second, looser pass for the ONE-vs-ONE leftover case.

    Runs only when a binding has exactly one unmatched name on each side, so the
    two are already the only candidates. Requires a shared token of >= 5 chars,
    which catches a shared surname (VIGIER / VIGIER) or a shared given name where
    the surname is punctuated differently (Emeline KBIDI / Emeline K/Bidi), while
    rejecting a genuine substitution (BUFFET -> VIDAL, RIST -> LUBET, which share
    nothing). Every hit is written to _review_name_variants.json for confirmation -
    this is a heuristic, and it is allowed to be wrong in a way a human will see.
    """
    return any(len(t) >= 5 for t in (a & b))


def fetch(url, dest, force=False):
    if dest.exists() and not force:
        return dest
    r = subprocess.run(["curl", "-sS", "-f", "-L", "-m", "60", "-o", str(dest), url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fetch failed {url}: {r.stderr.strip()}")
    return dest


def senateurs(cache, deps_by_name):
    """-> {departement_code: [full name, ...]} for sitting senators."""
    path = fetch(SEN_URL, Path(cache) / "ODSEN_GENERAL.csv")
    lines = [l for l in path.read_text(encoding="latin-1").splitlines()
             if l and not l.startswith("%")]
    out, unmatched = defaultdict(list), defaultdict(int)
    for r in csv.DictReader(lines, delimiter=","):
        if (r.get("État") or "").strip().upper() != "ACTIF":
            continue
        circo = (r.get("Circonscription") or "").strip()
        code = deps_by_name.get(slug(circo))
        if not code:
            unmatched[circo] += 1
            continue
        out[code].append(f"{(r.get('Prénom usuel') or '').strip()} "
                         f"{(r.get('Nom usuel') or '').strip()}".strip())
    return dict(out), dict(unmatched)


def senateurs_live(cache, dep_codes):
    """-> {dept_code: [{name, serie}]} from the Senat's live endpoint.

    Preferred over ODSEN_GENERAL.csv: it lists exactly the 348 sitting senators
    (no ACTIF/ANCIEN filtering needed), is refreshed continuously rather than
    nightly, and carries the `serie` field - which is what says whether a seat is
    renewed on 27 September 2026. Serie 2 = 178 seats = the 2026 renewal.
    """
    path = fetch(SEN_API, Path(cache) / "senateurs_live.json", force=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    data = data if isinstance(data, list) else data[list(data)[0]]
    out, unmatched = defaultdict(list), defaultdict(int)
    for r in data:
        # circonscription is {"code": "21", "libelle": "Côte-d'Or", ...} - the code IS
        # the département code, so no place-name matching is needed here.
        circo = r.get("circonscription") or {}
        code = (circo.get("code") or "").strip()
        code = code.zfill(2) if code.isdigit() and len(code) < 2 else code
        if code not in dep_codes:
            unmatched[circo.get("libelle") or code] += 1
            continue
        out[code].append({"name": f"{r.get('prenom','')} {r.get('nom','')}".strip(),
                          "serie": str(r.get("serie") or "")})
    return dict(out), dict(unmatched)


def deputes(cache):
    """-> {departement_code: [full name, ...]} for sitting deputies."""
    path = fetch(DEP_URL, Path(cache) / "AMO10_deputes.json.zip")
    out = defaultdict(list)
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if "/acteur/" not in name or not name.endswith(".json"):
                continue
            a = json.loads(z.read(name).decode("utf-8"))["acteur"]
            ident = a.get("etatCivil", {}).get("ident", {})
            mandats = a.get("mandats", {}).get("mandat", [])
            mandats = mandats if isinstance(mandats, list) else [mandats]
            for m in mandats:
                if (m.get("typeOrgane") != "ASSEMBLEE" or m.get("dateFin")
                        or str(m.get("legislature")) != "17"):
                    continue
                lieu = (m.get("election") or {}).get("lieu") or {}
                code = (lieu.get("numDepartement") or "").strip()
                code = code.zfill(2) if code.isdigit() and len(code) < 2 else code
                out[code].append(f"{ident.get('prenom','')} {ident.get('nom','')}".strip())
    return dict(out)
