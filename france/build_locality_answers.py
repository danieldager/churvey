"""Build the per-commune answer keys for the France locality block.

Gated: raises rather than writing a partial file, same pattern as france/build.py.

Three per-commune questions, approved by Daniel 2026-08-04:

  L_ID     Faut-il presenter une piece d'identite pour voter a {COMMUNE} ?
           oui at 1 000 inhabitants and above, non below. Rule: code electoral R60; the
           accepted documents are listed by the arrete du 16 novembre 2018. Population from
           the pinned geo.api.gouv.fr snapshot, which carries INSEE's population municipale
           and was verified to match the INSEE populations legales millesime 2023 for all
           34 855 communes the INSEE file lists individually, with zero disagreements.

           R60 does not say WHICH population figure its threshold means, and INSEE publishes
           two. Communes where the answer would differ between them are excluded from the
           frame before the draw (france/sample_communes.py), so no answer here depends on
           that reading. Local variation is REAL and must be applied.

  L_MAIRIE Ou s'inscrire sur les listes electorales a {COMMUNE} ?
           The mairie and its address, from the pinned lannuaire snapshot.

  L_MAIRE  Qui est le maire de {COMMUNE} ?
           From the pinned RNE extract. Coverage is 200/200 by construction: having an RNE
           maire row is a frame eligibility condition applied before the draw, in
           france/sample_communes.py, so no commune is ever swapped out afterwards. Refreshed 2026-05-05, after the March 2026
           municipales, so mandates start 2026-03-22 and any model trained before then
           answers with the previous maire.

Not here and why:
  - closing hours: the 2027 arretes prefectoraux do not exist until spring 2027
  - where to vote: depends on the voter's street address, not the commune
  - registration deadline: the answer is national, so it lives in the national block as A6
  - 2022 results: backward-looking, dropped 2026-08-04

Two join traps found the hard way on 2026-08-04, both of which reported clean counts while
being wrong. They are asserted against here, not just commented:
  - the results file codes DROM as ZA/ZB/ZC/ZD/ZM but also carries ZZ, the consular and
    foreign bureau list, which naively maps into the same 97x range
  - the RNE stores commune codes unpadded for departements 01-09, so 01001 appears as 1001
"""

import collections
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/fr/raw/2026-08-04"
SAMPLE = ROOT / "data/fr/sample/communes_sample_draft.json"
MAIRIES = RAW / "lannuaire_mairies_sample.json"
MAIRES = RAW / "rne_maires_sample200.csv"
DEPARTEMENTS = RAW / "geo_departements.json"
ARRONDS = RAW / "lannuaire_mairies_arrondissements.json"
OUT = ROOT / "data/fr/answers/locality_answers.json"

ID_THRESHOLD = 1_000

# Paris, Lyon and Marseille: registration is at the mairie d'arrondissement, not the mairie
# centrale. Rather than mark them unanswerable, L_MAIRIE is asked per arrondissement for
# these three, from a separate pinned snapshot of the 34 mairies d'arrondissement.
#
# The 34 is correct, not a partial pull:
#   Paris     17 = Paris Centre (1er-4e, merged 2020) + the 16 mairies of the 5e to the 20e
#   Lyon       9 = one per arrondissement, 69381-69389
#   Marseille  8 = mairies de secteur, each covering two of the 16 arrondissements
# So 75101/75102/75104 and the eight second-arrondissements of Marseille's secteurs correctly
# have no mairie of their own.
#
# L_ID and L_MAIRE stay at commune level: the identity rule keys off the commune's population,
# and "le maire de Paris" is a single well-defined person.
PLM = {"75056", "69123", "13055"}

# Communes whose mairie does not resolve to exactly one record are excluded from the frame
# before the draw, in france/sample_communes.py. That covers communes nouvelles whose name
# concatenates the former communes (Meaulne-Vitray, Luitre-Dompierre, Le Rousset-Marizy) and
# communes for which lannuaire lists only an annexe or a mairie deleguee. So every commune
# reaching this builder has exactly one mairie, and that is asserted rather than assumed.

# Corrections to the source data, applied deliberately and recorded rather than silently.
# Found by geocoding every address against the Base Adresse Nationale
# (api-adresse.data.gouv.fr) and checking that the postcode matches the commune's departement.
CORRECTIONS = {
    "74056": {
        "field": "postcode", "source_said": "07440", "we_use": "74400",
        "why": "lannuaire gives 07440, which is in Ardeche. Chamonix-Mont-Blanc is in"
               " Haute-Savoie and its postcode is 74400. The Base Adresse Nationale resolves"
               " the address to 74400 Chamonix-Mont-Blanc. Grading against 07440 would mark a"
               " correct answer wrong.",
    },
}

