from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from controls_monitor.db import Base


# the finance system being monitored 


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    department: Mapped[str] = mapped_column(String(50))
    job_title: Mapped[str] = mapped_column(String(80))
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    category: Mapped[str] = mapped_column(String(40))
    vendor: Mapped[str] = mapped_column(String(100))
    receipt_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_expenses_status_valid",
        ),
        Index("ix_expenses_employee_submitted", "employee_id", "submitted_at"),
        Index("ix_expenses_approver", "approver_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    action: Mapped[str] = mapped_column(String(20))  # submitted / approved / rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_audit_log_expense", "expense_id"),)





class InjectedViolation(Base):
    __tablename__ = "injected_violations"

    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[str] = mapped_column(String(10))  # C1 ... C6
    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id"), nullable=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    note: Mapped[str] = mapped_column(String(255), default="")


# output tables

class ControlRun(Base):
    __tablename__ = "control_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    total_exceptions: Mapped[int] = mapped_column(Integer, default=0)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)


class ControlResult(Base):
    __tablename__ = "control_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("control_runs.id", ondelete="CASCADE")
    )
    control_id: Mapped[str] = mapped_column(String(10))
    control_name: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))  # passed / failed / error
    exception_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_control_results_run", "run_id"),)


class ControlException(Base):
    __tablename__ = "control_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("control_runs.id", ondelete="CASCADE")
    )
    control_id: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id"), nullable=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(255))
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_control_exceptions_run", "run_id", "control_id"),)