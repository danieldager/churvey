#!/usr/bin/env python3
"""Stage 6 - render every loaded template x binding to the literal prompt string
a runner would send, for the native-speaker grammaticality read (Gate 1c/6).

321 prompts is few enough to read every one, so this emits all of them rather
than a sample. Refuses to write unless prepositions.AUDITED is True, because an
ungrammatical prompt is not a weaker probe of a chatbot - it is a different one,
and the capture cannot be repaired afterwards. Use --review to produce the sheet
the auditor marks up.

  france/render.py --review          # emit the audit sheet (works unaudited)
  france/render.py                   # emit runnable prompts (needs sign-off)
"""
import argparse
import json
import re
from pathlib import Path

from prepositions import AUDITED

GT = ["d1_senateurs", "d2_deputes", "s3_nb_senateurs",
      "s1_siege_renouvele_2026", "s2_nb_elus_2026",
      "d3_president_conseil_departemental", "r1_president_conseil_regional"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/fr")
    ap.add_argument("--review", action="store_true",
                    help="emit the audit sheet instead of runnable prompts")
    args = ap.parse_args()
    data = Path(args.data)

    prompts = []
    for name in GT:
        for row in json.loads((data / "groundtruth" / f"{name}.json").read_text(encoding="utf-8")):
            # a per-binding reworded template (976 Mayotte) names its body outright
            # and has no slot at all
            slot = re.search(r"\{[a-z_]+\}", row["template"])
            prompts.append({
                "template_id": name,
                "binding": next(iter(row["bindings"].values())),
                "prompt": (row["template"].replace(slot.group(), row["rendered_slot"])
                           if slot else row["template"]),
                "expected": row["expected"],
            })

    if args.review:
        out = data / "review" / "gate6_grammaticality.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Gate 6 - grammaticality read",
            "",
            f"{len(prompts)} prompts, all of them. Mark each OK or write the correction.",
            "The only thing under review is whether a French speaker would write this",
            "sentence. Do not check the answers - that is Gate 2d.",
            "",
        ]
        for tid in GT:
            rows = [p for p in prompts if p["template_id"] == tid]
            lines += [f"## {tid} ({len(rows)})", "", "| # | prompt | OK? | correction |",
                      "|---|---|---|---|"]
            lines += [f"| {p['binding']} | {p['prompt']} |  |  |" for p in rows]
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out} - {len(prompts)} prompts for review")
        return

    if not AUDITED:
        raise SystemExit(
            "REFUSING to emit runnable prompts: prepositions.AUDITED is False.\n"
            "Run --review, get the 119 preposition rows signed off, then flip the flag.")

    out = data / "prompts.jsonl"
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prompts),
                   encoding="utf-8")
    print(f"wrote {out} - {len(prompts)} prompts")


if __name__ == "__main__":
    main()
