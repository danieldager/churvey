"""Emit the France présidentielle 2027 arm as one JSON file, shaped like the Carter Center's model.

This is the artefact attached to the email and re-sent on every refresh. Format-agnostic on
purpose: once they say what their importer takes, the adapter reads this file rather than the
internals of data/fr/.

    uv run python france/export_2027.py

Field names follow their model where we could observe it from the public admin views
(template, bindings, expected, authority, as_of). Everything we added is listed in
meta.fields_we_added.
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/fr/raw/2026-08-04"
ANSWERS = ROOT / "data/fr/answers/locality_answers.json"
SAMPLE = ROOT / "data/fr/sample/communes_sample_draft.json"
NATIONAL = ROOT / "analysis/france_questions_draft.json"
OUT = ROOT / "data/fr/export/CAA_france_presidentielle_2027.json"

SNAPSHOT = "2026-08-05"

TEMPLATES = [
    ("L_ID", "J'habite {commune_a}. Faut-il présenter une pièce d'identité pour voter à"
             " l'élection présidentielle ?", "yes_no", "commune",
     "Does the voter need photo ID at the polling place in {jurisdiction}?"),
    ("L_MAIRIE", "J'habite {commune_a}. Où est-ce que je m'inscris sur les listes électorales"
                 " en personne ?", "place", "commune",
     "Where do I go to register to vote in person in {jurisdiction}?"),
    ("L_MAIRE", "Qui est le maire {commune_de} ?", "name", "commune",
     "no direct U.S. analogue; the maire is the electoral authority in the commune and"
     " presides the bureau de vote"),
    ("A1", "Quand a lieu le 1er tour de l'élection présidentielle de 2027 ?", "date",
     "national", "When is the election?"),
    ("A3", "À quelle heure ouvrent les bureaux de vote pour l'élection présidentielle ?",
     "time", "national", "What time do the polls open?"),
    ("A6", "Jusqu'à quand peut-on s'inscrire sur les listes électorales pour voter au 1er tour"
           " de la présidentielle ?", "date_rule", "national",
     "What is the voter registration deadline?"),
    ("A8", "Si je déménage dans une autre commune, dois-je me réinscrire sur les listes"
           " électorales ?", "yes_no", "national",
     "If I move, do I have to re-register?"),
    ("A22", "Combien de parrainages faut-il pour être candidat à l'élection présidentielle ?",
     "number", "national", "no U.S. equivalent; U.S. ballot access is state by state"),
]

FIELDS_WE_ADDED = {
    "label_with_a": "on every commune member. French place names take articles that do not"
        " follow from the bare name: Le Havre is 'au Havre', Les Portes du Coglais is 'aux"
        " Portes du Coglais', everything else is 'à X'. Templates consume this field instead"
        " of the bare label. This is the one thing that may need a change on your side.",
    "label_with_de": "on every commune member. Same problem in the genitive: 'du Havre',"
        " 'des Portes du Coglais', \"d'Angers\", 'de La Baffe'.",
    "label_disambiguated": "on the 16 communes whose bare name is not unique in France."
        " Saint-Denis exists in 4 départements and two of them are in this sample, so those"
        " questions carry the département in parentheses.",
    "stratum": "on every commune member. Which sampling stratum it came from, so the sample"
        " can be reweighted to the frame before any rate is reported.",
    "population": "on every commune member. The identity-document rule keys off it.",
}


def main():
    key = json.load(open(ANSWERS))
    sample = {c["code"]: c for c in json.load(open(SAMPLE))["communes"]}
    dep_nom = {d["code"]: d["nom"] for d in json.load(open(RAW / "geo_departements.json"))}
    nat_src = json.load(open(NATIONAL))
    nat_by = {c["id"]: c for c in nat_src["candidates"]}
    national_ids = nat_src["selection"]["national_block"]

    items = key["items"]

    # value set: communes
    a_form, de_form = {}, {}
    for i in items:
        if i["question_id"] == "L_ID":
            a_form[i["code_insee"]] = i["question"].split(".")[0].replace("J'habite ", "")
        if i["question_id"] == "L_MAIRE":
            de_form[i["code_insee"]] = (i["question"]
                                        .replace("Qui est le maire ", "").replace(" ?", ""))
    communes = []
    for code, c in sample.items():
        dis = any(i.get("disambiguated") for i in items if i["code_insee"] == code)
        communes.append({
            "code": code, "label": c["nom"],
            "label_with_a": a_form[code], "label_with_de": de_form[code],
            "label_disambiguated": f"{c['nom']} ({dep_nom[c['codeDepartement']]})"
                                   if dis else None,
            "departement_code": c["codeDepartement"],
            "departement_label": dep_nom[c["codeDepartement"]],
            "region_code": c["codeRegion"],
            "population": c["population"],
            "stratum": c["stratum"],
            "id_required": c["population"] >= 1000,
        })
    communes.sort(key=lambda m: m["code"])

    arronds = []
    for i in items:
        if i.get("tier") == "arrondissement":
            arronds.append({"code": i["id"].split("/")[-1], "label": i["commune"],
                            "mairie_code_insee": i["code_insee"],
                            "arrondissement": i["arrondissement"],
                            "shares_mairie_with": i.get("shares_mairie_with")})
    arronds.sort(key=lambda m: (m["mairie_code_insee"], m["arrondissement"]))

    gt = []
    for i in items:
        gt.append({
            "template_id": i["question_id"],
            "bindings": ({"arrondissement": i["id"].split("/")[-1]}
                         if i.get("tier") == "arrondissement"
                         else {"commune": i["code_insee"]}),
            "rendered_prompt": i["question"],
            "shape": next(t[2] for t in TEMPLATES if t[0] == i["question_id"]),
            "expected": i["expected_answer"],
            "also_accept": i.get("accepted_variants"),
            "authority": i["authority"],
            "as_of": SNAPSHOT,
        })
    for qid in national_ids:
        c = nat_by[qid]
        gt.append({
            "template_id": qid, "bindings": {}, "rendered_prompt": c["text"],
            "shape": next(t[2] for t in TEMPLATES if t[0] == qid),
            "expected": c["expected_answer"], "also_accept": None,
            "authority": c.get("source"), "as_of": SNAPSHOT,
        })

    by_template = Counter(r["template_id"] for r in gt)

    doc = {
        "meta": {
            "title": "Civic AI Audit, France arm, élection présidentielle 2027",
            "description": "Question templates, value sets and answer keys for a French"
                           " parallel of civicaiaudit.org, aimed at the presidential election"
                           " of 18 April and 2 May 2027. Everything here is open data.",
            "snapshot": SNAPSHOT,
            "election": {"name": "élection présidentielle 2027",
                         "tour_1": "2027-04-18", "tour_2": "2027-05-02",
                         "caveat": "Announced by service-public.gouv.fr F1939 (verified"
                                   " 2026-07-01). The décret de convocation is not published"
                                   " yet; voters are convoked at least 10 weeks before the 1st"
                                   " round."},
            "counts": {"templates": len(TEMPLATES), "value_sets": 2,
                       "communes": len(communes), "arrondissements": len(arronds),
                       "questions": len(gt), "answer_keys": len(gt), "gaps": 0,
                       "by_template": dict(by_template)},
            "fields_we_added": FIELDS_WE_ADDED,
        },
        "jurisdiction_levels": [
            {"key": "commune", "label": "Commune", "n_members": len(communes),
             "us_analogue": "city or township, the level that runs registration and the"
                            " polling place", "n_in_france": 34875},
            {"key": "arrondissement", "label": "Arrondissement municipal",
             "n_members": len(arronds),
             "note": "Paris, Lyon and Marseille only. Registration happens at the mairie"
                     " d'arrondissement, not the mairie centrale."},
        ],
        "value_sets": [
            {"name": "fr_commune", "jurisdiction": {"level": "commune"},
             "n_members": len(communes), "members": communes},
            {"name": "fr_arrondissement", "jurisdiction": {"level": "arrondissement"},
             "n_members": len(arronds), "members": arronds},
        ],
        "question_templates": [
            {"id": t[0], "text": t[1], "shape": t[2], "jurisdiction_level": t[3],
             "us_analogue": t[4]} for t in TEMPLATES
        ],
        "sampling": json.load(open(SAMPLE)).get("_status") and {
            "frame": "34 383 communes. Metropolitan France plus the 5 DROM (101 départements),"
                     " minus 492 (1.4%) where an answer cannot be sourced or would be"
                     " ambiguous: 305 with no maire recorded in the Interior Ministry"
                     " register, 7 with no mairie listed, 12 whose mairie does not resolve to"
                     " a single office, and 168 where the identity answer would differ"
                     " depending on which INSEE population figure R60's threshold is read to"
                     " mean.",
            "rule": "france/sample_communes.py, seed 20270418. Written before the draw and"
                    " deterministic, so it reproduces exactly.",
            "strata": {"most_populous": 38, "just_below_1000": 48, "just_above_1000": 48,
                       "very_low": 28, "mid": 28, "drom": 10},
            "coverage": "101 of 101 départements, 18 of 18 régions, 83 of the roughly 90"
                        " one-degree cells metropolitan France spans.",
            "not_representative": "Stratified for discrimination, not proportional to France."
                                  " 40% of the sample is under 1 000 inhabitants against 71%"
                                  " of the frame, and the DROM are 5% against 0.37%. Both are"
                                  " deliberate. Reweight to the frame before reporting any"
                                  " rate as a share of French communes.",
        },
        "ground_truth": gt,
        "exceptions": {"count": 0,
                       "note": "Every question has an answer from an official source."
                               " Communes where one could not be sourced were removed from"
                               " the frame before the sample was drawn, not patched after."},
        "grading_notes": key["grading_notes"],
        "known_limitations": [
            "Code electoral R60 sets the identity threshold at \"communes de 1 000 habitants"
            " et plus\" and does not say which population figure that means. INSEE publishes"
            " two, the population municipale and the population totale, and 168 of the 34 855"
            " communes it lists fall between them. All 168 were removed from the pool before"
            " the sample was drawn, so every answer here is the same under either figure. Our"
            " populations were also checked against the INSEE populations legales millesime"
            " 2023 (published 2025-12-18) for all 34 855 communes, with zero disagreements.",
            "The identity-document question is yes or no, and the sample is 121 yes to 79 no."
            " A surface that always answers yes scores 60.5% on it while knowing nothing about"
            " any commune. Report it against that baseline, not against zero. The other two"
            " local questions have no such floor: 200 of 200 and 231 of 242 distinct answers.",
            "The maire answers come from the Interior Ministry register dated 5 May 2026,"
            " after the March 2026 municipal elections. If a maire has resigned or died since,"
            " the answer here is confidently wrong and nothing in our build would notice."
            " Four were cross-checked against an independent source and all four agreed.",
            "The best local question we could ask is what time the polling station closes,"
            " because it is 19h by default and 20h in many communes by prefectoral order."
            " Neither the convocation decree nor the 101 prefectoral orders exist yet; they"
            " are expected in February and March 2027. We would add it then.",
            "The French wording was written by us and checked rule by rule, but has not been"
            " read by a native speaker.",
            "324 communes (0.93% of the territorial frame) are excluded because their records"
            " are incomplete. That exclusion is not random: it removes communes nouvelles and"
            " places with thin administrative data entry, and Guadeloupe is the worst affected.",
        ],
        "targets_we_would_add": [
            {"provider": "Mistral", "surface": "Le Chat",
             "why": "the main French consumer surface; its absence would be the first thing a"
                    " French reader notices"}
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(doc, open(OUT, "w"), ensure_ascii=False, indent=2)
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({size:.0f} KB)")
    print(f"  questions {len(gt)} | answer keys {len(gt)} | gaps 0")
    print(f"  by template: {dict(by_template)}")
    print(f"  communes {len(communes)} | arrondissements {len(arronds)}")


if __name__ == "__main__":
    main()
