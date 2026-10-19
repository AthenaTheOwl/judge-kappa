# A hand-computable reviewer experiment

These eight synthetic labels illustrate how to compare two reviewer input
conditions. They are not observations from live agents. The human reference is
balanced: four ready, four blocked. `claim_first.csv` agrees on six of eight;
expected chance agreement is one half, so kappa is `(0.75 - 0.5) / 0.5 = 0.50`.
`evidence_first.csv` is a deliberately perfect control and has kappa 1.00.

```bash
python -m judge_kappa examples/evidence_first/gold.csv examples/evidence_first/claim_first.csv
python -m judge_kappa examples/evidence_first/gold.csv examples/evidence_first/evidence_first.csv
```

With the default 0.60 threshold, expected exits are 1 and 0 respectively. The
fixture demonstrates the calculation; it cannot establish that withholding an
author's conclusion improves a real judge.

To measure that question, label a held-out set from the underlying diffs and
receipts before producing the review conditions. Hold model, rubric and budgets
fixed. Give one reviewer the author claim with the evidence, and give the other
the evidence first. Repeat both conditions and compare false-ready and false-block
items as well as kappa. Keep author claims out of the human gold-labeling input.

[Audit Without Verification](https://arxiv.org/abs/2609.07680) motivates testing
whether reviewers relay upstream conclusions. The separate `--retest` and
`--swapped` checks remain necessary: high agreement with one small gold set does
not establish repeatability or order invariance. Estimate whether the experiment
has adequate precision before adopting a small observed improvement.
