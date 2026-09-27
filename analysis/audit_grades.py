#!/usr/bin/env python3
"""Audit a grading pass: coverage, verdict distributions, per-provider stats,
critical errors, and internal-consistency checks on the grader's output.

Usage: python3 audit_grades.py [pass_label]   (default pass1)
"""
import json
import os
import re
import sys
import collections
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "chat-probe")
POINTS = {"correct": 1.0, "partial": 0.5, "missing": 0.0, "wrong": 0.0}


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "pass1"
    grades = [json.loads(l) for l in open(os.path.join(DATA, f"grades_{label}.jsonl"))]
    recs = {r["recordId"]: r for r in (json.loads(l) for l in open(os.path.join(DATA, "pilot_full.jsonl")))}
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))

    # -- coverage --
    failed = [g for g in grades if not g.get("grade")]
    print(f"coverage: {len(grades)-len(failed)}/{len(grades)} graded; failures: "
          f"{[(g['provider'], g['questionId'], g['repIndex']) for g in failed] or 'none'}")
    bad_items = []
    for g in grades:
        if not g.get("grade"):
            continue
        want = [it["id"].upper() for it in rubrics[g["questionId"]]["items"]]
        got = [i["id"].strip().upper().strip("[]") for i in g["grade"]["items"]]
        if sorted(got) != sorted(set(got)) or set(want) - set(got):
            bad_items.append((g["provider"], g["questionId"], g["repIndex"], got))
    print(f"item-coverage problems (dupes/missing): {bad_items or 'none'}")

    # -- verdict distribution --
    dist = collections.Counter()
    per_prov = collections.defaultdict(collections.Counter)
    for g in grades:
        if not g.get("grade"):
            continue
        for i in g["grade"]["items"]:
            dist[i["verdict"]] += 1
            per_prov[g["provider"]][i["verdict"]] += 1
    print(f"\nverdicts overall: {dict(dist)}")
    for p, c in sorted(per_prov.items()):
        print(f"  {p}: {dict(c)}")

    # -- headline stats per provider --
    print("\nper provider:")
    for p in sorted(per_prov):
        gs = [g for g in grades if g["provider"] == p and g.get("grade")]
        scores, wrongs, crits = [], 0, 0
        fact_wrong_items = collections.Counter()
        for g in gs:
            items = g["grade"]["items"]
            pts = sum(POINTS.get(i["verdict"], 0) for i in items)
            scores.append(pts / len(items))
            fact_wrong = [i for i in items
                          if i["verdict"] == "wrong" and i["id"].upper().strip("[]") not in ("SRC", "LANG")]
            if fact_wrong:
                wrongs += 1
                for i in fact_wrong:
                    fact_wrong_items[(g["questionId"], i["id"])] += 1
            if g["grade"].get("critical_error"):
                crits += 1
        print(f"  {p}: n={len(gs)}  mean score {statistics.mean(scores)*100:.0f}%  "
              f"misinfo rate {wrongs}/{len(gs)} ({100*wrongs/len(gs):.0f}%)  "
              f"critical errors {crits}")
        top = fact_wrong_items.most_common(5)
        if top:
            print(f"     most-wrong items: {top}")

    # -- critical errors listed --
    print("\ncritical errors:")
    for g in grades:
        if g.get("grade") and g["grade"].get("critical_error"):
            print(f"  {g['provider']} {g['questionId']} r{g['repIndex']}: "
                  f"{g['grade'].get('critical_reason','')[:130]}")

    # -- internal consistency checks --
    print("\nconsistency checks:")
    # (a) critical_error flag should match a wrong verdict on a critical rubric item
    mism = 0
    for g in grades:
        if not g.get("grade"):
            continue
        crit_ids = {it["id"].upper() for it in rubrics[g["questionId"]]["items"] if it["crit"]}
        has_crit_wrong = any(i["verdict"] == "wrong" and i["id"].upper().strip("[]") in crit_ids
                             for i in g["grade"]["items"])
        if bool(g["grade"].get("critical_error")) != has_crit_wrong:
            mism += 1
            print(f"  flag/item mismatch: {g['provider']} {g['questionId']} r{g['repIndex']} "
                  f"(flag={g['grade'].get('critical_error')}, crit-wrong-item={has_crit_wrong})")
    if not mism:
        print("  critical flag <-> critical wrong item: all consistent")
    # (b) justification/verdict polarity smell test
    smells = 0
    for g in grades:
        if not g.get("grade"):
            continue
        for i in g["grade"]["items"]:
            j = i["justification"].lower()
            if i["verdict"] == "correct" and re.search(r"\b(does not|doesn't|fails|omits|contradicts|fabricat)", j):
                smells += 1
                print(f"  smell: {g['provider']} {g['questionId']} r{g['repIndex']} {i['id']} "
                      f"correct but: {i['justification'][:110]}")
    if not smells:
        print("  verdict/justification polarity: no smells")
    # (c) zero-citation records should not earn SRC
    viol = 0
    for g in grades:
        if not g.get("grade"):
            continue
        rec = recs[g["recordId"]]
        real = [c for c in rec.get("citations") or [] if c.get("via") != "map-widget"]
        src = next((i for i in g["grade"]["items"] if i["id"].upper().strip("[]") == "SRC"), None)
        if not real and src and src["verdict"] == "correct":
            viol += 1
            print(f"  SRC without citations: {g['provider']} {g['questionId']} r{g['repIndex']}")
    if not viol:
        print("  SRC never awarded to zero-citation answers")

    # -- spend --
    tin = sum(g.get("in_tok") or 0 for g in grades)
    tout = sum(g.get("out_tok") or 0 for g in grades)
    lats = sorted(g["latency"] for g in grades if g.get("latency"))
    print(f"\nspend: {tin}+{tout} tok = ${tin*0.09/1e6+tout*0.18/1e6:.3f}; "
          f"median latency {lats[len(lats)//2] if lats else '-'}s")


if __name__ == "__main__":
    main()
