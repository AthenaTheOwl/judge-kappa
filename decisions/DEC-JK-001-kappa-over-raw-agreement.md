# DEC-JK-001 — gate on chance-corrected agreement, not raw agreement

## Status

Accepted (2026-09-23).

Amended by DEC-JK-003 (2026-10-19): an undefined kappa is reported as undefined (exit 3), not as 1.0.

## Context

LLM judges are usually validated by reporting how often they match human labels. On skewed label sets that number is inflated by chance: a judge that always answers the majority label can match 90 percent of a 90/10 gold set while carrying no information.

## Decision

The gate is Cohen's kappa against gold, plus test-retest kappa and the position-swap flip rate. Raw agreement is printed beside kappa but never gates. A missing verdict counts as a disagreement. When both raters use one identical label throughout, kappa is undefined and reported as 1.0 with a note.

## Alternatives considered

- Raw agreement: easy to read, inflated by label skew.
- Krippendorff's alpha: handles many raters and missing data, but v0.1 compares exactly two label sets at a time, where kappa is the standard and hand-checkable.
- Calling the judge from this tool: couples the gate to a provider; saved CSVs keep it provider-neutral.

## Evidence

`examples/textbook/` reproduces the standard worked example (po 0.70, pe 0.50, kappa 0.40), pinned in `tests/test_judge_kappa.py`.

## Rollback

Thresholds are flags; a team that must gate on raw agreement can lower `--min-kappa` and read `observed` from `--json`.
