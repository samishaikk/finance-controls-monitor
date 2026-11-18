from dataclasses import dataclass, field

from sqlalchemy import select

from controls_monitor.models import (
    ControlException,
    ControlResult,
    ControlRun,
    InjectedViolation,
)


class EvaluationError(Exception):
    pass


@dataclass
class ControlScore:
    control_id: str
    name: str
    violations: int
    caught: int
    missed: int
    decoys: int
    decoys_flagged: int
    unplanned: int
    missed_notes: list = field(default_factory=list)
    false_positive_notes: list = field(default_factory=list)

    @property
    def false_positives(self):
        return self.decoys_flagged + self.unplanned

    @property
    def precision(self):
        flagged = self.caught + self.false_positives
        return self.caught / flagged if flagged else None

    @property
    def recall(self):
        return self.caught / self.violations if self.violations else None


def case_key(control_id, expense_id, employee_id):
    """C5 judges approvers (employees); every other control judges claims."""
    return employee_id if control_id == "C5" else expense_id


def evaluate_run(session, run_id):
    run = session.get(ControlRun, run_id)
    if run is None:
        raise EvaluationError(f"run {run_id} not found")
    cases = session.scalars(select(InjectedViolation).order_by(InjectedViolation.id)).all()
    if not cases:
        raise EvaluationError(
            "no planted cases in this database - run: "
            "python -m controls_monitor.generator --reset --with-violations"
        )

    results = session.scalars(
        select(ControlResult).where(ControlResult.run_id == run_id).order_by(ControlResult.id)
    ).all()
    flagged = {}
    for e in session.scalars(select(ControlException).where(ControlException.run_id == run_id)):
        flagged.setdefault(e.control_id, set()).add(case_key(e.control_id, e.expense_id, e.employee_id))

    scores = []
    for r in results:
        mine = [c for c in cases if c.control_id == r.control_id]
        violations = {case_key(c.control_id, c.expense_id, c.employee_id): c for c in mine if not c.is_decoy}
        decoys = {case_key(c.control_id, c.expense_id, c.employee_id): c for c in mine if c.is_decoy}
        hit = flagged.get(r.control_id, set())
        scores.append(
            ControlScore(
                control_id=r.control_id,
                name=r.control_name,
                violations=len(violations),
                caught=len(violations.keys() & hit),
                missed=len(violations.keys() - hit),
                decoys=len(decoys),
                decoys_flagged=len(decoys.keys() & hit),
                unplanned=len(hit - violations.keys() - decoys.keys()),
                missed_notes=[violations[k].note for k in sorted(violations.keys() - hit)],
                false_positive_notes=[decoys[k].note for k in sorted(decoys.keys() & hit)],
            )
        )
    return scores


def _pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def totals(scores):
    caught = sum(s.caught for s in scores)
    violations = sum(s.violations for s in scores)
    false_positives = sum(s.false_positives for s in scores)
    flagged = caught + false_positives
    return {
        "violations": violations,
        "caught": caught,
        "missed": sum(s.missed for s in scores),
        "decoys": sum(s.decoys for s in scores),
        "decoys_flagged": sum(s.decoys_flagged for s in scores),
        "unplanned": sum(s.unplanned for s in scores),
        "precision": caught / flagged if flagged else None,
        "recall": caught / violations if violations else None,
    }


def format_table(scores):
    header = (
        f"{'control':<8}{'planted':<9}{'caught':<8}{'missed':<8}"
        f"{'decoys':<8}{'flagged':<9}{'unplanned':<11}{'precision':<11}recall"
    )
    lines = [header]
    for s in scores:
        lines.append(
            f"{s.control_id:<8}{s.violations:<9}{s.caught:<8}{s.missed:<8}"
            f"{s.decoys:<8}{s.decoys_flagged:<9}{s.unplanned:<11}{_pct(s.precision):<11}{_pct(s.recall)}"
        )
    t = totals(scores)
    lines.append(
        f"{'all':<8}{t['violations']:<9}{t['caught']:<8}{t['missed']:<8}"
        f"{t['decoys']:<8}{t['decoys_flagged']:<9}{t['unplanned']:<11}{_pct(t['precision']):<11}{_pct(t['recall'])}"
    )
    return "\n".join(lines)


def format_markdown(scores, run_id):
    t = totals(scores)
    lines = [
        f"# Detection evaluation - run {run_id}",
        "",
        "All data is synthetic. The case set was built with deliberate misses and "
        "look-alike decoys, so these numbers describe this test set, not real-world accuracy.",
        "",
        "| Control | Name | Planted | Caught | Missed | Decoys | Decoys flagged | Unplanned flags | Precision | Recall |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        lines.append(
            f"| {s.control_id} | {s.name} | {s.violations} | {s.caught} | {s.missed} | {s.decoys} | "
            f"{s.decoys_flagged} | {s.unplanned} | {_pct(s.precision)} | {_pct(s.recall)} |"
        )
    lines.append(
        f"| **all** | | {t['violations']} | {t['caught']} | {t['missed']} | {t['decoys']} | "
        f"{t['decoys_flagged']} | {t['unplanned']} | {_pct(t['precision'])} | {_pct(t['recall'])} |"
    )
    lines += [
        "",
        "- **Planted**: real violations put into the data. **Caught**: flagged by the control.",
        "- **Decoys**: legitimate look-alikes. **Decoys flagged**: false positives the rule cannot avoid.",
        "- **Unplanned flags**: flagged items that were not planted at all (should be 0).",
        "- Precision = caught / (caught + decoys flagged + unplanned). Recall = caught / planted.",
    ]
    misses = [(s.control_id, n) for s in scores for n in s.missed_notes]
    if misses:
        lines += ["", "## Known misses (real violations the rules do not catch)", ""]
        lines += [f"- {cid}: {note}" for cid, note in misses]
    false_positives = [(s.control_id, n) for s in scores for n in s.false_positive_notes]
    if false_positives:
        lines += ["", "## Known false positives (legitimate cases the rules flag)", ""]
        lines += [f"- {cid}: {note}" for cid, note in false_positives]
    return "\n".join(lines) + "\n"