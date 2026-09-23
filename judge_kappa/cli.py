"""judge-kappa: is this LLM judge fit to grade? One report, one exit code.

Exit 0 when every threshold holds, 1 when any fails, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import sys

from judge_kappa.core import cohen_kappa, parse_swap_map, position_flip_rate, read_labels


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="judge-kappa", description=__doc__.splitlines()[0])
    p.add_argument("gold", help="CSV of item_id,label: the human (gold) labels")
    p.add_argument("judge", help="CSV of item_id,label: the judge's first run")
    p.add_argument("--retest", help="CSV from a second run of the same judge on the same items")
    p.add_argument("--swapped", help="CSV from a run with the answer positions exchanged")
    p.add_argument("--swap-map", default="A=B,B=A", help="translate swapped-run labels back (default: A=B,B=A)")
    p.add_argument("--min-kappa", type=float, default=0.6, help="minimum kappa against gold (default 0.6)")
    p.add_argument("--min-retest", type=float, default=0.8, help="minimum test-retest kappa (default 0.8)")
    p.add_argument("--max-flip", type=float, default=0.1, help="maximum position-flip rate (default 0.1)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    return p


def run(args: argparse.Namespace) -> tuple[dict, bool]:
    gold = read_labels(args.gold)
    first = read_labels(args.judge)
    report: dict = {"checks": []}

    def check(name: str, value: float, op: str, bound: float, **extra) -> None:
        ok = value >= bound if op == ">=" else value <= bound
        report["checks"].append({"check": name, "value": round(value, 4), "threshold": f"{op} {bound}", "pass": ok, **extra})

    vs_gold = cohen_kappa(gold, first)
    check("kappa_vs_gold", vs_gold.kappa, ">=", args.min_kappa, n=vs_gold.n, observed=round(vs_gold.observed, 4),
          chance=round(vs_gold.expected, 4), missing=vs_gold.missing, note=vs_gold.note)
    if args.retest:
        retest = cohen_kappa(first, read_labels(args.retest))
        check("test_retest_kappa", retest.kappa, ">=", args.min_retest, n=retest.n, observed=round(retest.observed, 4),
              missing=retest.missing, note=retest.note)
    if args.swapped:
        flip = position_flip_rate(first, read_labels(args.swapped), parse_swap_map(args.swap_map))
        check("position_flip_rate", flip.rate, "<=", args.max_flip, n=flip.n, flips=flip.flips, flipped_items=flip.flipped_items)
    report["pass"] = all(c["pass"] for c in report["checks"])
    return report, report["pass"]


def render(report: dict) -> str:
    lines = ["judge-kappa report"]
    for c in report["checks"]:
        mark = "PASS" if c["pass"] else "FAIL"
        extra = f"  n={c['n']}"
        if "observed" in c:
            extra += f"  raw agreement={c['observed']:.3f}"
        if c.get("missing"):
            extra += f"  missing={c['missing']}"
        if "flips" in c:
            extra += f"  flips={c['flips']}"
        lines.append(f"  [{mark}] {c['check']:<20} {c['value']:.3f}  (needs {c['threshold']}){extra}")
        if c.get("note"):
            lines.append(f"         note: {c['note']}")
    lines.append("verdict: " + ("fit to grade" if report["pass"] else "not fit to grade"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, ok = run(args)
    except (OSError, ValueError) as exc:
        print(f"judge-kappa: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
