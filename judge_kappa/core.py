"""Agreement statistics for an LLM judge. Standard library only."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

MISSING = "<missing>"


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
    kappa: float
    missing: int = 0
    note: str = ""


def cohen_kappa(reference: dict[str, str], other: dict[str, str]) -> Agreement:
    """Cohen's kappa of `other` against `reference`, over the reference's items.

    An item `other` did not label counts as a disagreement (label <missing>).
    When chance agreement is 1 (both raters used one identical label throughout),
    kappa is undefined; it is reported as 1.0 with a note.
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
        return Agreement(n, observed, expected, 1.0, missing, "kappa undefined (one label throughout); reported as 1.0")
    return Agreement(n, observed, expected, (observed - expected) / (1 - expected), missing)


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
