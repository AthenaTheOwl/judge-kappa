from pathlib import Path

import pytest

from judge_kappa.cli import main
from judge_kappa.core import cohen_kappa, parse_swap_map, position_flip_rate, read_labels

EX = Path(__file__).resolve().parents[1] / "examples"


def test_textbook_kappa_is_point_four():
    # 50 items: both yes 20, yes/no 5, no/yes 10, both no 15 -> po 0.70, pe 0.50, kappa 0.40
    result = cohen_kappa(read_labels(EX / "textbook/gold.csv"), read_labels(EX / "textbook/judge.csv"))
    assert result.n == 50
    assert result.observed == pytest.approx(0.70)
    assert result.expected == pytest.approx(0.50)
    assert result.kappa == pytest.approx(0.40)


def test_perfect_and_chance_agreement():
    ref = {"1": "a", "2": "b", "3": "a", "4": "b"}
    assert cohen_kappa(ref, dict(ref)).kappa == pytest.approx(1.0)
    assert cohen_kappa(ref, {"1": "a", "2": "a", "3": "b", "4": "b"}).kappa == pytest.approx(0.0)


def test_missing_item_counts_as_disagreement():
    result = cohen_kappa({"1": "a", "2": "b"}, {"1": "a"})
    assert result.missing == 1
    assert result.observed == pytest.approx(0.5)


def test_single_label_kappa_is_reported_with_a_note():
    result = cohen_kappa({"1": "a", "2": "a"}, {"1": "a", "2": "a"})
    assert result.kappa == 1.0 and result.note


def test_flip_rate_translates_swapped_labels():
    first = {"1": "A", "2": "B", "3": "tie"}
    swapped = {"1": "B", "2": "B", "3": "tie"}  # item 2 kept the same position -> a flip
    flip = position_flip_rate(first, swapped, parse_swap_map("A=B,B=A"))
    assert (flip.flips, flip.flipped_items) == (1, ["2"])


def test_cli_exit_codes(tmp_path, capsys):
    assert main([str(EX / "textbook/gold.csv"), str(EX / "textbook/judge.csv")]) == 1
    pairwise = [str(EX / "pairwise/gold.csv"), str(EX / "pairwise/run1.csv"),
                "--retest", str(EX / "pairwise/run2.csv"), "--swapped", str(EX / "pairwise/swapped.csv")]
    assert main(pairwise) == 0
    assert main(pairwise + ["--max-flip", "0.01"]) == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("id,verdict\n1,a\n", encoding="utf-8")
    assert main([str(bad), str(bad)]) == 2
    capsys.readouterr()


def test_bad_swap_map():
    with pytest.raises(ValueError):
        parse_swap_map("A-B")
