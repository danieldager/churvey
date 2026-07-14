#!/usr/bin/env python3
"""Recompute each record's critical_error / critical_reason in a grades file
from the CURRENT rubrics.json crit flags — deterministically, no LLM call.

critical_error is definitionally "a critical rubric item graded wrong", so after
you flip a crit flag you can refresh it here instead of re-grading. Verdicts are
left untouched. Rewrites the file in place (use --dry to preview).

Usage:
  python3 set_criticals.py grades_pass1_v2.jsonl
  python3 set_criticals.py grades_pass1_v2.jsonl --dry
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "chat-probe")


def norm(i):
    return i.upper().strip("[]")


def main():
    args = [a for a in sys.argv[1:] if a != "--dry"]
    dry = "--dry" in sys.argv
    if not args:
        sys.exit("usage: set_criticals.py <grades_file.jsonl> [--dry]")
    path = args[0] if os.path.isabs(args[0]) else os.path.join(DATA, args[0])
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))
    rows = [json.loads(l) for l in open(path)]

    changed = []
    for r in rows:
        g = r.get("grade")
        if not g:
            continue
        qid = str(r["questionId"])
        crit_ids = {norm(it["id"]) for it in rubrics[qid]["items"] if it.get("crit")}
        wrong_crit = [i for i in g["items"]
                      if i["verdict"] == "wrong" and norm(i["id"]) in crit_ids]
        new_flag = bool(wrong_crit)
        new_reason = ("; ".join(f'{qid} {norm(i["id"])}: {i["justification"]}'
                                for i in wrong_crit) if wrong_crit else "")
        if bool(g.get("critical_error")) != new_flag or (g.get("critical_reason") or "") != new_reason:
            changed.append((r, g.get("critical_error"), new_flag,
                            f'{r["provider"]}/{qid}/r{r["repIndex"]}'))
            if not dry:
                g["critical_error"] = new_flag
                g["critical_reason"] = new_reason

    print(f"{path}: {len(changed)} record(s) {'would change' if dry else 'changed'}")
    for _, old, new, tag in changed:
        print(f"  {tag}: critical_error {old} -> {new}")
    if not dry:
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("wrote", path)


if __name__ == "__main__":
    main()
