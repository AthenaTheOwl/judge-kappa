# DEC-JK-004 — report a bootstrap interval beside each kappa

## Status

Accepted (2026-10-19).

## Context

The report printed each kappa as one number against a threshold written to two decimals, on gold sets of 50, 20 and 8 items. At those sizes the sampling error is wide. Resampling the committed fixtures shows the failing textbook judge (kappa 0.40, n=50) with a 95% interval of about [0.12, 0.64], which reaches past the 0.6 gate, and the passing pairwise judge (kappa 0.833, n=20) with about [0.57, 1.00], which reaches below it. A reader who sees only the point estimate cannot tell a clear pass from a lucky one.

## Decision

Each kappa check (`kappa_vs_gold`, `test_retest_kappa`) reports a 95% confidence interval and its n:

- Method: percentile bootstrap over items. Draw n items with replacement from the reference's items, recompute kappa, repeat; the interval is the 2.5th and 97.5th percentiles of those kappas (linear interpolation between order statistics, as in `statistics.quantiles(method="inclusive")`).
- Resamples: `--resamples` (default 2000). `--resamples 0` turns the interval off; a negative value is bad input (exit 2).
- Seed: `--seed` (default 0), fed to `random.Random`. The same files and seed give the same interval; the pinned values are the same on Python 3.11, 3.12 and 3.13.
- A resample whose kappa is undefined (one label throughout, DEC-JK-003) is left out of the percentiles and counted in `undefined_resamples`; the text report says how many were left out. No interval is reported when the point kappa is undefined.
- The text report adds a line `95% CI [low, high] (n=..., percentile bootstrap, R resamples, seed S)` under each kappa, and says when the interval spans the threshold. `--json` adds a `ci` object to the check.

The gate is unchanged: pass or fail is still decided by the point estimate against `--min-kappa` and `--min-retest`. The interval is information for the reader, not a second gate.

## Alternatives considered

- Analytic large-sample standard error (Cohen 1960 or Fleiss, Cohen and Everitt 1969): no randomness, but symmetric around the estimate and can exceed 1 at the sizes this tool sees (the pairwise fixture gives about [0.61, 1.05]).
- Gating on the lower bound: stricter and arguably right for small gold sets, but it changes which judges pass. That is a separate decision with its own record.
- Unseeded bootstrap: the report would change between runs of the same files.

## Evidence

`tests/test_judge_kappa.py` pins the textbook interval (0.1235, 0.6388) and the pairwise interval (0.5745, 1.0) at seed 0 with 2000 resamples, checks that perfect two-label agreement gives exactly [1, 1], that an undefined kappa gives no interval, and that exit codes do not change.

## Rollback

`--resamples 0` removes the interval from a run. Reverting this record and `bootstrap_kappa` removes it entirely; the gate does not depend on it.

## Limits

A percentile bootstrap undercovers on very small gold sets: on the eight-item `evidence_first` fixture the `claim_first` interval is [0.00, 1.00], which says the set is too small to decide, not that the judge is anywhere in that range with 95% confidence. The `evidence_first` condition matches gold exactly, so every resample gives kappa 1 and its interval is [1.00, 1.00]: zero width by construction, not a sign of precision. The interval covers sampling of items only; run-to-run noise is what `--retest` and the detection floor (DEC-JK-002) measure.
