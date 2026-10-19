"""Agreement statistics for an LLM judge. Standard library only."""

from __future__ import annotations

import csv
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

MISSING = "<missing>"
UNDEFINED_NOTE = "kappa undefined: both label sets use one label throughout, so chance agreement is 1 and kappa is 0/0"


def read_labels(path: str | Path) -> dict[str, str]:
    """Read a CSV with `item_id,label` columns into {item_id: label}."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"item_id", "label"} <= set(reader.fieldnames):
            raise ValueError(f"{path}: needs item_id and label columns")
        labels: dict[str, str] = {}
        for row in reader:
            item = row["item_id"].strip()
            if item in labels:
                raise ValueError(f"{path}: duplicate item_id {item!r}")
            labels[item] = row["label"].strip()
    if not labels:
        raise ValueError(f"{path}: no rows")
    return labels


@dataclass
class Agreement:
    n: int
    observed: float
    expected: float
    kappa: float | None  # None when kappa is undefined (chance agreement is 1)
    missing: int = 0
    note: str = ""

    @property
    def defined(self) -> bool:
        return self.kappa is not None


def cohen_kappa(reference: dict[str, str], other: dict[str, str]) -> Agreement:
    """Cohen's kappa of `other` against `reference`, over the reference's items.

    An item `other` did not label counts as a disagreement (label <missing>).
    When chance agreement is 1 (both raters used one identical label throughout),
    kappa is 0/0: undefined. It is returned as None with a note, never as a
    number, so it cannot pass a threshold (DEC-JK-003).
    """
    items = sorted(reference)
    pairs = [(reference[i], other.get(i, MISSING)) for i in items]
    n = len(pairs)
    missing = sum(1 for _, b in pairs if b == MISSING)
    observed = sum(1 for a, b in pairs if a == b) / n
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in left) / (n * n)
    if expected == 1.0:
        return Agreement(n, observed, expected, None, missing, UNDEFINED_NOTE)
    return Agreement(n, observed, expected, (observed - expected) / (1 - expected), missing)



def _kappa_of_pairs(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in left) / (n * n)
    return None if expected == 1.0 else (observed - expected) / (1 - expected)


def _quantile(ordered: list[float], q: float) -> float:
    """Linear interpolation between order statistics (statistics.quantiles 'inclusive')."""
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


@dataclass
class Interval:
    low: float
    high: float
    level: float
    resamples: int
    seed: int
    undefined: int = 0  # resamples whose kappa was undefined, left out of the percentiles


def bootstrap_kappa(reference: dict[str, str], other: dict[str, str], resamples: int = 2000,
                    seed: int = 0, level: float = 0.95) -> Interval | None:
    """Percentile bootstrap interval for cohen_kappa(reference, other).

    Draws `resamples` samples of the reference's n items with replacement from
    random.Random(seed), recomputes kappa on each, and returns the central
    `level` share of those kappas. The same inputs and seed give the same
    interval. A resample whose kappa is undefined (one label throughout) is
    left out and counted. Returns None when the point kappa is undefined,
    `resamples` is 0, or every resample is undefined.
    """
    items = sorted(reference)
    pairs = [(reference[i], other.get(i, MISSING)) for i in items]
    if resamples <= 0 or _kappa_of_pairs(pairs) is None:
        return None
    rng = random.Random(seed)
    n = len(pairs)
    values: list[float] = []
    for _ in range(resamples):
        k = _kappa_of_pairs([pairs[j] for j in rng.choices(range(n), k=n)])
        if k is not None:
            values.append(k)
    if not values:
        return None
    values.sort()
    tail = (1 - level) / 2
    return Interval(_quantile(values, tail), _quantile(values, 1 - tail), level, resamples, seed,
                    resamples - len(values))

def parse_swap_map(spec: str) -> dict[str, str]:
    """'A=B,B=A' -> {'A': 'B', 'B': 'A'}. Labels not in the map are unchanged."""
    mapping: dict[str, str] = {}
    for pair in filter(None, (p.strip() for p in spec.split(","))):
        left, sep, right = pair.partition("=")
        if not sep:
            raise ValueError(f"bad swap map entry {pair!r}; expected X=Y")
        mapping[left.strip()] = right.strip()
    return mapping


@dataclass
class FlipRate:
    n: int
    flips: int
    rate: float
    flipped_items: list[str] = field(default_factory=list)


def position_flip_rate(first: dict[str, str], swapped: dict[str, str], swap_map: dict[str, str]) -> FlipRate:
    """Share of items whose verdict changes when the answers are shown in the other order.

    `swapped` holds verdicts from the run with answer positions exchanged, in that
    run's own terms; `swap_map` translates them back (for pairwise A/B, 'A=B,B=A').
    Items missing from either run are skipped.
    """
    items = sorted(set(first) & set(swapped))
    if not items:
        raise ValueError("no items in common between the first run and the swapped run")
    flipped = [i for i in items if swap_map.get(swapped[i], swapped[i]) != first[i]]
    return FlipRate(len(items), len(flipped), len(flipped) / len(items), flipped)


@dataclass
class Stability:
    runs: int
    n: int
    moved: int
    moved_items: list[str] = field(default_factory=list)
    rates: list[float] = field(default_factory=list)
    floor: float | None = None

    @property
    def move_rate(self) -> float:
        return self.moved / self.n


def run_stability(runs: list[dict[str, str]], positive: str | None = None) -> Stability:
    """Compare repeated runs of one judge on the same items (the first run's items).

    An item moved if its label differs in any run; a run that skipped it counts
    as a different label. With `positive`, the detection floor is the largest
    gap in that label's rate between any two runs: an observed lower bound on
    how far the judge's own noise moves its score.
    """
    items = sorted(runs[0])
    moved_items = [i for i in items if len({r.get(i, MISSING) for r in runs}) > 1]
    stab = Stability(len(runs), len(items), len(moved_items), moved_items)
    if positive is not None:
        stab.rates = [sum(1 for i in items if r.get(i, MISSING) == positive) / len(items) for r in runs]
        stab.floor = max(stab.rates) - min(stab.rates)
    return stab
