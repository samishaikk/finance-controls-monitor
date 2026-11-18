from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register

@register
class FastApprovals(Control):
    control_id = "C4"
    name = "Approval too fast to be a real review"
    description = "Claims approved sooner after submission than a person could review them."
    sql_file = "c4_fast_approvals.sql"

    def row_to_finding(self, row):
        seconds = row["latency_seconds"]
        if seconds < 0:
            reason = f"claim {row['expense_id']} has an approval time before its submission time"
        else:
            reason = (
                f"claim {row['expense_id']} was approved {seconds} seconds after submission "
                f"(minimum {self.settings.min_review_seconds})"
            )
        return Finding(
            reason=reason,
            expense_id=row["expense_id"],
            employee_id=row["employee_id"],
            evidence=row,
        )