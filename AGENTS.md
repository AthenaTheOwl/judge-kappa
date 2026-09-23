# AGENTS.md — judge-kappa

Operating contract for AI agents working in this repo. Conventions match the rest of the AthenaTheOwl portfolio.

## What this repo is

A standard-library CLI that decides whether an LLM judge is fit to grade: Cohen's kappa against human labels, test-retest kappa, and the position-swap flip rate, each with a threshold and one exit code (0 pass, 1 fail, 2 bad input).

## Rules

- Standard library only in `judge_kappa/`. No model calls; the tool reads saved verdicts.
- The textbook fixture (`examples/textbook/`) must keep producing kappa 0.40 exactly. It is the acceptance check; change it only with a DEC record.
- New statistics need a hand-computable fixture and a test that pins the number.
- Record design choices in `decisions/DEC-JK-NNN-*.md`.

## Run

    python -m pip install -e . pytest
    python -m pytest -q
