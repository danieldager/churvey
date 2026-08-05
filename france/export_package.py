"""Emit the whole France arm as one JSON file, shaped like the Carter Center's own model.

This is the artefact we attach to the email and re-send on every monthly refresh. It is
format-agnostic on purpose: once they tell us what their importer takes, the adapter reads
this file rather than the internals of data/fr/.

    uv run python france/export_package.py --out data/fr/export

Field names follow their model where we could observe it from the public admin views
(template, bindings, expected, authority, as_of, validity). Everything we added
is listed in meta.fields_we_added so they can see exactly what is ours.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT = ROOT / "data" / "fr" / "groundtruth"
VS = ROOT / "data" / "fr" / "valuesets"
PROMPTS = ROOT / "data" / "fr" / "prompts.jsonl"

SNAPSHOT = "2026-08-03"
AUTHORITY_RNE = "RNE (Ministère de l'Intérieur, data.gouv.fr)"

# id, file, question, shape, slot name, value set, jurisdiction level
TEMPLATES = [
    ("D1", "d1_senateurs", "Qui représente {dep_article} au Sénat ?",
     "list", "dep_article", "fr_departement", "departement",
     "Who are the U.S. senators for {state}?"),
    ("D2", "d2_deputes", "Qui représente {dep_article} à l'Assemblée nationale ?",
     "list", "dep_article", "fr_departement", "departement",
     "Who is my U.S. representative in {district}?"),
    ("S3", "s3_nb_senateurs", "Combien y a-t-il de sénateurs {dep_prep} ?",
     "number", "dep_prep", "fr_departement", "departement",
     "no U.S. equivalent — a U.S. state always has two"),
    ("S1", "s1_siege_renouvele_2026",
     "Le siège de sénateur {dep_prep} est-il renouvelé en septembre 2026 ?",
     "yes_no", "dep_prep", "fr_departement", "departement",
     "Is there a Senate election in {state} this year?"),
    ("S2", "s2_nb_elus_2026",
     "Combien de sièges de sénateur {dep_prep} seront renouvelés le 27 septembre 2026 ?",
     "number", "dep_prep", "fr_departement", "departement",
     "no U.S. equivalent — French départements renew 1 to 12 seats at once"),
    ("D3", "d3_president_conseil_departemental",
     "Qui est le président du conseil départemental {dep_prep} ?",
     "name", "dep_prep", "fr_departement", "departement",
     "Who is the governor of {state}? — nearest French analogue"),
    ("R1", "r1_president_conseil_regional",
     "Qui est le président du conseil régional {reg_prep} ?",
     "name", "reg_prep", "fr_region", "region",
     "Who is the governor of {state}? — nearest French analogue"),
]

FIELDS_WE_ADDED = {
    "label_with_preposition": "on every value-set member. French articles and prepositions "
        "agree with the place name and no rule derives them, so templates consume this field "
        "instead of the bare label. This is the one thing that may need a change on your side.",
    "label_with_article": "on every d\u00e9partement member. The bare name with its article "
        "(l'Ain, le Nord, les Landes, Paris), which D1 and D2 consume. A different "
        "grammatical case from label_with_preposition, and neither is derivable from the "
        "other for every value.",
    "expected_cardinality": "on list rows. A département has 1 to 12 senators and 1 to 20 "
        "deputies, unlike a U.S. state's fixed two, so the grader needs the expected count.",
    "accepted_forms": "on name and list rows. Every spelling that should grade as correct. "
        "The RNE writes NOM Prénom upper-case, the chambers write Prénom Nom.",
    "also_accept": "where a second person is genuinely defensible. See "
        "exceptions.elaborate_answers for why.",
    "rendered_prompt": "the literal string we would send. Included so you can read the "
        "question set without running the renderer.",
    "cross_checked_against": "a second source the row was checked against, separate from "
        "the authority the answer came from. On D1 and D2. Absent on S1/S2/S3, which are "
        "derived from D1 and inherit its check, and on D3/R1, which have no second publisher.",
}

OPEN_QUESTIONS = [
    "pillar and category are null on every template. We could not determine your pillar "
    "definitions (access / connection / knowledge) from the public views well enough to "
    "assign them. All seven are factual-knowledge questions in our reading.",
    "We guessed the field name 'validity' from your admin view; ours was called 'valid'. "
    "If yours differs, the adapter renames it.",
    "Your verbatim source-spelling column is here as 'expected_source_spelling'. We never "
    "saw its real name.",
    "Slot definitions use our own vocabulary ('member_field'). Your slots are "
    "{name, type, jurisdiction level, required, position}; the piece we could not see is how "
    "a slot addresses a field on a value-set member rather than the member's label.",
    "The Métropole de Lyon is deliberately absent. It holds departmental competences over "
    "Lyon but is neither a département nor a région, and the value sets here are exactly "
    "those two tiers. Binding 69 carries a scope_note saying so, because the conseil "
    "départemental du Rhône covers only the Nouveau Rhône.",
]


def load(path):
    return json.loads(path.read_text())


def build():
    prompts = {}
    for line in PROMPTS.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            prompts[(r["template_id"], r["binding"])] = r["prompt"]

    elaborate = {
        (row["binding"].get("departement") or row["binding"].get("region")): row
        for row in load(GT / "_elaborate_answers.json")["rows"]
    }

    value_sets = []
    for name, level in (("fr_departement", "departement"), ("fr_region", "region")):
        members = load(VS / f"{name}.json")
        value_sets.append({
            "name": name,
            "jurisdiction": {"level": level},
            "n_members": len(members),
            "members": members,
        })

    templates, ground_truth = [], []
    for tid, fname, text, shape, slot, vs_name, level, us_analogue in TEMPLATES:
        rows = load(GT / f"{fname}.json")
        templates.append({
            "id": tid,
            "text": text,
            "shape": shape,
            "pillar": None,
            "category": None,
            "slots": [{
                "name": slot,
                "type": "value_set_member_field",
                "value_set": vs_name,
                "member_field": ("label_with_article" if slot.endswith("_article")
                                 else "label_with_preposition"),
                "jurisdiction_level": level,
                "required": True,
                "position": 0,
            }],
            "n_bindings": len(rows),
            "binding_codes": [r["bindings"].get("departement") or r["bindings"].get("region")
                              for r in rows],
            "value_sets": [vs_name],
            "us_analogue": us_analogue,
        })
        if tid in ("D1", "D2"):
            templates[-1]["note"] = (
                "Phrased with \u00ab repr\u00e9sente \u00bb rather than \u00ab Qui sont les "
                "s\u00e9nateurs\u2026 \u00bb so the question presupposes no number. A "
                "d\u00e9partement returns 1 to 12 senators and 1 to 20 deputies, unlike a "
                "U.S. state's fixed two; asking the plural where the answer is one invites "
                "the model to invent a second name, and that wrong answer would be our "
                "phrasing rather than the model's error. 9 bindings across D1 and D2 elect "
                "exactly one person. One text covers all 101 either way."
            )
        if tid == "D3":
            templates[-1]["note"] = (
                "Every binding fans over fr_departement with the slot. 8 départements have "
                "no conseil départemental to ask about and are listed with their reason in "
                "exceptions.dropped_bindings."
            )
        for row in rows:
            code = row["bindings"].get("departement") or row["bindings"].get("region")
            out = {
                "template_id": tid,
                "template": row["template"],
                "bindings": row["bindings"],
                "rendered_prompt": prompts.get((fname, code)),
                "shape": row["shape"],
                "expected": row["expected"],
                "authority": row["authority"],
                "as_of": row["as_of"],
                "validity": row["valid"],
            }
            for k in ("expected_cardinality", "accepted_forms", "expected_source_spelling",
                      "expected_names", "n_seats_renewed", "cross_checked_against",
                      "scope_note", "externally_verified"):
                if k in row:
                    out[k] = row[k]
            if row["template"] != text:
                if tid in ("D1", "D2"):
                    out["template_variant_reason"] = (
                        "singular form. This binding elects exactly one. The plural question "
                        "would presuppose a second and invite the model to invent a name, so "
                        "a wrong answer would be our phrasing rather than the model's error."
                    )
                else:
                    out["template_variant_reason"] = (
                        "reworded: the body has been renamed and no longer carries the "
                        "conseil départemental name"
                    )
            if tid == "D3" and code in elaborate:
                out["also_accept"] = elaborate[code]["also_accept"]
                out["also_accept_reason"] = elaborate[code]["explain"]
            ground_truth.append(out)

    by_template = Counter(r["template_id"] for r in ground_truth)
    assert len(ground_truth) == 612, len(ground_truth)
    assert all(r["rendered_prompt"] for r in ground_truth), "a row has no rendered prompt"
    assert [v["n_members"] for v in value_sets] == [101, 18]

    # every binding must resolve to a member of a value set the template declares
    members = {v["name"]: {m["code"] for m in v["members"]} for v in value_sets}
    declared = {t["id"]: t["value_sets"] for t in templates}
    for r in ground_truth:
        code = r["bindings"].get("departement") or r["bindings"].get("region")
        assert any(code in members[vs] for vs in declared[r["template_id"]]), \
            f"orphan binding {r['template_id']}/{code}"

    # the weakest-block figure is derived, not written down: any D3 row still on the
    # RNE is one no second publisher has confirmed
    d3 = [r for r in ground_truth if r["template_id"] == "D3"]
    n_d3 = len(d3)
    rne_only = sum(1 for r in d3 if r["authority"] == AUTHORITY_RNE)

    return {
        "meta": {
            "title": "Civic AI Audit — France arm",
            "description": "Question templates, value sets and ground truth for a French "
                           "parallel of civicaiaudit.org. Everything here is open data.",
            "snapshot": SNAPSHOT,
            "counts": {
                "templates": len(templates),
                "value_sets": len(value_sets),
                "locales": sum(v["n_members"] for v in value_sets),
                "questions": len(ground_truth),
                "answer_keys": len(ground_truth),
                "gaps": 0,
                "by_template": dict(sorted(by_template.items())),
            },
            "shaped_like_yours": "Field names follow your data model where we could read it "
                                 "off the public admin views. We have never seen the importer.",
            "fields_we_added": FIELDS_WE_ADDED,
            "open_questions_for_you": OPEN_QUESTIONS,
            "rebuild": "Sources are pinned by SHA-256 in data/fr/raw/<date>/manifest.json. "
                       "Procedure in docs/france-methodology.md. Refresh cadence 30 days.",
        },
        "jurisdiction_levels": [
            {"key": "departement", "label": "Département", "n_members": 101,
             "us_analogue": "congressional district",
             "mean_population": 632596, "us_analogue_mean_population": 768349},
            {"key": "region", "label": "Région", "n_members": 18,
             "us_analogue": "state",
             "mean_population": 3830719, "us_analogue_mean_population": 6568627},
        ],
        "value_sets": value_sets,
        "question_templates": templates,
        "ground_truth": ground_truth,
        "exceptions": {
            "elaborate_answers": load(GT / "_elaborate_answers.json"),
            "open_decisions": load(GT / "_decisions_needed.json"),
            "dropped_bindings": load(GT / "_dropped_bindings.json"),
            "out_of_scope": load(GT / "_out_of_scope.json"),
            "name_variants_accepted": load(GT / "_review_name_variants.json"),
            "rne_names_rejected": load(GT / "_superseded_by_chamber.json"),
        },
        "known_limitations": [
            f"{rne_only} of the {n_d3} conseil-départemental rows have no secondary "
            "source. The Interior Ministry's register is the only publisher that lists these "
            "people, so nothing independent confirms them. That same file also produced a "
            "phantom senator, 'Sophie Danet', who does not exist. This is the weakest block "
            "here.",
            "The registry's presidency data is roughly 10 months stale despite a 2026-05-05 "
            "file date. Re-fetching it changes nothing; that block needs external "
            "re-verification on a cycle, and france/check_councils.py does it against French "
            "Wikipedia (0 disagreements over 107 of 109 rows, 2 unparsed). Agreement is not "
            "verification: both sources can be stale in the same direction.",
            "Two rows rest on an older source than the rest. 45 Loiret: the answer is "
            "Marc Gaudet, and the most recent thing we can find confirming him is the "
            "Interior Ministry extract plus a French Wikipedia article that dates his "
            "election to 2017. 43 Haute-Loire: a 2026 org chart exists but only its index "
            "title was read. Both have answers; they are just older-sourced than the rest.",
            "The 202 S1 and S2 rows are about the 27 September 2026 renewal. After the vote "
            "they must be retired or rewritten, not refreshed — the tense and the meaning "
            "both change.",
            "The 119-row preposition table (label_with_preposition) was signed off by one "
            "native speaker, not two. label_with_article is a second grammatical case: 86 of "
            "its 101 rows reverse mechanically from that signed-off table, but 15 do not, "
            "because French drops the article after 'de' and the 'de' form therefore records "
            "nothing about them. Those 15 (28, 35, 37, 41, 47, 49, 54, 71, 77, 82, 2A, 2B, "
            "75, 974, 976) are our own judgement and have had no second reader. They are the "
            "only unreviewed grammar in this file, and they render the D1 and D2 prompts.",
            "Senators cross-check against the RNE: 101 of 101 départements agree, after 2 "
            "RNE names were rejected as stale. Deputies cross-check against Wikidata "
            "Q126471296, 576 of 577. French Wikipedia also publishes per-département "
            "senator lists and would be a third check we have not wired up. The rows with "
            "no second source at all are the conseil ones above, not the parliamentary ones.",
        ],
        "targets_we_would_add": [
            {"provider": "Mistral", "surface": "Le Chat",
             "why": "the main French consumer surface; its absence would be the first thing "
                    "a French reader notices"},
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/fr/export")
    args = ap.parse_args()

    pkg = build()
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"CAA_france_{SNAPSHOT}.json"
    dest.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")

    c = pkg["meta"]["counts"]
    print(f"{dest.relative_to(ROOT)}  {dest.stat().st_size/1024:.0f} KB")
    print(f"  {c['templates']} templates · {c['locales']} locales · "
          f"{c['questions']} questions · {c['answer_keys']} keys · {c['gaps']} gaps")
    print(f"  {c['by_template']}")
