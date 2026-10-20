import json
from pathlib import Path

import pytest

from judge_kappa.cli import main
from judge_kappa.core import (bootstrap_kappa, cohen_kappa, parse_swap_map, position_flip_rate, read_labels,
                              run_stability)

EX = Path(__file__).resolve().parents[1] / "examples"


def test_textbook_kappa_is_point_four():
    # 50 items: both yes 20, yes/no 5, no/yes 10, both no 15 -> po 0.70, pe 0.50, kappa 0.40
    result = cohen_kappa(read_labels(EX / "textbook/gold.csv"), read_labels(EX / "textbook/judge.csv"))
    assert result.n == 50
    assert result.observed == pytest.approx(0.70)
    assert result.expected == pytest.approx(0.50)
    assert result.kappa == pytest.approx(0.40)


def test_evidence_first_fixture_matches_its_readme(capsys):
    # gold 4 ready / 4 blocked; claim_first agrees on 6 of 8 with 6 ready -> po 0.75, pe 0.50, kappa 0.50
    ef = EX / "evidence_first"
    gold = read_labels(ef / "gold.csv")
    claim = cohen_kappa(gold, read_labels(ef / "claim_first.csv"))
    assert claim.n == 8
    assert claim.observed == pytest.approx(0.75)
    assert claim.expected == pytest.approx(0.50)
    assert claim.kappa == pytest.approx(0.50)
    assert cohen_kappa(gold, read_labels(ef / "evidence_first.csv")).kappa == pytest.approx(1.0)
    assert main([str(ef / "gold.csv"), str(ef / "claim_first.csv")]) == 1
    assert main([str(ef / "gold.csv"), str(ef / "evidence_first.csv")]) == 0
    capsys.readouterr()
    readme = (ef / "README.md").read_text(encoding="utf-8")
    for stated in ("= 0.50`", "kappa 1.00", "exits are 1 and 0"):
        assert stated in readme


def test_evidence_first_fixture_intervals_match_its_readme(capsys):
    # n=8: the failing condition's interval covers [0, 1]; the perfect control's is zero width by construction
    ef = EX / "evidence_first"
    gold = read_labels(ef / "gold.csv")
    claim = bootstrap_kappa(gold, read_labels(ef / "claim_first.csv"))
    assert (claim.low, claim.high, claim.undefined) == (pytest.approx(0.0), pytest.approx(1.0), 6)
    perfect = bootstrap_kappa(gold, read_labels(ef / "evidence_first.csv"))
    assert (perfect.low, perfect.high, perfect.undefined) == (pytest.approx(1.0), pytest.approx(1.0), 12)
    for args, kappa, code in ((["claim_first.csv"], 0.5, 1), (["evidence_first.csv"], 1.0, 0)):
        assert main([str(ef / "gold.csv"), str(ef / args[0]), "--json"]) == code
        check = json.loads(capsys.readouterr().out)["checks"][0]
        assert check["value"] == pytest.approx(kappa) and check["n"] == 8
    readme = (ef / "README.md").read_text(encoding="utf-8")
    for stated in ("constructed", "[0.00, 1.00]", "[1.00, 1.00]", "6 undefined", "12 undefined",
                   "What a general claim would need"):
        assert stated in readme


def test_perfect_and_chance_agreement():
    ref = {"1": "a", "2": "b", "3": "a", "4": "b"}
    assert cohen_kappa(ref, dict(ref)).kappa == pytest.approx(1.0)
    assert cohen_kappa(ref, {"1": "a", "2": "a", "3": "b", "4": "b"}).kappa == pytest.approx(0.0)


def test_missing_item_counts_as_disagreement():
    result = cohen_kappa({"1": "a", "2": "b"}, {"1": "a"})
    assert result.missing == 1
    assert result.observed == pytest.approx(0.5)


def test_single_label_kappa_is_undefined_not_one():
    # one label throughout: po = pe = 1, so kappa = 0/0 (DEC-JK-003 amends DEC-JK-001)
    result = cohen_kappa({"1": "a", "2": "a"}, {"1": "a", "2": "a"})
    assert result.kappa is None and not result.defined
    assert result.observed == 1.0 and result.expected == 1.0
    assert "undefined" in result.note


def test_rubber_stamp_on_one_label_gold_is_not_fit(capsys):
    # 20 all-pass gold items, a judge that always says pass: exit 3, never 0
    ol = EX / "one_label"
    assert main([str(ol / "gold.csv"), str(ol / "judge.csv")]) == 3
    out = capsys.readouterr().out
    assert "[UNDEFINED] kappa_vs_gold" in out
    assert "verdict: fit to grade" not in out
    assert "insufficient label variation" in out
    assert main([str(ol / "gold.csv"), str(ol / "judge.csv"), "--json"]) == 3
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "undefined" and report["pass"] is False
    assert report["checks"][0]["value"] is None and report["checks"][0]["status"] == "undefined"


def test_a_failed_check_outranks_an_undefined_one(tmp_path, capsys):
    ol = EX / "one_label"
    swapped = tmp_path / "swapped.csv"
    swapped.write_text("item_id,label\n" + "".join(f"{i},{'fail' if i <= 5 else 'pass'}\n" for i in range(1, 21)),
                       encoding="utf-8")
    assert main([str(ol / "gold.csv"), str(ol / "judge.csv"), "--swapped", str(swapped)]) == 1
    out = capsys.readouterr().out
    assert "[UNDEFINED] kappa_vs_gold" in out and "[FAIL] position_flip_rate" in out
    assert "verdict: not fit to grade" in out


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