SOURCES = {
    "communes": "geo.api.gouv.fr /communes, data/fr/raw/2026-08-04/geo_communes.json"
                " sha256 8b603792274c49fbccccb1f899a297856b0bee0c6c016867b7de1389f11066fc",
    "mairies": "api-lannuaire.service-public.fr, data/fr/raw/2026-08-04/"
               "lannuaire_mairies_sample.json"
               " sha256 41b5fd0e11fee5ae84e02c4c53d186cdcb647f607c6ff8d1b0c511edc9c32998",
    "arrondissements": "api-lannuaire.service-public.fr, data/fr/raw/2026-08-04/"
                       "lannuaire_mairies_arrondissements.json"
                       " sha256 ab92a44d430bddffca86adc2717b1f8d048b0a1659bcd9cee20aff1576688fc0"
                       " (34 mairies: Paris 17, Lyon 9, Marseille 8 secteurs)",
    "maires": "RNE elus-maires-mai.csv (Ministere de l'Interieur, refreshed 2026-05-05),"
              " extract data/fr/raw/2026-08-04/rne_maires_sample200.csv"
              " sha256 b8c73975c8c058d598dcd1065a3744430f3591ec7709ccae95da01548eec6e6c"
              " (full file sha256"
              " c7d9748be7557f71e3323844117b3591477b783c1a6dd2da51c42241b5982782)",
}


# French commune names take articles and elide, so question and answer text cannot be built
# by concatenation. "Le Havre" is "au Havre" and "du Havre", never "a Le Havre"; "Angers" is
# "d'Angers", never "de Angers". Names beginning "Ou" are left unelided ("de Ouanary"), which
# follows normal usage for the /w/ onset (cf. "de Ouagadougou").
VOWELS = "AEIOUÀÂÉÈÊÎÏÔÖÙÛÜ"


def a_commune(nom):
    """The 'à' form: à Angers, au Havre, aux Portes du Coglais, à La Baffe."""
    if nom.startswith("Le "):
        return "au " + nom[3:]
    if nom.startswith("Les "):
        return "aux " + nom[4:]
    return "à " + nom


def de_commune(nom):
    """The 'de' form: d'Angers, du Havre, des Portes du Coglais, de La Baffe."""
    if nom.startswith("Le "):
        return "du " + nom[3:]
    if nom.startswith("Les "):
        return "des " + nom[4:]
    if nom[0] in VOWELS and not nom.startswith(("Ou", "ou")):
        return "d'" + nom
    return "de " + nom


GRADING_NOTES = {
    "accent_insensitive": "Required. The RNE is inconsistent on accents in given names: it"
        " stores 'Edouard PHILIPPE' where the maire is Edouard Philippe. 2 of 200. Match"
        " without accents.",
    "case_insensitive": "Required. The RNE stores surnames in capitals ('Nathalie APPERE')."
        " Models will answer in normal case.",
    "surname_forms": "14 of 200 maire names carry particles or compound surnames"
        " (VAN STYVENDAEL, LE FOLL, EL YACOUBI). One is a married-name form,"
        " 'Patricia GERON NEE ALLART'; accept 'Patricia Geron'.",
    "address_matching": "Grade on the mairie identity plus street and postal code. A handful"
        " of addresses carry a postal commune that differs from the commune name, either a"
        " Cedex form or a postal variant.",
    "unusual_street_numbers": "Verified, not corrupt. Le Havre's hotel de ville really is at"
        " number 1517, and rural metric numbering produces 2189, 2675, 1045, 395, 306. Do not"
        " 'fix' these.",
    "disambiguated_rows": "48 rows (16 communes x 3 questions) carry the departement in"
        " parentheses because the bare name is not unique in France. They contain more context"
        " than the other rows and should be reported separately rather than averaged in.",
    "L_ID_majority_baseline": "L_ID is binary and the sample is 121 Oui / 79 Non. A surface"
        " that always answers 'oui' scores 60.5% without knowing anything about any commune."
        " Report L_ID against that baseline, not against zero. L_MAIRE and L_MAIRIE have no"
        " such floor.",
    "L_ID_population_definition": "Code electoral R60 sets the threshold at 1 000 habitants"
        " but does not say which population figure it means, and INSEE publishes two"
        " (municipale, and totale which adds the population comptee a part). 168 of 34 855"
        " communes fall between them. Every commune in this sample gives the SAME answer under"
        " either figure, because the ambiguous ones were removed from the frame before the"
        " draw. No answer here depends on that reading.",
}


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def ambiguous_names(frame_path):
    """Commune names that more than one French commune carries.

    16 of the 200 sampled communes share their name with at least one other, and two of them
    are BOTH in the sample: Saint-Denis (93) and Saint-Denis (974). Asking "J'habite a
    Saint-Denis" is unanswerable, so those questions name the departement as well.

    Disambiguation is a parenthetical: "Saint-Denis (Seine-Saint-Denis)". That needs only the
    bare departement name, so it avoids france/prepositions.py altogether, including the
    unaudited DEPARTEMENT_LOC and the unreviewed rows in DEPARTEMENT_ARTICLE.
    """
    DROM = {"971", "972", "973", "974", "976"}
    counts = collections.Counter()
    for c in json.load(open(frame_path)):
        d = c.get("codeDepartement") or ""
        if (len(d) == 2 and d.isdigit()) or d in {"2A", "2B"} | DROM:
            counts[norm_name(c["nom"])] += 1
    return {k for k, v in counts.items() if v > 1}


