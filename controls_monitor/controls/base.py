from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def to_jsonable(value):
    """Make evidence safe to store as JSON (Decimal and datetime are not)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


@dataclass
class Finding:
    """One exception: what was wrong and the rows that prove it."""

    reason: str
    expense_id: int | None = None
    employee_id: int | None = None
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        self.evidence = to_jsonable(self.evidence)





class Control:
    """Base class. A control = one SQL file + settings from the YAML config."""
    control_id: str = ""
    name: str = ""
    description: str = ""
    sql_file: str = ""
    sql_dir: Path = SQL_DIR

    def __init__(self, settings):
        self.settings = settings

    @property
    def severity(self):
        return self.settings.severity

    def params(self):
        """Thresholds passed to the SQL as named bind parameters."""
        return self.settings.model_dump(exclude={"name", "enabled", "severity"})

    def load_sql(self):
        return (self.sql_dir / self.sql_file).read_text(encoding="utf-8")

    def row_to_finding(self, row):
        raise NotImplementedError

    def run(self, session):
        rows = session.execute(text(self.load_sql()), self.params()).mappings().all()
        return [self.row_to_finding(dict(row)) for row in rows]