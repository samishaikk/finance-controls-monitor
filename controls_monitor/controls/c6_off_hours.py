from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import register

DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
             5: "Friday", 6: "Saturday", 7: "Sunday"}

@register
class OffHoursApprovals(Control):
    control_id = "C6"
    name = "Off-hours or weekend approval"
    description = "Approvals made outside business hours or at weekends (UTC)."
    sql_file = "c6_off_hours_approvals.sql"

    def row_to_finding(self, row):
        day = DAY_NAMES[row["iso_weekday"]]
        if row["reason_type"] == "weekend":
            reason = f"claim {row['expense_id']} was approved on a {day}"
        else:
            reason = (
                f"claim {row['expense_id']} was approved at {row['hour_utc']:02d}:xx UTC "
                f"on a {day}, outside {self.settings.business_start_hour:02d}:00-"
                f"{self.settings.business_end_hour:02d}:00"
            )
        return Finding(
            reason=reason,
            expense_id=row["expense_id"],
            employee_id=row["employee_id"],
            evidence=row,
        )