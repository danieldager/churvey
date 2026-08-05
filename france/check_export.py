"""Audit the export package before it is sent to anyone.

Reads only the emitted JSON - never the pipeline - so it catches what the pipeline knows
implicitly and the file does not say. Run after every export_package.py.

    uv run python france/check_export.py data/fr/export/civic_ai_audit_france_2026-08-03.json
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

fails, warns = [], []


def check(ok, label, detail=""):
    (print if ok else fails.append)(f"  [{'PASS' if ok else 'FAIL'}] {label}" +
                                    (f": {detail}" if detail else ""))
    if not ok:
        print(f"  [FAIL] {label}" + (f": {detail}" if detail else ""))


def warn(ok, label, detail=""):
    if ok:
        print(f"  [PASS] {label}" + (f": {detail}" if detail else ""))
    else:
        warns.append(label)
        print(f"  [WARN] {label}" + (f": {detail}" if detail else ""))


def main(path):
    raw = Path(path).read_bytes()
    check(raw.decode("utf-8") == raw.decode("utf-8"), "file is valid UTF-8")
    pkg = json.loads(raw)
    gt = pkg["ground_truth"]
    vs = {v["name"]: v for v in pkg["value_sets"]}
    tpl = {t["id"]: t for t in pkg["question_templates"]}
    meta = pkg["meta"]["counts"]

    print("\n=== 1. STRUCTURE ===")
    check(set(pkg) == {"meta", "jurisdiction_levels", "value_sets", "question_templates",
                       "ground_truth", "exceptions", "known_limitations",
                       "targets_we_would_add"},
          "top-level keys are the expected eight", str(sorted(pkg)))
    required = {"template_id", "template", "bindings", "rendered_prompt", "shape",
                "expected", "authority", "as_of", "validity"}
    missing = [i for i, r in enumerate(gt) if not required <= set(r)]
    check(not missing, "every row has the 10 required fields", f"{len(missing)} rows short")

    print("\n=== 2. COUNTS AGREE WITH META ===")
    check(len(gt) == meta["questions"] == meta["answer_keys"],
          "row count matches meta", f"{len(gt)} rows vs meta {meta['questions']}")
    check(sum(v["n_members"] for v in pkg["value_sets"]) == meta["locales"],
          "locale count matches meta", str(meta["locales"]))
    per = Counter(r["template_id"] for r in gt)
    check(dict(per) == meta["by_template"], "per-template counts match meta", str(dict(per)))
    check(all(t["n_bindings"] == per[t["id"]] for t in pkg["question_templates"]),
          "each template's n_bindings matches its actual rows")
    check(all(v["n_members"] == len(v["members"]) for v in pkg["value_sets"]),
          "each value set's n_members matches its actual members")
    check(meta["gaps"] == 0 and all(r["expected"] not in (None, "", []) for r in gt),
          "no row has an empty answer")

    print("\n=== 3. REFERENTIAL INTEGRITY ===")
    members = {n: {m["code"] for m in v["members"]} for n, v in vs.items()}
    orphans = []
    for r in gt:
        code = next(iter(r["bindings"].values()))
        if not any(code in members[n] for n in tpl[r["template_id"]]["value_sets"]):
            orphans.append(f"{r['template_id']}/{code}")
    check(not orphans, "every binding resolves to a declared value-set member", str(orphans))
    check(all(vsn in vs for t in pkg["question_templates"] for vsn in t["value_sets"]),
          "every template's declared value sets exist")
    dupes = [k for k, n in Counter(
        (r["template_id"], next(iter(r["bindings"].values()))) for r in gt).items() if n > 1]
    check(not dupes, "no duplicate (template, binding) pair", str(dupes))
    check(all(t["id"] in per for t in pkg["question_templates"]),
          "no template has zero rows")

    print("\n=== 4. THE RENDERED PROMPT IS ACTUALLY RENDERED ===")
    unfilled = [r["rendered_prompt"] for r in gt if re.search(r"\{[a-z_]+\}", r["rendered_prompt"])]
    check(not unfilled, "no prompt still contains an unsubstituted {slot}", str(unfilled[:3]))
    # not "contains the place name somewhere" - that passes an S3 row rendered from the
    # article table ("sénateurs l'Ain") because "l'Ain" still contains "Ain". Substitute
    # the exact field the template's own slot declares and demand the strings match.
    bad_slot = []
    for r in gt:
        code = next(iter(r["bindings"].values()))
        t = tpl[r["template_id"]]
        if not t["slots"]:
            continue
        slot = t["slots"][0]
        member = next((m for m in vs[slot["value_set"]]["members"] if m["code"] == code), None)
        if member is None:
            continue
        want = t["text"].replace("{" + slot["name"] + "}", member[slot["member_field"]])
        if want != r["rendered_prompt"] and "scope_note" not in r \
                and r["template"] == t["text"]:
            bad_slot.append(f"{r['template_id']}/{code}: {r['rendered_prompt']!r} "
                            f"!= {want!r}")
    check(not bad_slot, "every prompt is its template with the declared member field "
                        "substituted", str(bad_slot[:4]))
    check(all(r["rendered_prompt"].strip().endswith("?") for r in gt),
          "every prompt is a question")
    check(all("  " not in r["rendered_prompt"] for r in gt), "no double spaces in prompts")

    print("\n=== 5. ANSWER SHAPES ===")
    by_shape = Counter(r["shape"] for r in gt)
    check(all(r["shape"] == tpl[r["template_id"]]["shape"] for r in gt),
          "row shape matches its template's shape", str(dict(by_shape)))
    lists = [r for r in gt if r["shape"] == "list"]
    check(all(isinstance(r["expected"], list) and r["expected"] for r in lists),
          "list rows hold a non-empty list")
    check(all(r.get("expected_cardinality") == len(r["expected"]) for r in lists),
          "expected_cardinality equals the number of names",
          str([f"{r['template_id']}/{next(iter(r['bindings'].values()))}" for r in lists
               if r.get("expected_cardinality") != len(r["expected"])][:5]))
    names = [r for r in gt if r["shape"] == "name"]
    check(all(isinstance(r["expected"], str) and r["expected"].strip() for r in names),
          "name rows hold a non-empty string")
    nums = [r for r in gt if r["shape"] == "number"]
    check(all(isinstance(r["expected"], int) and r["expected"] >= 0 for r in nums),
          "number rows hold a non-negative integer")
    yn = [r for r in gt if r["shape"] == "yes_no"]
    check(all(r["expected"] in ("oui", "non") for r in yn),
          "yes_no rows are exactly oui or non", str(Counter(r["expected"] for r in yn)))

    print("\n=== 6. CROSS-TEMPLATE CONSISTENCY ===")
    d1 = {next(iter(r["bindings"].values())): r for r in gt if r["template_id"] == "D1"}
    s3 = {next(iter(r["bindings"].values())): r for r in gt if r["template_id"] == "S3"}
    s2 = {next(iter(r["bindings"].values())): r for r in gt if r["template_id"] == "S2"}
    s1 = {next(iter(r["bindings"].values())): r for r in gt if r["template_id"] == "S1"}
    check(all(s3[c]["expected"] == len(d1[c]["expected"]) for c in s3),
          "S3 count equals the number of senators D1 names")
    check(all(s2[c]["expected"] <= s3[c]["expected"] for c in s2),
          "S2 seats renewed never exceeds the département's total seats",
          str([c for c in s2 if s2[c]["expected"] > s3[c]["expected"]]))
    mism = [c for c in s1 if (s1[c]["expected"] == "oui") != (s2[c]["expected"] > 0)]
    check(not mism, "S1 says oui exactly when S2 is greater than zero", str(mism))
    vsd = {m["code"]: m for m in vs["fr_departement"]["members"]}
    check(all(vsd[c]["n_senateurs"] == s3[c]["expected"] for c in s3 if c in vsd),
          "S3 matches n_senateurs on the value-set member")
    check(sum(r["expected"] for r in s3.values()) == 328,
          "territorial senate seats sum to 328",
          str(sum(r["expected"] for r in s3.values())))

    print("\n=== 7. NAMES AND ENCODING ===")
    forms = [r for r in gt if "accepted_forms" in r]
    bad = [r["template_id"] for r in forms
           if not all(n in r["accepted_forms"] for n in r["expected"])]
    check(not bad, "every expected name has an accepted_forms entry", str(set(bad)))
    check(all(v for r in forms for v in r["accepted_forms"].values()),
          "no accepted_forms entry is empty")
    blob = json.dumps(pkg, ensure_ascii=False)
    check("Ã©" not in blob and "â€" not in blob and "�" not in blob,
          "no mojibake or replacement characters")
    check(blob == unicodedata.normalize("NFC", blob), "all text is NFC-normalised")
    accented = sum(1 for r in gt if any(ord(ch) > 127 for ch in str(r["expected"])))
    warn(accented > 100, "accents survived in answers", f"{accented} rows carry non-ASCII")

    print("\n=== 8. NOTHING INTERNAL LEAKED ===")
    # "Claude" alone is a false positive - it is a common French given name
    # (Claude Malhuret, Jean-Claude Anglars, Claude Riboulet...). Match the tool, not the name.
    leaks = [p for p in ("/Users/", "TODO", "FIXME", "scratchpad", "NOT_FOR_LOAD",
                         "Claude Code", "Anthropic", "anthropic", "claude.ai",
                         "claude-opus", "LLM-generated") if p in blob]
    check(not leaks, "no local paths, TODOs or internal markers", str(leaks))
    check("69M" not in blob, "the dropped Métropole binding appears nowhere")

    print("\n=== 9. PROVENANCE IS COMPLETE ===")
    check(all(r["authority"] and r["as_of"] for r in gt),
          "every row names its authority and its as_of date")
    check(all(r["validity"] == "current" for r in gt),
          "every row is marked current", str(Counter(r["validity"] for r in gt)))
    check(set(Counter(r["authority"] for r in gt)) <= {
              "senat.fr api-senat/senateurs.json (Sénat, live register)",
              "data.assemblee-nationale.fr (AMO10, législature 17)",
              "RNE (Ministère de l'Intérieur, data.gouv.fr)",
              "operator (external verification, 2026-08-03)"},
          "every authority is one of the four declared sources",
          str(dict(Counter(r["authority"] for r in gt))))
    check("precedence" not in json.dumps(pkg), "the precedence field is gone entirely")
    check(bool(pkg["meta"].get("fields_we_added")) and
          bool(pkg["meta"].get("open_questions_for_you")),
          "meta declares what we added and where we guessed")
    variants = [r for r in gt if r["template"] != tpl[r["template_id"]]["text"]]
    check(all("template_variant_reason" in r for r in variants),
          "every row whose text differs from its template says why",
          f"{len(variants)} variant rows")
    check(all("note" in tpl[t] for t in {r["template_id"] for r in variants}),
          "every template with variant rows carries a note saying so")

    print("\n=== 10. LIMITATIONS ARE STATED ===")
    check(len(pkg["known_limitations"]) >= 5, "known_limitations is populated",
          f"{len(pkg['known_limitations'])} entries")
    check(all(k in pkg["exceptions"] for k in
              ("elaborate_answers", "open_decisions", "dropped_bindings", "out_of_scope",
               "name_variants_accepted", "rne_names_rejected")),
          "all six exception registers are present")
    ela = {b["binding"].get("departement") for b in pkg["exceptions"]["elaborate_answers"]["rows"]}
    inline = {next(iter(r["bindings"].values())) for r in gt if "also_accept" in r}
    check(ela == inline, "every elaborate answer is merged onto its row", f"{ela} vs {inline}")

    print(f"\n{'=' * 46}")
    print(f"{len(gt)} rows · {sum(v['n_members'] for v in pkg['value_sets'])} locales · "
          f"{len(pkg['question_templates'])} templates · {Path(path).stat().st_size/1024:.0f} KB")
    if fails:
        print(f"FAILED {len(fails)} check(s)")
        return 1
    print(f"ALL CHECKS PASS" + (f" ({len(warns)} warning)" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
