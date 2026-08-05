"""Draw a reproducible, geographically spread sample of communes for the France locality block.

DRAFT, not approved. The sampling rule is written here BEFORE the sample is inspected, so the
draw cannot be cherry-picked. Seeded and deterministic, so it reproduces exactly.

Frame: metropolitan France (96 departements incl. 2A/2B) plus the 5 DROM (971 Guadeloupe,
972 Martinique, 973 Guyane, 974 La Reunion, 976 Mayotte). 101 departements, the same set the
parked roster instrument uses.

Excluded and why: 975 Saint-Pierre-et-Miquelon, 977 Saint-Barthelemy, 978 Saint-Martin,
986 Wallis-et-Futuna, 987 Polynesie francaise, 988 Nouvelle-Caledonie, 984 TAAF,
989 Clipperton. Collectivites, not departements. Nouvelle-Caledonie in particular has
different electoral registration rules (service-public F34240), TAAF and Clipperton have no
permanent electorate.

Two competing objectives, resolved in this order:

1. SIZE, because the 1 000-inhabitant threshold is the only place a commune binding clearly
   earns its cost: below it an identity document is not obligatory at the bureau de vote, at
   and above it one is required (arrete du 16 novembre 2018, service-public F1361). Half the
   sample sits in the two bands either side of that line.
2. GEOGRAPHY, because the sample has to look like France on a map rather than a cluster.
   Within each size stratum, communes are chosen by farthest-point sampling: repeatedly take
   the candidate whose nearest already-chosen commune is furthest away. That fills holes
   instead of following population density, which a random or departement-quota draw does not.

The most-populous stratum is a forced census of the top N by population, so it clusters where
the cities are. It is drawn FIRST, and every later stratum spreads around it, so the small
communes fill the gaps the cities leave.

DROM get a fixed quota rather than entering the spatial spread, because they sit thousands of
km from metropolitan France and farthest-point sampling would otherwise load the sample with
them. The quota over-represents them (10 of 200 = 5%, against 129 of 34 875 = 0.37% of the
frame) and that is deliberate, for map coverage. Reweight before reporting any rate.

Source: geo.api.gouv.fr /communes, snapshotted to data/fr/raw/2026-08-04/geo_communes.json,
sha256 8b603792274c49fbccccb1f899a297856b0bee0c6c016867b7de1389f11066fc, fetched 2026-08-04.
"""

import csv
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data/fr/raw/2026-08-04/geo_communes.json"
RNE = ROOT / "data/fr/raw/2026-08-04/rne_maires_full.csv"
LANNUAIRE_ALL = ROOT / "data/fr/raw/2026-08-04/lannuaire_mairies_all.json"
INSEE_POP = ROOT / "data/fr/raw/2026-08-04/insee_populations_legales_2023.csv"

# Seed is the date of the 1st tour. Fixed and documented so the draw is reproducible.
SEED = 20270418

METRO_EXTRA = {"2A", "2B"}
DROM = {"971", "972", "973", "974", "976"}

# (name, population predicate, share of the metropolitan quota)
STRATA = [
    ("most_populous", lambda p: p >= 100_000, 0.20),
    ("just_below_1000", lambda p: 500 <= p < 1_000, 0.25),
    ("just_above_1000", lambda p: 1_000 <= p < 2_000, 0.25),
    ("very_low", lambda p: p < 500, 0.15),
    ("mid", lambda p: 2_000 <= p < 100_000, 0.15),
]

DROM_QUOTA = 10  # 2 per DROM


