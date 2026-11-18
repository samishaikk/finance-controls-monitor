from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register


@register
class DuplicateClaims(Control):
    control_id = "C1"
    name = "Duplicate claims"
    description = "The same expense submitted twice (same receipt, or same employee, vendor and amount)."
    sql_file = "c1_duplicate_claims.sql"

    def row_to_finding(self, row):
        if row["match_type"] == "same_receipt":
            why = "shares a receipt number with"
        else:
            why = "has the same employee, vendor and amount as"
        return Finding(
            reason=f"claim {row['expense_id']} {why} earlier claim {row['original_expense_id']}",
            expense_id=row["expense_id"],
            employee_id=row["employee_id"],
            evidence=row,
        )