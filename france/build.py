#!/usr/bin/env python3
"""Stages 1, 2 and 8 - build the French value sets and ground truth from a
pinned snapshot.

  Stage 1  value sets   fr_region (18), fr_departement (101)
  Stage 2  ground truth D1 senateurs, D2 deputes  (list, per departement)
           D3 president du conseil departemental  (name)
           R1 president du conseil regional       (name)
  Stage 8  offline wide build - maires + piece-d'identite keys, NOT for load

Every stage asserts its gate and exits non-zero on failure. Nothing is written
if a cardinality gate fails: a silently short value set corrupts every verdict
downstream.

  france/build.py [--snapshot data/fr/raw/2026-08-03] [--out data/fr]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from prepositions import (AUDITED, ARTICLE_REVIEWED_ROWS, DEPARTEMENT_ARTICLE,
                          DEPARTEMENT_PREP, REGION_PREP)
from chambers import (deputes as ch_deputes, key, probable_variant,
                      same_person, senateurs_live as ch_senateurs_live, slug)
from probe_presidents import NO_CD, NO_CR, pad, presidents, read
from verified import (ANSWERS as VERIFIED_ANSWERS, DECISIONS_NEEDED,
                      MISSING_PRESIDENTS, NAME_VARIANTS,
                      OPERATOR_AUTHORITY, OVERRIDES,
                      TEMPLATE_OVERRIDES)

VARIANTS_REVIEW = []
AS_OF = "2026-05-05"          # RNE extract date
AUTHORITY = "RNE (Ministère de l'Intérieur, data.gouv.fr)"
# For their own members the chambers beat the RNE (decision 2026-08-03): the RNE
# lists the titulaire, the chamber lists whoever is actually sitting. This is
# enforced by consulting the chamber first, not by a rank stored on the row.
SEN_AUTHORITY = "senat.fr api-senat/senateurs.json (Sénat, live register)"
DEP_AUTHORITY = "data.assemblee-nationale.fr (AMO10, législature 17)"
# The chambers are live endpoints fetched at snapshot time, so a chamber row's
# as_of is the day we fetched it, NOT the RNE's quarterly extract date. Stamping
# both with AS_OF made every D1/D2/S* row claim to be three months older than it is.
CHAMBER_AS_OF = "2026-08-03"

failures = []


def gate(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        failures.append(f"{name}: {detail}")


def display_name(row):
    return f"{row['Prénom de l\'élu'].strip()} {row['Nom de l\'élu'].strip()}"


def source_name(row):
    """RNE stores surname-first, upper-case. Keep it verbatim beside the display
    form so the judge can be tested against both (Gate 2c)."""
    return f"{row['Nom de l\'élu'].strip()} {row['Prénom de l\'élu'].strip()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="data/fr/raw/2026-08-03")
    ap.add_argument("--out", default="data/fr")
    args = ap.parse_args()
    snap, out = Path(args.snapshot), Path(args.out)

    deps = json.loads((snap / "departements.json").read_text(encoding="utf-8"))
    regs = json.loads((snap / "regions.json").read_text(encoding="utf-8"))
    sen = read(snap / "elus-senateurs-sen.csv")
    dep = read(snap / "elus-deputes-dep.csv")

    # ---- per-departement rosters (leading zeros: RNE stores '1', not '01') ----
    # The 101 departements do NOT cover the whole chamber. Seats also exist for
    # the collectivites a statut particulier (empty departement code) and for the
    # Francais etablis hors de France (code 'ZZ'). Those are out of scope for a
    # {dep_prep} template - "Qui sont les senateurs du Nord ?" has no analogue for
    # a non-territorial constituency - so they are partitioned off and counted,
    # never silently dropped.
    dep_codes = {d["code"] for d in deps}
    # Martinique and Guyane are collectivites territoriales uniques: the RNE files
    # their senators under the collectivite label with an EMPTY departement code,
    # even though both are departements in the COG. Map them back or D1 loses
    # 2 departements and 4 seats.
    COLLECTIVITE_TO_DEP = {"Martinique": "972", "Guyane": "973"}

    def roster(rows):
        inside, outside = defaultdict(list), defaultdict(list)
        for r in rows:
            code = pad(r["Code du département"], 2)
            label = r["Libellé du département"].strip() or \
                r["Libellé de la collectivité à statut particulier"].strip()
            if code not in dep_codes:
                code = COLLECTIVITE_TO_DEP.get(
                    r["Libellé de la collectivité à statut particulier"].strip(), code)
            (inside if code in dep_codes else outside)[
                code if code in dep_codes else label].append(r)
        return inside, outside

    sen_by, sen_out = roster(sen)
    dep_by, dep_out = roster(dep)

    # ================= Stage 1 - value sets =================
    print("\n=== STAGE 1: value sets ===")
    reg_codes = {r["code"] for r in regs}

    gate("1a cardinality fr_departement", len(deps) == 101, f"{len(deps)} (expect 101)")
    gate("1a cardinality fr_region", len(regs) == 18, f"{len(regs)} (expect 18)")
    gate("1b region referential", all(d["codeRegion"] in reg_codes for d in deps),
         "every département's région resolves")
    in_sen = sum(len(v) for v in sen_by.values())
    in_dep = sum(len(v) for v in dep_by.values())
    ex_sen = sum(len(v) for v in sen_out.values())
    ex_dep = sum(len(v) for v in dep_out.values())
    gate("1b senate seats reconcile", in_sen + ex_sen == 348,
         f"{in_sen} in départements + {ex_sen} out of scope = {in_sen + ex_sen} (expect 348)")
    gate("1b circonscriptions reconcile", in_dep + ex_dep == 577,
         f"{in_dep} in départements + {ex_dep} out of scope = {in_dep + ex_dep} (expect 577)")
    gate("1b every département has ≥1 sénateur", set(sen_by) == dep_codes,
         f"missing: {sorted(dep_codes - set(sen_by)) or 'none'}")
    gate("1b every département has ≥1 député", set(dep_by) == dep_codes,
         f"missing: {sorted(dep_codes - set(dep_by)) or 'none'}")
    print(f"    out of scope (non-territorial constituencies):")
    for k, v in sorted(sen_out.items()):
        print(f"      sénateurs  {k or '(unnamed)':45s} {len(v):3d}")
    for k, v in sorted(dep_out.items()):
        print(f"      députés    {k or '(unnamed)':45s} {len(v):3d}")
    gate("1c preposition coverage dépt", set(DEPARTEMENT_PREP) == dep_codes,
         f"missing: {sorted(dep_codes - set(DEPARTEMENT_PREP)) or 'none'}")
    gate("1d article coverage dépt",
         set(DEPARTEMENT_ARTICLE) == dep_codes and all(DEPARTEMENT_ARTICLE.values()),
         f"{len(DEPARTEMENT_ARTICLE)} rows, {len(ARTICLE_REVIEWED_ROWS)} written out "
         f"(the rest derived from the audited 'de' table)")
    gate("1c preposition coverage région", set(REGION_PREP) == reg_codes,
         f"missing: {sorted(reg_codes - set(REGION_PREP)) or 'none'}")
    # not build-blocking: the artifacts are what the auditor reads. It blocks the
    # BATCH RUN - see render.py, which refuses to emit prompts while AUDITED is False.
    print(f"  [{'PASS' if AUDITED else 'WARN'}] 1c native-speaker audit: "
          f"{'signed off' if AUDITED else 'PENDING - render.py will refuse to emit prompts'}")

    vs_dep = [{
        "code": d["code"], "label": d["nom"],
        "label_with_preposition": DEPARTEMENT_PREP.get(d["code"]),
        "label_with_article": DEPARTEMENT_ARTICLE.get(d["code"]),
        "region_code": d["codeRegion"],
        "n_senateurs": len(sen_by.get(d["code"], [])),
        "n_circonscriptions": len(dep_by.get(d["code"], [])),
        "has_conseil_departemental": d["code"] not in NO_CD,
    } for d in sorted(deps, key=lambda x: x["code"])]
    vs_reg = [{
        "code": r["code"], "label": r["nom"],
        "label_with_preposition": REGION_PREP.get(r["code"]),
        "has_conseil_regional": r["code"] not in NO_CR,
    } for r in sorted(regs, key=lambda x: x["code"])]

    # ---- RNE integrity: the published deputy file contains corrupt rows ----
    # Verified 2026-08-03: 577 rows but only 572 distinct circonscription codes.
    # Five mid-legislature entrants carry a code that collides with the legitimate
    # holder. The corruption varies - sometimes the département code is wrong
    # (Duparay filed under Doubs, actually Saône-et-Loire), sometimes the
    # circonscription code is (Bergantz labelled Yvelines but coded 102 = Ain-2).
    # This is in the PUBLISHED FILE, not in our extraction. It does not affect the
    # answer keys, which come from the chambers - but it must be re-detected on
    # every refresh, because the RNE is still the cross-check.
    circo_codes = Counter(r["Code de la circonscription législative"].strip()
                          for r in dep)
    collisions = {c: n for c, n in circo_codes.items() if n > 1}
    prefix_mismatch = [
        r for r in dep
        if (cc := r["Code de la circonscription législative"].strip())
        and (dc := r["Code du département"].strip())
        and not cc.startswith(dc) and dc not in ("", "ZZ")]
    print(f"\n=== RNE INTEGRITY (cross-check source, not the answer key) ===")
    print(f"  deputy rows {len(dep)}, distinct circonscription codes {len(circo_codes)}")
    print(f"  colliding codes: {len(collisions)} {sorted(collisions) or ''}")
    print(f"  rows whose circo code does not start with their département code: "
          f"{len(prefix_mismatch)}")
    for r in prefix_mismatch[:8]:
        print(f"      {r['Nom de l\'élu']:22s} dept={r['Code du département']:4s} "
              f"circo={r['Code de la circonscription législative']:6s} "
              f"debut={r['Date de début du mandat']}")
    if len(collisions) > 5:
        failures.append(f"RNE integrity: {len(collisions)} colliding circo codes, "
                        f"was 5 at 2026-05-05 - the published file degraded further")

    # ================= Stage 2 - ground truth =================
    print("\n=== STAGE 2: ground truth ===")

    def list_rows(template, roster, rne_roster, prep, unit_label, authority):
        """Chamber roster is authoritative. RNE spellings of the SAME person are
        recorded as additionally-acceptable forms; RNE names that match nobody in
        the chamber are recorded as superseded (titulaire replaced by suppléant),
        NOT accepted - they are a different person, and the sitting member is the
        correct answer."""
        rows, superseded = [], []
        variants_for_review = VARIANTS_REVIEW
        for code in sorted(roster):
            members = sorted(roster[code])
            rne = sorted(display_name(m) for m in rne_roster.get(code, []))
            rne_keys = {n: key(n) for n in rne}
            accepted, used = {}, set()
            for n in members:
                k = key(n)
                variants = [r for r, rk in rne_keys.items()
                            if r not in used and same_person(k, rk)]
                used.update(variants)
                accepted[n] = sorted({n, *variants})
            leftover_rne = [r for r in rne if r not in used]
            leftover_ch = [n for n in members if accepted[n] == [n]]
            if len(leftover_rne) == 1 and len(leftover_ch) == 1 and probable_variant(
                    key(leftover_ch[0]), key(leftover_rne[0])):
                accepted[leftover_ch[0]] = sorted({leftover_ch[0], leftover_rne[0]})
                v = NAME_VARIANTS.get((code, leftover_ch[0]))
                variants_for_review.append({
                    "departement": code, "chamber": leftover_ch[0],
                    "rne": leftover_rne[0],
                    "action": "BOTH ACCEPTED as answers",
                    "status": v["status"] if v else "UNCONFIRMED - confirm one person",
                    "note": v["note"] if v else None,
                    "source": v["url"] if v else None})
                leftover_rne = []
            for r in leftover_rne:
                superseded.append({"departement": code, "name_in_rne": r,
                                   "reason": "not sitting per the chamber - "
                                             "titulaire replaced, or RNE is stale"})
            rows.append({
                "template": template,
                "bindings": {unit_label: code},
                "rendered_slot": prep[code],
                # always `list`, even where the answer is one name: `expected` is a list
                # either way, and a row whose shape contradicts the type of its own value
                # breaks any consumer that reads shape to decide how to parse it.
                "shape": "list",
                "expected_cardinality": len(members),
                "expected": members,
                "accepted_forms": accepted,
                "authority": authority,
                "cross_checked_against": AUTHORITY,
                "as_of": CHAMBER_AS_OF, "valid": "current",
            })
        return rows, superseded

    cache = snap / "_external"
    cache.mkdir(parents=True, exist_ok=True)
    deps_by_name = {slug(d["nom"]): d["code"] for d in deps}
    sen_live, sen_unmatched = ch_senateurs_live(cache, dep_codes)
    sen_ch = {c: [x["name"] for x in v] for c, v in sen_live.items()}
    dep_ch = {c: v for c, v in ch_deputes(cache).items() if c in dep_codes}
    if sen_unmatched:
        print(f"    senat.fr constituencies not matched to a département "
              f"(expected - non-territorial): {sorted(sen_unmatched)[:6]}")

    # Phrased with "représente" rather than "Qui sont les sénateurs {dep_prep} ?"
    # so the question presupposes no number: 7 départements elect one sénateur and
    # 2 elect one député, and a plural question there invites the model to invent a
    # second name - a wrong answer that would be our phrasing, not the model's error.
    d1, d1_sup = list_rows("Qui représente {dep_article} au Sénat ?", sen_ch, sen_by,
                           DEPARTEMENT_ARTICLE, "departement", SEN_AUTHORITY)
    d2, d2_sup = list_rows("Qui représente {dep_article} à l'Assemblée nationale ?",
                           dep_ch, dep_by,
                           DEPARTEMENT_ARTICLE, "departement", DEP_AUTHORITY)
    gate("2a coverage D1", len(d1) == 101, f"{len(d1)}/101 départements (chamber-primary)")
    gate("2a coverage D2", len(d2) == 101, f"{len(d2)}/101 départements (chamber-primary)")
    c1 = sum(r["expected_cardinality"] for r in d1)
    c2 = sum(r["expected_cardinality"] for r in d2)
    gate("2b cardinality D1", c1 == 328, f"{c1} territorial senate seats (expect 328)")
    gate("2b cardinality D2", c2 == 558, f"{c2} territorial circonscriptions (expect 558)")
    gate("2a no empty expected", all(r["expected"] for r in d1 + d2),
         "every row has at least one name")
    texts = {r["template"] for r in d1} | {r["template"] for r in d2}
    gate("2f no number presupposed", len(texts) == 2 and not any(
             w in t for t in texts for w in ("les sénateurs", "les députés")),
         f"D1/D2 use {len(texts)} question texts, neither presupposing a count "
         f"({sum(1 for r in d1 + d2 if r['expected_cardinality'] == 1)} bindings "
         f"elect exactly one)")
    n_var = sum(1 for r in d1 + d2 for v in r["accepted_forms"].values() if len(v) > 1)
    print(f"    accepted spelling variants recorded: {n_var}")
    print(f"    RNE names superseded by the chamber: D1 {len(d1_sup)}, D2 {len(d2_sup)}")

    # D3 / R1 - derivable where the RNE marks the fonction; the rest is a
    # declared manual patch (Stage 5 measured 89/94 and 14/14).
    # Units with no such body are DROPPED FROM THE BINDING SET, not hand-patched.
    # "Qui est le president du conseil departemental de Paris ?" presupposes a body
    # that does not exist - that is a gotcha, and this project does not ask those.
    # (A separate "president de la Collectivite de X" template would be the honest
    # way to cover them; parked for now.)
    def name_rows(template, pres, universe, excluded, prep, unit_label, body):
        rows, todo, dropped = [], [], []
        for u in sorted(universe):
            if u in excluded:
                dropped.append({"code": u, "reason": f"no {body} exists - {excluded[u]}"})
                continue
            hits = pres.get(u, [])
            if len(hits) == 1:
                rows.append({
                    "template": template, "bindings": {unit_label: u},
                    "rendered_slot": prep[u], "shape": "name",
                    "expected": display_name(hits[0]),
                    "expected_source_spelling": source_name(hits[0]),
                    "authority": AUTHORITY,
                    "as_of": AS_OF, "valid": "current",
                })
            else:
                todo.append({"code": u, "name": prep[u], "reason":
                             "no président row in RNE" if not hits
                             else f"{len(hits)} rows marked président - ambiguous"})
        return rows, todo, dropped

    cd = read(snap / "elus-conseillers-departementaux-cd.csv")
    cr = read(snap / "elus-conseillers-regionaux-cr.csv")
    d3, d3_todo, d3_drop = name_rows("Qui est le président du conseil départemental {dep_prep} ?",
                            presidents(cd, "Code du département", 2), dep_codes, NO_CD,
                            DEPARTEMENT_PREP, "departement", "conseil départemental")
    r1, r1_todo, r1_drop = name_rows("Qui est le président du conseil régional {reg_prep} ?",
                            presidents(cr, "Code de la région", 2), reg_codes, NO_CR,
                            REGION_PREP, "region", "conseil régional")
    gate("2a coverage D3", len(d3) + len(d3_todo) == 101 - len(NO_CD),
         f"{len(d3)} auto + {len(d3_todo)} need an answer = {101 - len(NO_CD)} bindings "
         f"({len(d3_drop)} dropped: no conseil départemental exists)")
    gate("2a coverage R1", len(r1) + len(r1_todo) == 14,
         f"{len(r1)} auto + {len(r1_todo)} need an answer = 14 bindings "
         f"({len(r1_drop)} dropped: no conseil régional exists)")

    # ================= write =================
    if failures:
        print("\nBUILD FAILED - nothing written:\n  " + "\n  ".join(failures))
        sys.exit(1)

    # ---- S3: how many senators represent this departement? ----
    # Phrased « Combien y a-t-il de sénateurs {dep_prep} ? » on purpose. The obvious
    # phrasing, « Combien de sénateurs représentent {dep_prep} ? », takes a DIRECT
    # OBJECT and would need the nominative form (le Nord / l'Ain / la Somme / les
    # Landes) - a second 119-row agreement table and a second native-speaker audit.
    # The « y a-t-il ... de » construction reuses the 'de' column we already have
    # signed off, so S3 costs nothing.
    # D1 renders with the ARTICLE table, S3 with the PREPOSITION table, so S3 takes its
    # slot from the table by name rather than copying D1's rendered_slot.
    s3 = [{
        "template": "Combien y a-t-il de sénateurs {dep_prep} ?",
        "bindings": dict(r["bindings"]),
        "rendered_slot": DEPARTEMENT_PREP[r["bindings"]["departement"]],
        "shape": "number",
        "expected": r["expected_cardinality"],
        "expected_names": r["expected"],
        "authority": r["authority"],
        "as_of": r["as_of"], "valid": "current",
    } for r in d1]
    gate("2g S3 derived from D1", len(s3) == 101 and
         sum(x["expected"] for x in s3) == 328,
         f"{len(s3)} rows, Σ = {sum(x['expected'] for x in s3)} seats (expect 328)")

    # ---- S1 / S2: the September 2026 senatorial renewal ----
    # The Senat's live register carries `serie` per seat. Serie 2 is renewed on
    # 27 Sept 2026. Verified: no département has seats in both séries, so série is
    # a clean per-département property. 59 départements / 167 territorial seats.
    RENEWAL = "27 septembre 2026"
    s2_count = {c: sum(1 for x in v if x["serie"] == "2") for c, v in sen_live.items()}
    n_up = sum(1 for n in s2_count.values() if n)
    gate("2j série is per-département", not [c for c, v in sen_live.items()
                                             if len({x["serie"] for x in v}) > 1],
         f"no département splits across séries; {n_up} renewed, "
         f"{sum(s2_count.values())} territorial seats")
    s1 = [{
        "template": "Le siège de sénateur {dep_prep} est-il renouvelé en septembre 2026 ?",
        "bindings": {"departement": c}, "rendered_slot": DEPARTEMENT_PREP[c],
        "shape": "yes_no", "expected": "oui" if s2_count[c] else "non",
        "n_seats_renewed": s2_count[c],
        "authority": SEN_AUTHORITY,
        "as_of": CHAMBER_AS_OF, "valid": "current",
    } for c in sorted(sen_live)]
    s2 = [{
        # NOT « Combien de sénateurs seront élus {dep_prep} ... » - "élus de l'Ain"
        # is ungrammatical; that phrasing needs a LOCATIVE form (dans l'Ain / en
        # Gironde / à Paris), i.e. a second 119-row agreement table and a second
        # native-speaker audit. « Combien de sièges de sénateur ... seront
        # renouvelés » takes the same 'de' form we already have signed off.
        "template": "Combien de sièges de sénateur {dep_prep} seront renouvelés le "
                    + RENEWAL + " ?",
        "bindings": {"departement": c}, "rendered_slot": DEPARTEMENT_PREP[c],
        "shape": "number", "expected": s2_count[c],
        "authority": SEN_AUTHORITY,
        "as_of": CHAMBER_AS_OF, "valid": "current",
    } for c in sorted(sen_live)]
    gate("2k S1/S2 built", len(s1) == 101 and len(s2) == 101,
         f"S1 {len(s1)} ({sum(1 for r in s1 if r['expected']=='oui')} oui / "
         f"{sum(1 for r in s1 if r['expected']=='non')} non), S2 {len(s2)}")

    # fill the D3 gaps the RNE could not answer, from human-verified external sources
    filled = []
    for todo in list(d3_todo):
        v = MISSING_PRESIDENTS.get(todo["code"])
        if not v:
            continue
        d3.append({
            "template": "Qui est le président du conseil départemental {dep_prep} ?",
            "bindings": {"departement": todo["code"]},
            "rendered_slot": DEPARTEMENT_PREP[todo["code"]], "shape": "name",
            "expected": v["expected"], "in_office_since": v["since"],
            "authority": OPERATOR_AUTHORITY,
            "as_of": "2026-08-03", "valid": "current",
            "externally_verified": {k: v[k] for k in ("status", "note", "url")},
            **({"elaborate_answer": v["elaborate"]} if "elaborate" in v else {}),
        })
        d3_todo.remove(todo)
        filled.append(todo["code"])
    d3.sort(key=lambda r: r["bindings"]["departement"])
    gate("2i D3 gaps filled externally", not d3_todo,
         f"filled {len(filled)} ({', '.join(filled)}); {len(d3_todo)} still unanswered")

    # The Métropole de Lyon exercises departmental competences over Lyon, so
    # "président du conseil départemental du Rhône" is only correct for the Nouveau
    # Rhône. The Métropole is neither a département nor a région, so it is not a
    # binding here - the value sets are exactly those two tiers.
    for r in d3:
        if r["bindings"]["departement"] == "69":
            r["rendered_slot"] = "du Rhône"
            r["scope_note"] = ("the conseil départemental du Rhône covers the Nouveau Rhône; "
                               "the Métropole de Lyon holds departmental competences over "
                               "Lyon itself and is deliberately not a binding")
    # correct rows where the RNE answer is simply out of date
    corrected = []
    for r in d3:
        c = r["bindings"]["departement"]
        v = OVERRIDES.get(c)
        if not v:
            continue
        if r["expected"] != v["was"]:
            failures.append(f"OVERRIDES[{c}] expected to replace {v['was']!r} but the "
                            f"build produced {r['expected']!r} - re-verify before editing")
            continue
        r.update({"expected": v["expected"], "in_office_since": v["since"],
                  "authority": OPERATOR_AUTHORITY,
                  "as_of": "2026-08-03",
                  "superseded_rne_answer": v["was"],
                  "externally_verified": {k: v[k] for k in ("status", "note", "url")}})
        r.pop("expected_source_spelling", None)
        if "elaborate" in v:
            r["elaborate_answer"] = v["elaborate"]
        corrected.append(c)
    gate("2l stale RNE answers corrected", len(corrected) == len(OVERRIDES),
         f"corrected {len(corrected)}/{len(OVERRIDES)} ({', '.join(corrected)})")

    # rename bindings whose body no longer exists under that name
    renamed = []
    for r in d3:
        v = TEMPLATE_OVERRIDES.get(r["bindings"]["departement"])
        if not v:
            continue
        r["template"] = v["template"]
        r["rendered_slot"] = ""
        r["body_renamed"] = {k: v[k] for k in ("status", "note", "url")}
        renamed.append(r["bindings"]["departement"])
    gate("2m renamed bodies", len(renamed) == len(TEMPLATE_OVERRIDES),
         f"{len(renamed)} binding(s) re-worded to name the body that actually exists"
         f" ({', '.join(renamed)})")

    d3.sort(key=lambda r: r["bindings"]["departement"])

    # stamp external verifications LAST, so every row (incl. 69M) exists to be checked
    for tmpl, rows in (("d3", d3), ("r1", r1)):
        for r in rows:
            v = VERIFIED_ANSWERS.get((tmpl, r["bindings"]["departement"]
                                      if tmpl == "d3" else r["bindings"]["region"]))
            if not v:
                continue
            if v["expected"] != r["expected"]:
                failures.append(f"verified.py says {tmpl} {r['bindings']} = "
                                f"{v['expected']!r} but the build produced {r['expected']!r}")
                continue
            r["externally_verified"] = {k: v[k] for k in ("status", "note", "url")}
    n_ver = sum(1 for rows in (d3, r1) for r in rows if "externally_verified" in r)
    gate("2h external verification stamped",
         n_ver == len(VERIFIED_ANSWERS) + len(MISSING_PRESIDENTS) + len(OVERRIDES),
         f"{n_ver} rows confirmed against a source outside the pipeline "
         f"({len(VERIFIED_ANSWERS)} cross-checked + {len(MISSING_PRESIDENTS)} gap-filled "
         f"+ {len(OVERRIDES)} corrected)")

    # ---- 2n: the rendered slot comes from the table the slot NAMES ----
    # S3 used to copy D1's rendered_slot, which was correct until D1 switched from the
    # 'de' form to the article form and silently made all 101 S3 prompts ungrammatical.
    # A slot called {dep_prep} must hold a 'de' form and {dep_article} an article form,
    # whatever route the row took to get built.
    slot_tables = {"dep_prep": DEPARTEMENT_PREP, "dep_article": DEPARTEMENT_ARTICLE,
                   "reg_prep": REGION_PREP}
    wrong_table = []
    for rows in (d1, d2, s1, s2, s3, d3, r1):
        for r in rows:
            m = re.search(r"\{([a-z_]+)\}", r["template"])
            if not m:                       # a reworded row names its body outright
                continue
            code = r["bindings"].get("departement") or r["bindings"]["region"]
            want = slot_tables[m.group(1)].get(code)
            # 69 D3 is deliberately narrowed to "du Rhône"; it is still a 'de' form
            if r["rendered_slot"] != want and r["rendered_slot"] != "du Rhône":
                wrong_table.append(f"{m.group(1)}/{code}={r['rendered_slot']!r} "
                                   f"(want {want!r})")
    settled = set(MISSING_PRESIDENTS) | set(OVERRIDES)
    both = [c["binding"] for c in DECISIONS_NEEDED
            if c["binding"].split("/")[-1] in settled]
    gate("2o no decision is both open and answered", not both,
         f"{len(DECISIONS_NEEDED)} open decision(s)"
         + (f"; ALSO ANSWERED: {both}" if both else ""))

    gate("2n rendered slot matches the table its slot names", not wrong_table,
         f"{len(wrong_table)} row(s) rendered from the wrong grammar table"
         + (": " + "; ".join(wrong_table[:4]) if wrong_table else ""))

    if failures:
        print("\nBUILD FAILED - nothing written:\n  " + "\n  ".join(failures))
        sys.exit(1)

    (out / "valuesets").mkdir(parents=True, exist_ok=True)
    (out / "groundtruth").mkdir(parents=True, exist_ok=True)
    w = lambda p, o: p.write_text(json.dumps(o, indent=2, ensure_ascii=False), encoding="utf-8")
    w(out / "valuesets/fr_departement.json", vs_dep)
    w(out / "valuesets/fr_region.json", vs_reg)
    for name, rows in (("d1_senateurs", d1), ("d2_deputes", d2), ("s3_nb_senateurs", s3),
                       ("s1_siege_renouvele_2026", s1), ("s2_nb_elus_2026", s2),
                       ("d3_president_conseil_departemental", d3),
                       ("r1_president_conseil_regional", r1)):
        w(out / f"groundtruth/{name}.json", rows)
    elab = [r for r in d3 + r1 if "elaborate_answer" in r]
    w(out / "groundtruth/_elaborate_answers.json", {
        "note": "answers that are genuinely more than one name. Every defensible answer "
                "is carried; the legal position is stated. Re-checked monthly.",
        "count": len(elab),
        "rows": [{"binding": r["bindings"], "canonical": r["expected"],
                  **r["elaborate_answer"]} for r in elab]})
    w(out / "groundtruth/_no_answer.json", {
        "note": "bindings we ASK but have no answer key for - these must not reach a batch",
        "count": len(d3_todo) + len(r1_todo),
        "d3": d3_todo, "r1": r1_todo})
    # WRITTEN, not hand-maintained. The Charente decision was made on 2026-08-03 and
    # this file still listed it as open on 2026-08-04, so a settled question came back
    # to the user as an unsettled one. A register that is not rebuilt goes stale.
    w(out / "groundtruth/_decisions_needed.json", {
        "note": "genuinely contested answers - a human decides before capture",
        "cases": DECISIONS_NEEDED})
    w(out / "groundtruth/_review_name_variants.json", {
        "note": "the chamber and the RNE spell these differently and we accept BOTH. "
                "Heuristic match on a shared token >= 5 chars - confirm each is one person.",
        "cases": VARIANTS_REVIEW})
    w(out / "groundtruth/_superseded_by_chamber.json", {
        "note": "names the RNE lists that the chamber does not - titulaire replaced by "
                "suppléant, or RNE stale. NOT accepted as answers.",
        "d1": d1_sup, "d2": d2_sup})
    w(out / "groundtruth/_manual_patch_needed.json",
      {"note": "bindings we ASK but cannot answer from the RNE - need a source",
       "d3": d3_todo, "r1": r1_todo})
    w(out / "groundtruth/_dropped_bindings.json",
      {"note": "bindings NOT asked - the body does not exist, so the question "
               "would presuppose something false",
       "d3": d3_drop, "r1": r1_drop})
    w(out / "groundtruth/_out_of_scope.json", {
        "note": "non-territorial constituencies - no {dep_prep} template applies",
        "senateurs": {k: len(v) for k, v in sorted(sen_out.items())},
        "deputes": {k: len(v) for k, v in sorted(dep_out.items())}})

    # Re-read what actually landed. This build has twice produced a log that
    # disagreed with the files (rows appended after the write loop), so trust the
    # disk, not the variables.
    on_disk = {}
    for name in ("d1_senateurs", "d2_deputes", "s3_nb_senateurs",
                 "s1_siege_renouvele_2026", "s2_nb_elus_2026",
                 "d3_president_conseil_departemental", "r1_president_conseil_regional"):
        on_disk[name] = len(json.loads(
            (out / f"groundtruth/{name}.json").read_text(encoding="utf-8")))
    expected = dict(d1_senateurs=len(d1), d2_deputes=len(d2), s3_nb_senateurs=len(s3),
                    s1_siege_renouvele_2026=len(s1), s2_nb_elus_2026=len(s2),
                    d3_president_conseil_departemental=len(d3),
                    r1_president_conseil_regional=len(r1))
    mismatch = {k: (expected[k], on_disk[k]) for k in expected if expected[k] != on_disk[k]}
    gate("3a written == built", not mismatch,
         f"{sum(on_disk.values())} rows on disk"
         + (f"  MISMATCH (built, on-disk): {mismatch}" if mismatch else ""))
    if mismatch:
        sys.exit("BUILD FAILED: files on disk do not match what was built")

    n = len(d1) + len(d2) + len(s3) + len(s1) + len(s2) + len(d3) + len(r1)
    print(f"\nWROTE  value sets: 101 + 18")
    print(f"       ground truth: D1 {len(d1)}  D2 {len(d2)}  S3 {len(s3)}  "
          f"S1 {len(s1)}  S2 {len(s2)}  D3 {len(d3)}  R1 {len(r1)}  = {n} rows")
    print(f"       manual patch needed: {len(d3_todo) + len(r1_todo)} rows")
    n_bind = (101 + 101 + len(s3) + len(s1) + len(s2)
              + len(d3) + len(d3_todo) + len(r1) + len(r1_todo))
    print(f"       dropped bindings (no such body): {len(d3_drop) + len(r1_drop)}")
    print(f"\nloaded template×bindings: {n_bind} across 7 templates")


if __name__ == "__main__":
    main()
