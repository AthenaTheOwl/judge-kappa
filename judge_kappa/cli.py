"""judge-kappa: is this LLM judge fit to grade? One report, one exit code.

Exit 0 when every threshold holds, 1 when any fails, 2 on bad input, 3 when no
check fails but a kappa is undefined (one label throughout; DEC-JK-003).
"""

from __future__ import annotations

import argparse
import json
import sys

from judge_kappa.core import (bootstrap_kappa, cohen_kappa, parse_swap_map, position_flip_rate, read_labels,
                              run_stability)

EXIT_PASS, EXIT_FAIL, EXIT_BAD_INPUT, EXIT_UNDEFINED = 0, 1, 2, 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="judge-kappa", description=__doc__.splitlines()[0])
    p.add_argument("gold", help="CSV of item_id,label: the human (gold) labels")
    p.add_argument("judge", help="CSV of item_id,label: the judge's first run")
    p.add_argument("--retest", action="append", help="CSV from another run of the same judge on the same items; repeat for more runs (test-retest kappa uses the first)")
    p.add_argument("--positive", help="the label whose rate is the judge's score; needed for the detection floor")
    p.add_argument("--gate-margin", type=float, help="the gap between your score and its gate threshold; fails unless it exceeds the detection floor")
    p.add_argument("--swapped", help="CSV from a run with the answer positions exchanged")
    p.add_argument("--swap-map", default="A=B,B=A", help="translate swapped-run labels back (default: A=B,B=A)")
    p.add_argument("--min-kappa", type=float, default=0.6, help="minimum kappa against gold (default 0.6)")
    p.add_argument("--min-retest", type=float, default=0.8, help="minimum test-retest kappa (default 0.8)")
    p.add_argument("--max-flip", type=float, default=0.1, help="maximum position-flip rate (default 0.1)")
    p.add_argument("--resamples", type=int, default=2000,
                   help="bootstrap resamples for each kappa's 95%% confidence interval (default 2000; 0 turns it off)")
    p.add_argument("--seed", type=int, default=0, help="random seed for the bootstrap (default 0)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    return p


def run(args: argparse.Namespace) -> tuple[dict, bool]:
    gold = read_labels(args.gold)
    first = read_labels(args.judge)
    if args.resamples < 0:
        raise ValueError("--resamples must be 0 or more")
    report: dict = {"checks": []}

    def interval(reference: dict[str, str], other: dict[str, str]) -> dict | None:
        ci = bootstrap_kappa(reference, other, args.resamples, args.seed)
        if ci is None:
            return None
        return {"level": ci.level, "low": round(ci.low, 6), "high": round(ci.high, 6),
                "method": "percentile bootstrap over items", "resamples": ci.resamples, "seed": ci.seed,
                "undefined_resamples": ci.undefined}

    def check(name: str, value: float | None, op: str, bound: float, **extra) -> None:
        if value is None:  # an undefined statistic neither passes nor fails (DEC-JK-003)
            report["checks"].append({"check": name, "value": None, "threshold": f"{op} {bound}", "pass": False,
                                     "status": "undefined", **extra})
            return
        ok = {">=": value >= bound, "<=": value <= bound, "<": value < bound}[op]
        report["checks"].append({"check": name, "value": round(value, 4), "threshold": f"{op} {bound}", "pass": ok,
                                 "status": "pass" if ok else "fail", **extra})

    vs_gold = cohen_kappa(gold, first)
    check("kappa_vs_gold", vs_gold.kappa, ">=", args.min_kappa, n=vs_gold.n, observed=round(vs_gold.observed, 4),
          chance=round(vs_gold.expected, 4), missing=vs_gold.missing, note=vs_gold.note, ci=interval(gold, first))
    if args.gate_margin is not None and (not args.positive or not args.retest):
        raise ValueError("--gate-margin needs --positive and at least one --retest")
    retests = [read_labels(path) for path in args.retest or []]
    if retests:
        retest = cohen_kappa(first, retests[0])
        check("test_retest_kappa", retest.kappa, ">=", args.min_retest, n=retest.n, observed=round(retest.observed, 4),
              missing=retest.missing, note=retest.note, ci=interval(first, retests[0]))
    if args.swapped:
        flip = position_flip_rate(first, read_labels(args.swapped), parse_swap_map(args.swap_map))
        check("position_flip_rate", flip.rate, "<=", args.max_flip, n=flip.n, flips=flip.flips, flipped_items=flip.flipped_items)
    if retests and (len(retests) > 1 or args.positive):
        stab = run_stability([first] + retests, args.positive)
        report["stability"] = {"runs": stab.runs, "n": stab.n, "verdict_move_rate": round(stab.move_rate, 4),
                               "moved_items": stab.moved_items, "positive": args.positive,
                               "positive_rates": [round(r, 4) for r in stab.rates],
                               "detection_floor": None if stab.floor is None else round(stab.floor, 4)}
        if args.gate_margin is not None:
            check("detection_floor", stab.floor, "<", args.gate_margin, n=stab.n, runs=stab.runs)
    statuses = {c["status"] for c in report["checks"]}
    report["status"] = "fail" if "fail" in statuses else "undefined" if "undefined" in statuses else "pass"
    report["pass"] = report["status"] == "pass"
    return report, report["pass"]


def render(report: dict) -> str:
    lines = ["judge-kappa report"]
    for c in report["checks"]:
        mark = c["status"].upper()
        extra = f"  n={c['n']}"
        if "observed" in c:
            extra += f"  raw agreement={c['observed']:.3f}"
        if c.get("missing"):
            extra += f"  missing={c['missing']}"
        if "flips" in c:
            extra += f"  flips={c['flips']}"
        if "runs" in c:
            extra += f"  runs={c['runs']}"
        value = "undefined" if c["value"] is None else f"{c['value']:.3f}"
        lines.append(f"  [{mark}] {c['check']:<20} {value}  (needs {c['threshold']}){extra}")
        if c.get("ci"):
            ci = c["ci"]
            bound = float(c["threshold"].split()[1])
            dropped = f", {ci['undefined_resamples']} undefined resamples left out" if ci["undefined_resamples"] else ""
            spans = "; the interval spans the threshold" if ci["low"] < bound <= ci["high"] else ""
            lines.append(f"         {ci['level']:.0%} CI [{ci['low']:.3f}, {ci['high']:.3f}]  (n={c['n']}, percentile bootstrap, "
                         f"{ci['resamples']} resamples, seed {ci['seed']}{dropped}{spans})")
        if c.get("note"):
            lines.append(f"         note: {c['note']}")
    st = report.get("stability")
    if st:
        lines.append(f"  runs={st['runs']}  verdict_move_rate={st['verdict_move_rate']:.3f}  ({len(st['moved_items'])} of {st['n']} items changed label in some run)")
        if st["detection_floor"] is None:
            lines.append("  detection_floor: pass --positive LABEL to compute it")
        else:
            lines.append(f"  detection_floor={st['detection_floor']:.3f}  (observed lower bound: largest gap in the rate of {st['positive']!r} between any two runs; "
                         "a score change smaller than this is indistinguishable from the judge's own noise)")
    verdict = {"pass": "fit to grade", "fail": "not fit to grade",
               "undefined": "undefined (insufficient label variation); not fit to grade"}
    lines.append("verdict: " + verdict[report["status"]])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, ok = run(args)
    except (OSError, ValueError) as exc:
        print(f"judge-kappa: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    print(json.dumps(report, indent=2) if args.json else render(report))
    return {"pass": EXIT_PASS, "fail": EXIT_FAIL, "undefined": EXIT_UNDEFINED}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