def rne_covered():
    """Commune codes for which the RNE records a maire.

    The RNE stores departements 01-09 unpadded, so 01001 appears as 1001.
    Source: RNE elus-maires-mai.csv, refreshed 2026-05-05,
    sha256 c7d9748be7557f71e3323844117b3591477b783c1a6dd2da51c42241b5982782.
    """
    rows = list(csv.reader(RNE.read_text(encoding="utf-8", errors="replace")
                           .replace("\r\n", "\n").splitlines(), delimiter=";"))
    i = rows[0].index("Code de la commune")
    return {(r[i].zfill(5) if r[i].isdigit() else r[i]) for r in rows[1:]}


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def resolve_mairie(records, commune_nom):
    """Pick the one mairie that serves a commune, or None if genuinely ambiguous.

    lannuaire lists 35 803 mairie records for 35 723 communes. 61 communes carry more than
    one, almost all of them communes nouvelles that kept an entry per former commune.

    Resolution, in order:
      1. drop "Mairie annexe" and "Mairie deleguee" records. If that leaves nothing, the
         commune has only a deleguee or annexe listed and is treated as unresolved rather
         than answered with an office that may not be where registration happens.
      2. collapse rows that are the same name modulo case, accents and punctuation. Five
         communes carry pure duplicates this way, e.g. "TESSY-BOCAGE" beside "Tessy-Bocage"
         and "Etinehem-Mericourt" beside "Etinehem-Mericourt" with different accents.
      3. if more than one remains, keep the record whose name matches the commune's own.

    Three communes survive all three rules: communes nouvelles whose name concatenates the
    former communes so neither mairie matches it. 03168 Meaulne-Vitray (Meaulne / Vitray),
    35163 Luitre-Dompierre (Dompierre-du-Chemin / Luitre) and 71279 Le Rousset-Marizy
    (Le Rousset / Marizy). They are excluded from the frame rather than guessed at.
    """
    main = [r for r in records
            if not norm_name(r["nom"]).startswith(("mairieannexe", "mairiedeleguee"))]
    if not main:
        return None
    seen, deduped = set(), []
    for r in main:
        k = norm_name(r["nom"])
        if k not in seen:
            seen.add(k)
            deduped.append(r)
    if len(deduped) == 1:
        return deduped[0]
    exact = [r for r in deduped
             if norm_name(r["nom"].split(" - ", 1)[-1]) == norm_name(commune_nom)]
    return exact[0] if len(exact) == 1 else None


def unambiguous_id_answer():
    """Commune codes where the identity-document answer is the same either way.

    Code electoral R60 sets the threshold at "communes de 1 000 habitants et plus" and does
    NOT say which population figure that means. INSEE publishes two: the population municipale
    and the population totale (municipale plus the population comptee a part), and says of the
    latter that "la population totale est une population de reference a laquelle de tres
    nombreux textes legislatifs ou reglementaires font reference".

    168 of 34 855 communes (0.48%) fall between the two, so their answer depends on a reading
    of R60 that R60 does not supply. Rather than pick a reading, those communes are excluded
    from the frame. Every commune that survives gives the same answer under either figure, so
    no answer in this instrument turns on the question.

    Source: INSEE populations legales millesime 2023, published 2025-12-18, file
    donnees_communes.csv, sha256
    ccfe782e04ebde04a1706214157b288a0d055eb3ab913ff9f7bab5a3571f67ab.
    Communes absent from that file (Mayotte, and Paris/Lyon/Marseille which it lists by
    arrondissement) are kept only if they clear the threshold by a wide margin.
    """
    ok = set()
    rows = list(csv.reader(INSEE_POP.read_text(encoding="utf-8", errors="replace")
                           .replace("\r\n", "\n").splitlines(), delimiter=";"))
    i = {h: n for n, h in enumerate(rows[0])}
    for r in rows[1:]:
        if len(r) != len(rows[0]):
            continue
        mun = int(r[i["PMUN"]].replace(" ", ""))
        tot = int(r[i["PTOT"]].replace(" ", ""))
        if (mun >= ID_THRESHOLD) == (tot >= ID_THRESHOLD):
            ok.add(r[i["COM"]])
    return ok


ID_THRESHOLD = 1_000
WIDE_MARGIN = 1_200  # for the 20 communes the INSEE file does not list individually

_RNE = None
_MAIRIE_OK = None
_POP_OK = None


def mairie_resolvable():
    """Commune codes whose mairie resolves to exactly one record."""
    recs = {}
    for r in json.load(open(LANNUAIRE_ALL)):
        if r.get("code_insee_commune"):
            recs.setdefault(str(r["code_insee_commune"]), []).append(r)
    return recs


