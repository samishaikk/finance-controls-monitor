import pytest

from controls_monitor.cli import main
from controls_monitor.config import load_config
from controls_monitor.evaluation import (
    ControlScore,
    EvaluationError,
    evaluate_run,
    format_markdown,
    format_table,
    totals,
)
from controls_monitor.generator import seed_clean_org
from controls_monitor.injector import inject_violations
from controls_monitor.runner import run_all


EXPECTED = {
    "C1": (11, 8, 3, 6, 2, 0),
    "C2": (14, 10, 4, 7, 2, 0),
    "C3": (8, 8, 0, 7, 2, 0),
    "C4": (7, 5, 2, 5, 2, 0),
    "C5": (2, 1, 1, 2, 1, 0),
    "C6": (6, 6, 0, 4, 2, 0),
}


def planted_run(db, seed=42):
    seed_clean_org(db, seed)
    inject_violations(db, seed)
    return run_all(db, load_config()).run_id


#  the arithmetic 


def score(**kwargs):
    base = dict(control_id="C1", name="x", violations=0, caught=0, missed=0,
                decoys=0, decoys_flagged=0, unplanned=0)
    base.update(kwargs)
    return ControlScore(**base)


def test_precision_and_recall_arithmetic():
    s = score(violations=10, caught=8, missed=2, decoys=5, decoys_flagged=1, unplanned=1)
    assert s.false_positives == 2
    assert s.precision == pytest.approx(0.8)
    assert s.recall == pytest.approx(0.8)


def test_precision_and_recall_are_none_when_there_is_nothing_to_divide():
    s = score()
    assert s.precision is None
    assert s.recall is None


def test_no_flags_means_no_precision_but_zero_recall():
    s = score(violations=4, missed=4)
    assert s.precision is None
    assert s.recall == 0


def test_totals_add_up_across_controls():
    t = totals([score(violations=4, caught=3, missed=1, decoys_flagged=1), score(violations=6, caught=6)])
    assert t["violations"] == 10
    assert t["caught"] == 9
    assert t["recall"] == pytest.approx(0.9)
    assert t["precision"] == pytest.approx(9 / 10)


#  the real thing 


@pytest.mark.parametrize("seed", [42, 7])
def test_scores_match_the_designed_case_set(db, seed):
    scores = evaluate_run(db, planted_run(db, seed))
    got = {
        s.control_id: (s.violations, s.caught, s.missed, s.decoys, s.decoys_flagged, s.unplanned)
        for s in scores
    }
    assert got == EXPECTED


def test_nothing_is_flagged_that_was_not_planted(db):
    scores = evaluate_run(db, planted_run(db))
    assert sum(s.unplanned for s in scores) == 0


def test_rule_based_controls_catch_everything_and_threshold_ones_do_not(db):
    by_id = {s.control_id: s for s in evaluate_run(db, planted_run(db))}
    assert by_id["C3"].recall == 1.0
    assert by_id["C6"].recall == 1.0
    for control_id in ("C1", "C2", "C4", "C5"):
        assert by_id[control_id].recall < 1.0


def test_known_misses_and_false_positives_are_listed_with_reasons(db):
    by_id = {s.control_id: s for s in evaluate_run(db, planted_run(db))}
    assert any("1 cent" in note for note in by_id["C1"].missed_notes)
    assert any("30 hours apart" in note for note in by_id["C2"].missed_notes)
    assert any("India time" in note for note in by_id["C6"].false_positive_notes)
    assert any("delegate" in note for note in by_id["C3"].false_positive_notes)


def test_the_table_and_markdown_show_the_numbers(db):
    run_id = planted_run(db)
    scores = evaluate_run(db, run_id)

    table = format_table(scores)
    assert "C1      11       8       3" in table
    assert "72.7%" in table
    assert table.splitlines()[-1].startswith("all")

    markdown = format_markdown(scores, run_id)
    assert f"# Detection evaluation - run {run_id}" in markdown
    assert "| C1 | Duplicate claims | 11 | 8 | 3 | 6 | 2 | 0 | 80.0% | 72.7% |" in markdown
    assert "## Known misses" in markdown
    assert "## Known false positives" in markdown
    assert "not real-world accuracy" in markdown


def test_evaluating_without_planted_cases_is_an_error(db):
    seed_clean_org(db)
    run_id = run_all(db, load_config()).run_id
    with pytest.raises(EvaluationError, match="--with-violations"):
        evaluate_run(db, run_id)


def test_evaluating_an_unknown_run_is_an_error(db):
    with pytest.raises(EvaluationError, match="run 999 not found"):
        evaluate_run(db, 999)



def test_evaluate_command_prints_the_table(db, engine, capsys):
    seed_clean_org(db)
    inject_violations(db)
    assert main(["evaluate"], engine=engine) == 0
    out = capsys.readouterr().out
    assert "evaluation of run" in out
    assert "precision" in out
    assert "C5      2        1       1" in out


def test_evaluate_command_can_write_markdown(db, engine, tmp_path, capsys):
    seed_clean_org(db)
    inject_violations(db)
    target = tmp_path / "eval.md"
    assert main(["evaluate", "--output", str(target)], engine=engine) == 0
    assert "## Known misses" in target.read_text(encoding="utf-8")


def test_evaluate_command_without_cases_exits_two(db, engine, capsys):
    seed_clean_org(db)
    assert main(["evaluate"], engine=engine) == 2
    assert "--with-violations" in capsys.readouterr().err