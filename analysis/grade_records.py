#!/usr/bin/env python3
"""Grade an arbitrary capture file (the entrypoint for each new provider run),
optionally merging the fresh grades onto an existing grades file.

Uses the same validated DeepSeek-V4-Flash grader (thinking mode) as grade_pilot.

Usage:
  # grade gemini+deepseek from a run export, merge onto the corrected pilot grades
  python3 grade_records.py 'run_...(1).jsonl' --label gd \
        --providers gemini,deepseek --merge grades_pass1_v2.jsonl --out grades_4models.jsonl

Reads  <input> (path rel to ../data/chat-probe or absolute) + rubrics.json
Writes ../data/chat-probe/grades_<label>.jsonl        (just the newly graded rows)
       ../data/chat-probe/<out>  (if --merge given: base with these rows added/replaced)
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grade_pilot import grade_one
from validate_grader import api_key

DATA = os.path.join(HERE, "..", "data", "chat-probe")


def dpath(p):
    return p if os.path.isabs(p) else os.path.join(DATA, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="capture jsonl (one record per line)")
    ap.add_argument("--label", required=True, help="output label -> grades_<label>.jsonl")
    ap.add_argument("--providers", default=None, help="comma list to keep (default: all)")
    ap.add_argument("--merge", default=None, help="base grades file to merge onto")
    ap.add_argument("--out", default=None, help="merged output filename (with --merge)")
    ap.add_argument("--only-new", action="store_true",
                    help="skip records already graded in --merge base (resume workflow)")
    ap.add_argument("--skip-questions", default=None,
                    help="comma list of question ids to NOT grade (e.g. P3, which is dropped)")
    args = ap.parse_args()

    keep = set(args.providers.split(",")) if args.providers else None
    skipq = set(args.skip_questions.split(",")) if args.skip_questions else set()
    key = api_key()
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))
    recs = [json.loads(l) for l in open(dpath(args.input)) if l.strip()]
    todo = [r for r in recs if r.get("status", "ok") == "ok"
            and (keep is None or r["provider"] in keep)
            and str(r["questionId"]) not in skipq]
    if args.only_new:
        if not args.merge:
            sys.exit("--only-new requires --merge <base grades file>")
        # only records with a real grade count as done — failed rows (grade: null)
        # must be re-graded, not skipped.
        done = {json.loads(l)["recordId"] for l in open(dpath(args.merge))
                if l.strip() and json.loads(l).get("grade")}
        before = len(todo)
        todo = [r for r in todo if r["recordId"] not in done]
        print(f"--only-new: {before - len(todo)} already graded, {len(todo)} to grade")
    if not todo:
        sys.exit("no ok records match filter")
    prov = sorted({r["provider"] for r in todo})
    print(f"grading {len(todo)} records ({prov}) with thinking mode ...")

    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        new = list(ex.map(lambda r: grade_one(r, rubrics[str(r["questionId"])], key), todo))

    new_path = dpath(f"grades_{args.label}.jsonl")
    with open(new_path, "w") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = sum(1 for r in new if r.get("grade"))
    tin = sum(r.get("in_tok") or 0 for r in new)
    tout = sum(r.get("out_tok") or 0 for r in new)
    print(f"\n{ok}/{len(new)} graded in {(time.time()-t0)/60:.1f} min; "
          f"{tin}+{tout} tok = ${tin*0.09/1e6 + tout*0.18/1e6:.4f}")
    print("wrote", new_path)

    if args.merge:
        base = [json.loads(l) for l in open(dpath(args.merge))]
        newby = {r["recordId"]: r for r in new}
        seen = set()
        merged = []
        for r in base:
            merged.append(newby.get(r["recordId"], r))
            seen.add(r["recordId"])
        for r in new:  # append records not already in base
            if r["recordId"] not in seen:
                merged.append(r)
        out = dpath(args.out or args.merge.replace(".jsonl", "_merged.jsonl"))
        with open(out, "w") as f:
            for r in merged:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"merged -> {out} ({len(merged)} records)")


if __name__ == "__main__":
    main()