def in_frame(c):
    """Eligibility, applied BEFORE the draw so no commune is ever swapped out afterwards.

    A commune enters the frame only if all three questions can be answered from an official
    source. In practice the binding condition is the RNE: 305 of the 34 875 communes in the
    territorial frame (0.87%) have no maire row, because the RNE holds their conseil municipal
    but has not recorded who holds the maire function. Guadeloupe is the worst affected, with
    26 maire rows against 32 communes.

    Filtering before the draw rather than replacing afterwards keeps the sample a clean
    probability sample of the eligible frame. It does bias that frame very slightly against
    places with poor RNE data entry, which is stated rather than hidden.
    """
    global _RNE, _MAIRIE_OK, _POP_OK
    if _RNE is None:
        _RNE = rne_covered()
        _MAIRIE_OK = mairie_resolvable()
        _POP_OK = unambiguous_id_answer()
    d = c.get("codeDepartement") or ""
    territorial = (len(d) == 2 and d.isdigit()) or d in METRO_EXTRA or d in DROM
    if not (territorial and c["code"] in _RNE):
        return False
    if c["code"] in _POP_OK:
        pass
    elif (c.get("population") or 0) < WIDE_MARGIN:
        return False
    recs = _MAIRIE_OK.get(c["code"], [])
    return bool(recs) and resolve_mairie(recs, c["nom"]) is not None


def lonlat(c):
    return c["centre"]["coordinates"]


def dist2(a, b):
    """Squared equirectangular distance in km. Adequate at France's latitudes."""
    (lo1, la1), (lo2, la2) = a, b
    x = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
    y = math.radians(la2 - la1)
    return (6371.0 ** 2) * (x * x + y * y)


def farthest_point(pool, k, already):
    """Pick k from pool, each time taking the candidate furthest from everything chosen.

    Deterministic. `already` is the list of points chosen so far, including other strata,
    so strata spread around each other rather than each clustering independently.
    """
    chosen, pts = [], [lonlat(c) for c in already]
    remaining = list(pool)
    for _ in range(min(k, len(remaining))):
        if not pts:
            best = remaining[0]  # pool is pre-shuffled, so this is seeded, not positional
        else:
            best = max(remaining, key=lambda c: min(dist2(lonlat(c), p) for p in pts))
        chosen.append(best)
        pts.append(lonlat(best))
        remaining.remove(best)
    return chosen


def repair_departement_coverage(picked, metro):
    """Guarantee every departement in the frame appears at least once.

    Farthest-point sampling optimises distance, so it skips departements that are small in
    area even when they are dense in people (the petite couronne especially). This swaps the
    most spatially redundant member of the largest stratum for a commune from each missing
    departement, keeping every stratum count exactly as drawn.
    """
    covered = {c["codeDepartement"] for c in picked}
    missing = sorted({c["codeDepartement"] for c in metro} - covered)
    for dep in missing:
        pool = [c for c in metro if c["codeDepartement"] == dep]
        if not pool:
            continue
        counts = Counter(c["stratum"] for c in picked)
        # Prefer a stratum this departement can actually supply, biggest first.
        options = [(s, n) for s, n in counts.most_common()
                   if s not in ("drom", "most_populous")
                   and any(pred(c.get("population") or 0)
                           for name, pred, _ in STRATA if name == s
                           for c in pool)]
        if not options:
            continue
        stratum = options[0][0]
        pred = next(p for name, p, _ in STRATA if name == stratum)
        cand = max((c for c in pool if pred(c.get("population") or 0)),
                   key=lambda c: c.get("population") or 0)
        # Drop whichever member of that stratum sits closest to another sample member, but
        # never one that is the only representative of its own departement: evicting it would
        # simply move the hole somewhere else.
        dep_counts = Counter(c["codeDepartement"] for c in picked)
        members = [c for c in picked if c["stratum"] == stratum
                   and dep_counts[c["codeDepartement"]] > 1]
        if not members:
            continue
        others = [lonlat(c) for c in picked]
        victim = min(members, key=lambda c: sorted(
            dist2(lonlat(c), p) for p in others)[1])  # [1] skips itself at distance 0
        picked.remove(victim)
        picked.append({**cand, "stratum": stratum})
    return picked


