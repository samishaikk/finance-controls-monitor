from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register

REASONS = {
    "no_approver": "claim {expense_id} was approved but no approver is recorded",
    "self_approval": "employee {employee_id} approved their own claim {expense_id}",
    "not_manager": (
        "claim {expense_id} was approved by employee {approver_id}, "
        "who is not the employee's manager"
    ),
}


@register
class ApproverNotManager(Control):
    control_id = "C3"
    name = "Approver is not the employee's manager"
    description = "Segregation of duties: only the employee's manager (or skip-level) may approve."
    sql_file = "c3_approver_not_manager.sql"

    def row_to_finding(self, row):
        return Finding(
            reason=REASONS[row["violation_type"]].format(**row),
            expense_id=row["expense_id"],
            employee_id=row["employee_id"],
            evidence=row,
        )