# judge-kappa

An LLM judge agreed with the human labels 70 percent of the time. That sounds like a grader. Corrected for the agreement two coin-flippers would reach on the same label mix, it is a kappa of 0.40, and this tool says no.

## What it does

Before a model grades anything, three questions decide whether its grades mean something:

- **Does it agree with people, beyond chance?** Cohen's kappa against a gold set of human labels.
- **Does it agree with itself?** Test-retest kappa between two runs of the same judge on the same items.
- **Does it care which answer came first?** The share of pairwise verdicts that change when the two answers swap positions.

Each check has a threshold. Every check passes, exit 0. Any check fails, exit 1. Bad input, exit 2. One line in CI decides whether the judge is allowed to grade.

Standard library only. No model calls: you run the judge however you run it, save its verdicts as CSV, and point this at the files.

## Try it

```bash
python -m pip install -e .
judge-kappa examples/textbook/gold.csv examples/textbook/judge.csv
```

```text
judge-kappa report
  [FAIL] kappa_vs_gold        0.400  (needs >= 0.6)  n=50  raw agreement=0.700
verdict: not fit to grade
```

The textbook fixture is the standard worked example: 50 items, 20 both-yes, 5 yes/no, 10 no/yes, 15 both-no. Raw agreement 0.70, chance agreement 0.50, kappa 0.40.

A pairwise judge with a retest run and a swapped-order run:

```bash
judge-kappa examples/pairwise/gold.csv examples/pairwise/run1.csv \
  --retest examples/pairwise/run2.csv --swapped examples/pairwise/swapped.csv
```

```text
judge-kappa report
  [PASS] kappa_vs_gold        0.833  (needs >= 0.6)  n=20  raw agreement=0.900
  [PASS] test_retest_kappa    0.913  (needs >= 0.8)  n=20  raw agreement=0.950
  [PASS] position_flip_rate   0.050  (needs <= 0.1)  n=20  flips=1
verdict: fit to grade
```

## Inputs

Every file is a CSV with `item_id,label`. The swapped run records verdicts in its own terms (for A/B pairs, "A" means the answer shown first in that run); `--swap-map` translates them back and defaults to `A=B,B=A`. An item the judge skipped counts as a disagreement. Thresholds: `--min-kappa` (0.6), `--min-retest` (0.8), `--max-flip` (0.1). `--json` prints the full report, including which items flipped.

## What it does not do

It does not run the judge, and it does not tell you why a judge disagrees. Kappa also flatters nothing: on a gold set where one label dominates, a judge can agree 95 percent of the time and still score near zero, which is the point.

## License

MIT.
