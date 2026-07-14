#!/usr/bin/env python3
"""Regrade selected question(s) with the current rubrics, merging the fresh
grades into a versioned full grades file. Use after correcting a rubric so you
don't re-spend on all 120 records.

Usage:
  python3 regrade.py P5                 # regrade one question
  python3 regrade.py P5 P3 16.6         # regrade several
  python3 regrade.py --base grades_pass1.jsonl --out grades_pass1_v2.jsonl P5

Reads  ../data/chat-probe/pilot_full.jsonl + rubrics.json
       ../data/chat-probe/<base>            (default grades_pass1.jsonl)
Writes ../data/chat-probe/<out>             (default <base stem>_v2.jsonl)
       ../data/chat-probe/grades_regrade_<qids>.jsonl   (just the regraded rows)
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grade_pilot import grade_one
from validate_grader import api_key

DATA = os.path.join(HERE, "..", "data", "chat-probe")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qids", nargs="+", help="question IDs to regrade, e.g. P5 16.6")
    ap.add_argument("--base", default="grades_pass1.jsonl", help="grades file to merge into")
    ap.add_argument("--out", default=None, help="output merged file (default <base>_v2)")
    args = ap.parse_args()
    qids = {str(q) for q in args.qids}
    out = args.out or args.base.replace(".jsonl", "_v2.jsonl")

    key = api_key()
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))
    recs = [json.loads(l) for l in open(os.path.join(DATA, "pilot_full.jsonl"))]
    todo = [r for r in recs if str(r["questionId"]) in qids]
    if not todo:
        sys.exit(f"no records match {sorted(qids)}")
    print(f"regrading {len(todo)} records for {sorted(qids)} (thinking mode) ...")

    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        new = list(ex.map(lambda r: grade_one(r, rubrics[str(r["questionId"])], key), todo))

    tag = "-".join(sorted(qids)).replace(".", "")
    regr_path = os.path.join(DATA, f"grades_regrade_{tag}.jsonl")
    with open(regr_path, "w") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    old = [json.loads(l) for l in open(os.path.join(DATA, args.base))]
    newby = {r["recordId"]: r for r in new}
    merged = [newby.get(r["recordId"], r) for r in old]
    out_path = os.path.join(DATA, out)
    with open(out_path, "w") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    oldby = {r["recordId"]: r for r in old}
    ok = sum(1 for r in new if r.get("grade"))
    tin = sum(r.get("in_tok") or 0 for r in new)
    tout = sum(r.get("out_tok") or 0 for r in new)
    print(f"\n{ok}/{len(new)} graded in {(time.time()-t0)/60:.1f} min; "
          f"{tin}+{tout} tok = ${tin*0.09/1e6 + tout*0.18/1e6:.4f}")
    print("wrote", regr_path)
    print("wrote", out_path)

    print("\n== per-record verdicts before -> after (changed items only) ==")
    for r in sorted(new, key=lambda x: (str(x["questionId"]), x["provider"], x["repIndex"])):
        head = f'{r["questionId"]} {r["provider"]} rep{r["repIndex"]}'
        if not r.get("grade"):
            print(f'  {head}: FAILED after retries')
            continue
        o = {i["id"]: i["verdict"] for i in oldby[r["recordId"]]["grade"]["items"]}
        n = {i["id"]: i["verdict"] for i in r["grade"]["items"]}
        chg = [f'{k} {o.get(k)}->{n[k]}' for k in n if o.get(k) != n[k]]
        ow = sum(1 for v in o.values() if v == "wrong")
        nw = sum(1 for v in n.values() if v == "wrong")
        print(f'  {head}: #wrong {ow}->{nw}' + (f'  [{", ".join(chg)}]' if chg else '  (no change)'))


if __name__ == "__main__":
    main()
