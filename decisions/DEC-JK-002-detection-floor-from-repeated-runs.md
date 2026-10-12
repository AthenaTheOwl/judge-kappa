# DEC-JK-002 — report a detection floor from repeated runs

## Status

Accepted (2026-10-12).

## Context

A single retest shows whether a judge repeats itself, not how far its score moves between runs. A gate whose threshold sits within that movement passes or fails by luck. LangChain's judge-evaluation write-up (https://www.langchain.com/blog/jev-agent-evals-langsmith) frames the share of verdicts that move as the number to publish beside a judge-derived threshold.

## Decision

`--retest` is repeatable. The report adds `verdict_move_rate` (items whose label differs in any run; a skipped item counts as different) and `detection_floor` (largest gap in the `--positive` label's rate between any two runs). `--gate-margin X` fails unless X is strictly greater than the floor. The floor requires `--positive`; `--gate-margin` without it is bad input (exit 2). Test-retest kappa keeps using the first retest. With one `--retest` and no `--positive`, output is unchanged.

## Alternatives considered

- Standard deviation of the rate: needs more runs than people will pay for; the range is hand-checkable with five.
- A default positive label: wrong for multi-class judges.

## Evidence

`tests/test_judge_kappa.py` pins a hand-computed floor and the five-run example (floor 0.10).

## Rollback

The floor is observed from few runs and understates the true spread; treat it as a lower bound. Omit `--gate-margin` to keep the old gates only.
