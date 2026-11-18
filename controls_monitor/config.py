import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "controls.yaml"


class ConfigError(Exception):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ControlSettings(Strict):
    name: str
    enabled: bool = True
    severity: Severity


class DuplicateClaimsSettings(ControlSettings):
    window_days: int = Field(7, ge=1, le=365)


class SplitClaimsSettings(ControlSettings):
    approval_limit: float = Field(500, gt=0)
    window_hours: int = Field(24, ge=1, le=168)
    min_claims: int = Field(2, ge=2, le=20)


class ApproverSettings(ControlSettings):
    allow_skip_level: bool = True


class FastApprovalSettings(ControlSettings):
    min_review_seconds: int = Field(120, ge=1, le=86400)


class OutlierManagerSettings(ControlSettings):
    min_decisions: int = Field(30, ge=1)
    min_rate_gap_points: float = Field(10, gt=0, le=100)


class OffHoursSettings(ControlSettings):
    business_start_hour: int = Field(9, ge=0, le=23)
    business_end_hour: int = Field(18, ge=1, le=24)
    flag_weekends: bool = True

    @model_validator(mode="after")
    def start_before_end(self):
        if self.business_start_hour >= self.business_end_hour:
            raise ValueError("business_start_hour must be before business_end_hour")
        return self


class ControlsSection(Strict):
    C1: DuplicateClaimsSettings
    C2: SplitClaimsSettings
    C3: ApproverSettings
    C4: FastApprovalSettings
    C5: OutlierManagerSettings
    C6: OffHoursSettings

    def by_id(self):
        return {name: getattr(self, name) for name in type(self).model_fields}


class MonitorConfig(Strict):
    fail_on_severity: Severity = "high"
    controls: ControlsSection

    def snapshot(self):
        """Plain dict saved with every run, so a result can be reproduced."""
        return self.model_dump()


def build_config(data):
    if not isinstance(data, dict):
        raise ConfigError("config file is empty or is not a YAML mapping")
    try:
        return MonitorConfig.model_validate(data)
    except ValidationError as exc:
        lines = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        raise ConfigError("invalid config:\n  " + "\n  ".join(lines)) from exc


def load_config(path=None):
    path = Path(path or os.getenv("CONTROLS_CONFIG") or DEFAULT_CONFIG_PATH)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file is not valid YAML: {exc}") from exc
    return build_config(data)