def test_stability_move_rate_and_floor_by_hand():
    # A-rates: 3/4, 2/4, 3/4 -> floor 0.25; items 2 and 3 changed label in some run
    runs = [{"1": "A", "2": "A", "3": "A", "4": "B"},
            {"1": "A", "2": "B", "3": "A", "4": "B"},
            {"1": "A", "2": "A", "3": "tie", "4": "A"}]
    stab = run_stability(runs, "A")
    assert stab.moved_items == ["2", "3", "4"] and stab.move_rate == pytest.approx(0.75)
    assert stab.rates == pytest.approx([0.75, 0.5, 0.75]) and stab.floor == pytest.approx(0.25)
    assert run_stability(runs).floor is None


def test_floor_is_largest_gap_between_any_two_runs():
    runs = [{"1": "A", "2": "A"}, {"1": "A", "2": "B"}, {"1": "B", "2": "B"}]
    assert run_stability(runs, "A").floor == pytest.approx(1.0)


def test_gate_margin_against_five_runs(capsys):
    pw = EX / "pairwise"
    cmd = [str(pw / "gold.csv"), str(pw / "run1.csv")]
    for n in (2, 3, 4, 5):
        cmd += ["--retest", str(pw / f"run{n}.csv")]
    cmd += ["--positive", "A"]
    assert main(cmd + ["--gate-margin", "0.02"]) == 1
    assert "[FAIL] detection_floor" in capsys.readouterr().out
    assert main(cmd + ["--gate-margin", "0.5"]) == 0
    capsys.readouterr()
    assert main(cmd + ["--gate-margin", "0.1"]) == 1  # margin equal to the floor cannot be told from noise
    capsys.readouterr()


def test_gate_margin_without_positive_is_bad_input(capsys):
    pw = EX / "pairwise"
    assert main([str(pw / "gold.csv"), str(pw / "run1.csv"), "--retest", str(pw / "run2.csv"), "--gate-margin", "0.1"]) == 2
    capsys.readouterr()


def test_single_retest_output_is_unchanged(capsys):
    pw = EX / "pairwise"
    main([str(pw / "gold.csv"), str(pw / "run1.csv"), "--retest", str(pw / "run2.csv")])
    out = capsys.readouterr().out
    assert "verdict_move_rate" not in out and "detection_floor" not in out


def test_bootstrap_of_perfect_agreement_is_exactly_one():
    # every resample with both labels has kappa 1; one-label resamples are undefined and left out
    ref = {"1": "a", "2": "b", "3": "a", "4": "b", "5": "a", "6": "b"}
    ci = bootstrap_kappa(ref, dict(ref), resamples=500, seed=0)
    assert (ci.low, ci.high, ci.level, ci.resamples, ci.seed) == (1.0, 1.0, 0.95, 500, 0)
    assert 0 <= ci.undefined < 500


def test_bootstrap_is_seeded_and_pinned():
    # 2000 resamples, seed 0: same inputs and seed give the same interval
    tb = read_labels(EX / "textbook/gold.csv"), read_labels(EX / "textbook/judge.csv")
    ci = bootstrap_kappa(*tb)
    assert ci == bootstrap_kappa(*tb, resamples=2000, seed=0)
    assert (ci.low, ci.high) == (pytest.approx(0.1235, abs=1e-4), pytest.approx(0.6388, abs=1e-4))
    assert ci.high > 0.6  # the failing textbook judge's interval reaches past the 0.6 gate
    pw = bootstrap_kappa(read_labels(EX / "pairwise/gold.csv"), read_labels(EX / "pairwise/run1.csv"))
    assert (pw.low, pw.high) == (pytest.approx(0.5745, abs=1e-4), 1.0)
    assert bootstrap_kappa(*tb, seed=1) != ci


def test_bootstrap_has_no_interval_for_an_undefined_kappa_or_zero_resamples():
    one = read_labels(EX / "one_label/gold.csv")
    assert bootstrap_kappa(one, dict(one)) is None
    assert bootstrap_kappa(read_labels(EX / "textbook/gold.csv"), read_labels(EX / "textbook/judge.csv"), resamples=0) is None


def test_report_states_interval_and_n_without_changing_the_gate(capsys):
    pw = EX / "pairwise"
    cmd = [str(pw / "gold.csv"), str(pw / "run1.csv"), "--retest", str(pw / "run2.csv")]
    assert main(cmd) == 0  # the point estimate still decides: 0.833 >= 0.6 although the interval reaches 0.574
    out = capsys.readouterr().out
    assert "95% CI [0.574, 1.000]  (n=20, percentile bootstrap, 2000 resamples, seed 0; the interval spans the threshold)" in out
    assert "95% CI [0.688, 1.000]  (n=20," in out
    assert main(cmd + ["--json"]) == 0
    ci = json.loads(capsys.readouterr().out)["checks"][0]["ci"]
    assert ci["level"] == 0.95 and ci["resamples"] == 2000 and ci["seed"] == 0 and ci["high"] == 1.0
    assert main([str(EX / "textbook/gold.csv"), str(EX / "textbook/judge.csv")]) == 1
    capsys.readouterr()
    assert main(cmd + ["--resamples", "0"]) == 0
    assert "CI [" not in capsys.readouterr().out
    assert main(cmd + ["--resamples", "-1"]) == 2
    capsys.readouterr()
