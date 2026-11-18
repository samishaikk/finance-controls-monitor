from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register

@register
class OutlierManager(Control):
    control_id = "C5"
    name = "Approval-rate outlier manager"
    description = "An approver whose approval rate is far above the median of their peers."
    sql_file = "c5_outlier_manager.sql"

    def row_to_finding(self, row):
        return Finding(
            reason=(
                f"approver {row['employee_id']} approved {row['approval_rate']}% of "
                f"{row['decisions']} decisions; peer median is {row['peer_median']}%"
            ),
            employee_id=row["employee_id"],
            evidence=row,
        )