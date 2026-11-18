from controls_monitor.controls import (  # noqa: F401  
    c1_duplicate_claims,
    c2_split_claims,
    c3_approver,
    c4_fast_approvals,
    c5_outlier_manager,
    c6_off_hours,
)
from controls_monitor.controls.registry import REGISTRY, build_controls  