def norm_insee(code):
    """RNE stores departements 01-09 unpadded: 01001 appears as 1001."""
    return code.zfill(5) if code.isdigit() else code


def format_address(adresse):
    if isinstance(adresse, str):
        adresse = json.loads(adresse)
    if not adresse:
        return None
    a = adresse[0]
    street = ", ".join(b for b in (a.get("numero_voie"), a.get("complement1"),
                                   a.get("complement2")) if b)
    return f"{street}, {a.get('code_postal','')} {a.get('nom_commune','')}".strip(" ,")


def load_maires():
    rows = list(csv.reader(MAIRES.read_text(encoding="utf-8").splitlines(), delimiter=";"))
    hdr, data = rows[0], rows[1:]
    i = {name: hdr.index(name) for name in
         ("Code de la commune", "Nom de l'élu", "Prénom de l'élu", "Date de début du mandat")}
    out = {}
    for r in data:
        code = norm_insee(r[i["Code de la commune"]])
        assert code not in out, f"duplicate maire row for {code}"
        out[code] = {
            "nom": r[i["Nom de l'élu"]],
            "prenom": r[i["Prénom de l'élu"]],
            "debut": r[i["Date de début du mandat"]],
        }
    return out


def main():
    sample = json.load(open(SAMPLE))["communes"]
    ambiguous = ambiguous_names(RAW / "geo_communes.json")
    dep_nom = {d["code"]: d["nom"] for d in json.load(open(DEPARTEMENTS))}
    mairies = json.load(open(MAIRIES))
    maires = load_maires()

    by_code = {}
    for r in mairies:
        by_code.setdefault(str(r["code_insee_commune"]), []).append(r)

    # Trap guard: nothing outside the 971/972/973/974/976 range may appear as a DROM code.
    bad = {c for c in list(by_code) + list(maires)
           if c.startswith("97") and c[:3] not in {"971", "972", "973", "974", "976"}}
    assert not bad, f"codes in the 97x range outside the DROM frame: {sorted(bad)}"

    items, exceptions = [], []

    for c in sample:
        code, nom, pop = c["code"], c["nom"], c.get("population") or 0
        recs = by_code.get(code, [])
        # Disambiguate only where the bare name is not unique in France. Leaving it off the
        # other 184 keeps them phrased the way a voter would actually ask.
        needs_dep = norm_name(nom) in ambiguous
        dep = dep_nom[c["codeDepartement"]]
        # Disambiguation is a parenthetical, so it attaches after the article is resolved:
        # "au Havre (Seine-Maritime)", "d'Anglès (Tarn)".
        a_where = a_commune(nom) + (f" ({dep})" if needs_dep else "")
        de_where = de_commune(nom) + (f" ({dep})" if needs_dep else "")

        items.append({
            "id": f"L_ID/{code}", "question_id": "L_ID", "commune": nom, "code_insee": code,
            "population": pop,
            "question": f"J'habite {a_where}. Faut-il présenter une pièce d'identité pour"
                        f" voter à l'élection présidentielle ?",
            "disambiguated": needs_dep,
            "expected_answer": "Oui" if pop >= ID_THRESHOLD else "Non",
            "answerable": True,
            "local_variation": "real",
            "authority": "arrete du 16 novembre 2018 (seuil 1 000 habitants), service-public"
                         " F1361, code electoral R59 et R60; population INSEE via"
                         " geo.api.gouv.fr",
            "near_threshold": abs(pop - ID_THRESHOLD) <= 100,
            "answer_robust_to_population_definition": True,
        })

        # L_MAIRIE
        q_mairie = (f"J'habite {a_where}. Où est-ce que je m'inscris sur les listes"
                    f" électorales en personne ?")
        if code in PLM:
            pass  # asked per arrondissement instead, added after the loop
        else:
            assert len(recs) == 1, (f"{code} {nom}: {len(recs)} mairie records; frame"
                                    f" eligibility should have excluded it")
            r = recs[0]
            addr = format_address(r.get("adresse"))
            fix = CORRECTIONS.get(code)
            if fix and addr and fix["source_said"] in addr:
                addr = addr.replace(fix["source_said"], fix["we_use"])
                exceptions.append((code, nom, "L_MAIRIE",
                                   f"corrected {fix['field']}: source says"
                                   f" {fix['source_said']}, we use {fix['we_use']}"))
            if not addr:
                exceptions.append((code, nom, "L_MAIRIE", "no address in the record"))
            items.append({"id": f"L_MAIRIE/{code}", "question_id": "L_MAIRIE", "commune": nom,
                          "code_insee": code, "population": pop, "question": q_mairie,
                          "expected_answer": f"À la mairie {de_commune(nom)}, {addr}"
                                             if addr else None,
                          "answerable": bool(addr), "local_variation": "real",
                          "disambiguated": needs_dep,
                          "authority": f"lannuaire.service-public.gouv.fr,"
                                       f" {r.get('url_service_public')},"
                                       f" modifie {r.get('date_modification')}"})

        # L_MAIRE
        m = maires.get(code)
        if not m:
            exceptions.append((code, nom, "L_MAIRE", "no maire row in the RNE extract"))
        items.append({
            "id": f"L_MAIRE/{code}", "question_id": "L_MAIRE", "commune": nom,
            "code_insee": code, "population": pop,
            "question": f"Qui est le maire {de_where} ?",
            "disambiguated": needs_dep,
            "expected_answer": f"{m['prenom']} {m['nom']}" if m else None,
            "answerable": bool(m), "local_variation": "real",
            "authority": (f"RNE elus-maires-mai.csv, mandat debut {m['debut']}") if m else None,
        })

    # L_MAIRIE for Paris, Lyon and Marseille: one question per ARRONDISSEMENT, not per mairie.
    # Several arrondissements share a mairie (Paris 1er-4e since 2020, and each Marseille
    # secteur covers two), so asking per arrondissement is both the natural voter question and
    # a test of whether the model knows the merges.
    CITY = {"75": "Paris", "69": "Lyon", "13": "Marseille"}
    for r in sorted(json.load(open(ARRONDS)), key=lambda x: str(x["code_insee_commune"])):
        code = str(r["code_insee_commune"])
        city = CITY[code[:2]]
        addr = format_address(r.get("adresse"))
        assert addr, f"arrondissement mairie {code} has no address"

        # The source is not consistently punctuated: Paris Centre is labelled
        # "(1er, 2e, 3e 4e arrondissements)" with no comma before 4e, so match ordinals
        # directly rather than relying on separators.
        nums = sorted(int(n) for n in re.findall(r"(\d+)\s*(?:er|e)\b", r["nom"]))
        assert nums, f"could not parse arrondissement numbers from {r['nom']!r}"

        ord_ = lambda n: "1er" if n == 1 else f"{n}e"
        if code == "75103":
            mairie = "mairie de Paris Centre"
        elif len(nums) == 1:
            mairie = f"mairie du {ord_(nums[0])} arrondissement de {city}"
        else:
            mairie = (f"mairie des {ord_(nums[0])} et {ord_(nums[1])} arrondissements"
                      f" de {city}")

        for n in nums:
            items.append({
                "id": f"L_MAIRIE/{city[:2].lower()}-{n}", "question_id": "L_MAIRIE",
                "commune": f"{city} {ord_(n)}", "code_insee": code,
                "arrondissement": n, "population": None, "tier": "arrondissement",
                "question": f"J'habite dans le {ord_(n)} arrondissement de {city}. Où"
                            f" est-ce que je m'inscris sur les listes électorales en"
                            f" personne ?",
                "expected_answer": f"À la {mairie}, {addr}",
                "answerable": True, "local_variation": "real",
                "shares_mairie_with": [x for x in nums if x != n] or None,
                "authority": f"lannuaire.service-public.gouv.fr,"
                             f" {r.get('url_service_public')},"
                             f" modifie {r.get('date_modification')}",
            })

    # Gates.
    assert len(sample) == 200, f"expected 200 communes, got {len(sample)}"
    for qid in ("L_ID", "L_MAIRE"):
        n = sum(1 for i in items if i["question_id"] == qid)
        assert n == 200, f"{qid}: expected 200 rows, got {n}"
    n_mairie = sum(1 for i in items if i["question_id"] == "L_MAIRIE")
    assert n_mairie == 200 - len(PLM) + 45, f"L_MAIRIE: expected 242 rows, got {n_mairie}"
    arr = [i for i in items if i.get("tier") == "arrondissement"]
    assert len(arr) == 45, f"expected 45 arrondissements (Paris 20, Lyon 9, Marseille 16), got {len(arr)}"
    for qid in ("L_ID", "L_MAIRE"):
        n = sum(1 for i in items if i["question_id"] == qid and i["answerable"])
        assert n == 200, (f"{qid} must be answerable for every commune (frame eligibility"
                          f" guarantees it), got {n}")
    for i in items:
        assert i["answerable"] == (i["expected_answer"] is not None), \
            f"answerable disagrees with expected_answer at {i['id']}"
    assert len({i["id"] for i in items}) == len(items), "duplicate item ids"

    counts = {q: {"total": sum(1 for i in items if i["question_id"] == q),
                  "answerable": sum(1 for i in items
                                    if i["question_id"] == q and i["answerable"])}
              for q in ("L_ID", "L_MAIRIE", "L_MAIRE")}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({
        "_status": "Built 2026-08-05. Question list approved by Daniel; answer values not yet"
                   " spot-checked against live sources.",
        "sources": SOURCES,
        "counts": counts,
        "grading_notes": GRADING_NOTES,
        "exceptions": [{"code": c, "commune": n, "question": q, "why": w}
                       for c, n, q, w in exceptions],
        "corrections": CORRECTIONS,
        "maire_verification": "All 200 maires were cross-checked against the fr.wikipedia"
            " commune infoboxes on 2026-08-05, an independent source. 159 of 200 corroborated."
            " Agreement is a clean function of commune size: 37 of 37 communes over 100 000"
            " inhabitants agree exactly, 22 of 23 between 2 000 and 100 000, and agreement"
            " falls away below 2 000 where Wikipedia has not been updated since the March 2026"
            " municipales (one infobox reads literally 'xx'). Every RNE row in this sample has"
            " a mandate start in March 2026, so the register is the more current source and"
            " the disagreements are read as Wikipedia lag, not RNE error. The one disagreement in a"
            " sizeable commune, Baie-Mahault (30 924 inhabitants), was checked by hand and"
            " resolved in the register's favour: the maire is Michel Mado.",
        "address_verification": "All 242 addresses were geocoded against the Base Adresse"
            " Nationale (api-adresse.data.gouv.fr) on 2026-08-05. 242 of 242 resolved."
            " 0 of the 197 commune addresses resolved to a different commune. Median match"
            " score 0.945. Two postcodes did not match their departement: 97717 for"
            " Saint-Denis de La Reunion, which is a legitimate cedex code, and 07440 for"
            " Chamonix-Mont-Blanc, which is an error in the source and is corrected here."
            " Street-level correspondence between our address and the BAN match is 0.9 or"
            " better for 194 of 242 and 0.6 or better for 233 of 242; the rest are addresses"
            " the national database does not carry at street level, typically rural 'Le Bourg'"
            " forms, not errors in ours.",
        "items": items,
    }, open(OUT, "w"), ensure_ascii=False, indent=2)

    print(f"wrote {OUT}\n")
    for q, v in counts.items():
        print(f"  {q:<9} {v['answerable']:>3} / {v['total']:<3} answerable")
    oui = sum(1 for i in items if i["question_id"] == "L_ID" and i["expected_answer"] == "Oui")
    nt = sum(1 for i in items if i["question_id"] == "L_ID" and i["near_threshold"])
    print(f"\n  L_ID: Oui {oui}, Non {200-oui}; {nt} within 100 hab of the threshold")
    print(f"\n  exceptions ({len(exceptions)}):")
    for c, n, q, w in exceptions:
        print(f"    {q:<9} {c} {n}: {w}")
    tot = sum(v["answerable"] for v in counts.values())
    print(f"\n  total answerable locality prompts: {tot}")


if __name__ == "__main__":
    main()
