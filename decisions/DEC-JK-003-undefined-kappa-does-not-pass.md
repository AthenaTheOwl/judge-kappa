# DEC-JK-003 — an undefined kappa does not pass

## Status

Accepted (2026-10-19). Amends DEC-JK-001.

## Context

DEC-JK-001 reported kappa as 1.0, with a note, when both label sets use one identical label throughout. Chance agreement is then 1 and kappa is 0/0, so the 1.0 was a convention, not a measurement. The exit code turned that convention into a pass: on a 20-item gold set labelled `pass` throughout, a judge that always answers `pass` scored 1.000, "fit to grade", exit 0. On the same gold set a judge that dissents once (raw agreement 0.95) scores 0.000 and fails. The judge that carries no information passed; the one that showed it can tell items apart failed.

## Decision

An undefined kappa is reported as undefined, never as a number. `cohen_kappa` returns `kappa=None` with a note. In the report the check is `[UNDEFINED]`, with `"value": null`, `"status": "undefined"` and `"pass": false` in `--json`. It neither passes nor fails a threshold.

Exit codes: 0 every check passes, 1 any check fails, 2 bad input, 3 no check fails but at least one kappa is undefined. A failed check outranks an undefined one, because a definite failure already settles the verdict. Exit 3 is non-zero, so a CI line that tests for 0 does not let it through. The verdict line reads `undefined (insufficient label variation); not fit to grade`.

The same rule covers test-retest kappa: two runs that each use one identical label throughout are undefined. DEC-JK-001's other decisions (kappa gates, raw agreement never gates, a missing verdict counts as a disagreement) stand.

## Alternatives considered

- Keep 1.0 and rely on the note: the note does not change the exit code, and the exit code is what CI reads.
- Report 0.0: treats "no variation to measure" as "no better than chance", and makes this case indistinguishable from a real chance-level judge.
- Exit 2 (bad input): the files are well formed; the gold set lacks variation. A distinct code lets a caller tell the two apart.

## Evidence

`examples/one_label/` holds the 20-item all-`pass` gold set and an always-`pass` judge; `tests/test_judge_kappa.py` pins exit 3 for it, exit 1 when another check also fails, and `kappa is None` in `cohen_kappa`. CI runs the fixture and checks for exit 3.

## Rollback

Revert this record and the change to `judge_kappa/core.py` and `judge_kappa/cli.py`. Callers that only test for exit 0 need no change either way.
