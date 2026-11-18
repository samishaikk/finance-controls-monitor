from controls_monitor.controls import (  # noqa: F401  (importing registers each control)
    c1_duplicate_claims,
    c2_split_claims,
    c3_approver,
)
from controls_monitor.controls.registry import REGISTRY, build_controls  # noqa: F401