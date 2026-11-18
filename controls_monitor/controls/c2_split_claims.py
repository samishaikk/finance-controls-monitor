from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register


@register
class SplitClaims(Control):
    control_id = "C2"
    name = "Split claims under the approval limit"
    description = "Several small claims in a short window that together reach the approval limit."
    sql_file = "c2_split_claims.sql"

    def row_to_finding(self, row):
        return Finding(
            reason=(
                f"claim {row['expense_id']} is one of {row['claim_count']} claims "
                f"totalling {row['total']} inside {self.settings.window_hours} hours "
                f"(limit {self.settings.approval_limit:g})"
            ),
            expense_id=row["expense_id"],
            employee_id=row["employee_id"],
            evidence=row,
        )