def draw(communes, n_total=200):
    rng = random.Random(SEED)
    metro = [c for c in communes if c["codeDepartement"] not in DROM]
    drom = [c for c in communes if c["codeDepartement"] in DROM]

    picked = []

    # DROM first, fixed quota, spread by size within each territory.
    per = DROM_QUOTA // len(DROM)
    for dep in sorted(DROM):
        pool = sorted([c for c in drom if c["codeDepartement"] == dep],
                      key=lambda c: c.get("population") or 0)
        if not pool:
            continue
        take = [pool[0], pool[-1]][:per] if per <= 2 else pool[:per]
        for c in take:
            picked.append({**c, "stratum": "drom"})

    n_metro = n_total - len(picked)
    for name, pred, share in STRATA:
        k = round(n_metro * share)
        pool = [c for c in metro if pred(c.get("population") or 0)]
        if name == "most_populous":
            chosen = sorted(pool, key=lambda c: -(c["population"]))[:k]
        else:
            rng.shuffle(pool)
            chosen = farthest_point(pool, k, picked)
        for c in chosen:
            picked.append({**c, "stratum": name})

    return repair_departement_coverage(picked, metro)


def ascii_map(sample, width=68, height=26):
    """Metropolitan-only eyeball check that the draw covers the map."""
    pts = [lonlat(c) for c in sample if c["codeDepartement"] not in DROM]
    lo = [p[0] for p in pts]
    la = [p[1] for p in pts]
    lo0, lo1, la0, la1 = -5.2, 9.6, 41.3, 51.1  # metropolitan bounding box
    grid = [[" "] * width for _ in range(height)]
    for x, y in zip(lo, la):
        col = int((x - lo0) / (lo1 - lo0) * (width - 1))
        row = int((la1 - y) / (la1 - la0) * (height - 1))
        if 0 <= col < width and 0 <= row < height:
            grid[row][col] = "#" if grid[row][col] != " " else "o"
    return "\n".join("  |" + "".join(r) + "|" for r in grid)


def profile(sample, frame):
    deps = {c["codeDepartement"] for c in sample}
    regs = {c["codeRegion"] for c in sample}
    fd = {c["codeDepartement"] for c in frame}
    fr = {c["codeRegion"] for c in frame}
    below = sum(1 for c in sample if (c.get("population") or 0) < 1_000)
    # 1-degree grid cells occupied, metropolitan only, as a spread measure
    cells = {(round(lonlat(c)[0]), round(lonlat(c)[1]))
             for c in sample if c["codeDepartement"] not in DROM}
    print(f"  n                     {len(sample)}")
    print(f"  departements covered  {len(deps)} / {len(fd)}")
    print(f"  regions covered       {len(regs)} / {len(fr)}")
    print(f"  1-degree cells hit    {len(cells)} (metropolitan France spans ~90)")
    print(f"  under 1 000 hab       {below} ({100*below/len(sample):.0f}%), frame is 71%")
    print(f"  smallest              {min(c['population'] for c in sample)} hab")
    print("  by stratum            " + ", ".join(
        f"{k} {v}" for k, v in Counter(c["stratum"] for c in sample).items()))


if __name__ == "__main__":
    frame = [c for c in json.load(open(SNAPSHOT)) if in_frame(c)]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    sample = draw(frame, n)

    print(f"frame: {len(frame)} communes\n")
    print(f"N = {n}")
    profile(sample, frame)
    print("\n  metropolitan spread (o = 1 commune, # = 2+):\n")
    print(ascii_map(sample))

    out = ROOT / "data/fr/sample/communes_sample_draft.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(
        {
            "_status": "DRAFT, not approved. Drawn 2026-08-04.",
            "rule": "france/sample_communes.py, seed 20270418, farthest-point spatial spread",
            "source": "geo.api.gouv.fr /communes, snapshot data/fr/raw/2026-08-04/geo_communes.json"
                      " sha256 8b603792274c49fbccccb1f899a297856b0bee0c6c016867b7de1389f11066fc",
            "not_representative": "Stratified for discrimination around the 1 000-hab identity"
                                  " threshold, and DROM are over-quota for map coverage."
                                  " Reweight to the frame before reporting any rate.",
            "n": len(sample),
            "communes": sample,
        },
        open(out, "w"), ensure_ascii=False, indent=2,
    )
    print(f"\nwrote {out}")
