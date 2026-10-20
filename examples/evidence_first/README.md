# A hand-computable reviewer fixture

This is a constructed, illustrative fixture: eight hand-written labels, not
observations from live agents or a real review queue. It exists to show how to
compare two reviewer input conditions with judge-kappa, and to give a kappa that
can be checked by hand. It is not evidence that either condition is better.

The human reference is balanced: four ready, four blocked. `claim_first.csv`
agrees on six of eight; expected chance agreement is one half, so kappa is
`(0.75 - 0.5) / 0.5 = 0.50`. `evidence_first.csv` was written as a copy of the
gold labels, a deliberately perfect control, so its kappa 1.00 holds by
construction. The two conditions differ on two items out of eight.

```bash
python -m judge_kappa examples/evidence_first/gold.csv examples/evidence_first/claim_first.csv
python -m judge_kappa examples/evidence_first/gold.csv examples/evidence_first/evidence_first.csv
```

With the default 0.60 threshold, expected exits are 1 and 0 respectively. The
report also prints a bootstrap interval for each kappa
([DEC-JK-004](../../decisions/DEC-JK-004-bootstrap-interval-for-kappa.md)), and
at n=8 both intervals say the set is too small to decide anything:

| condition | kappa | 95% CI (seed 0, 2000 resamples) | exit |
| --- | --- | --- | --- |
| `claim_first.csv` | 0.50 | [0.00, 1.00], spans the 0.60 threshold; 6 undefined resamples left out | 1 |
| `evidence_first.csv` | 1.00 | [1.00, 1.00]; 12 undefined resamples left out | 0 |

The `claim_first` interval covers almost every value kappa can take on this
set. The `evidence_first` interval is zero width only because every resample of
perfect agreement is again perfect agreement; it reflects the construction, not
precision. The pass and the fail demonstrate the calculation and the exit
codes. They cannot establish that withholding an author's conclusion improves a
real judge, by how much, or for which models and tasks.

## What a general claim would need

To measure that question:

- Label a held-out set of real items from the underlying diffs and receipts
  before producing either review condition, and keep author claims out of the
  human gold-labeling input.
- Use enough items that each condition's kappa interval is narrow and clear of
  the threshold. Eight items are not close; on this fixture a one-item change
  moves kappa by about 0.25.
- Hold model, rubric and budgets fixed. Give one reviewer the author claim with
  the evidence, and give the other the evidence first. Run both conditions on
  the same items.
- Repeat each condition (`--retest`) and compare the difference between
  conditions with the run-to-run noise (DEC-JK-002). judge-kappa reports each
  condition's kappa separately, not an interval for the difference; a paired
  comparison of the items on which the two conditions disagree is still needed.
- Count false-ready and false-block items as well as kappa. judge-kappa reports
  kappa only, so count them by comparing each condition's CSV with gold; here
  both `claim_first.csv` misses (items 5 and 6) are false-ready.
- Repeat across more than one model, rubric and task before stating the result
  generally.

[Audit Without Verification](https://arxiv.org/abs/2609.07680) motivates testing
whether reviewers relay upstream conclusions. The separate `--retest` and
`--swapped` checks remain necessary: high agreement with one small gold set does
not establish repeatability or order invariance.
