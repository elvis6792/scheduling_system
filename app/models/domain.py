from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date as dt_date, time as dt_time, datetime
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    PRODUCER = "producer"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    role: str = Field(default="producer")  # 'admin', 'producer', 'staff'
    staff_id: Optional[int] = Field(default=None, foreign_key="staff.id")

    line_bind_code: str | None = Field(default=None, description="LINE 綁定碼")
    line_user_id: str | None = Field(default=None, description="綁定後的 LINE 唯一識別碼")



class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    staff: List["Staff"] = Relationship(back_populates="department")
    shifts: List["Shift"] = Relationship(back_populates="department")


class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department_id: int = Field(foreign_key="department.id")
    daily_work_hours: float = Field(default=9.0)
    shifts: List["Shift"] = Relationship(back_populates="staff", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    department: "Department" = Relationship(back_populates="staff")
    work_hours_overrides: List["WorkHoursOverride"] = Relationship(back_populates="staff", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    leave_records: List["LeaveRecord"] = Relationship(back_populates="staff", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class WorkHoursOverride(SQLModel, table=True):
    __tablename__ = "work_hours_override"
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", ondelete="CASCADE")
    date: dt_date
    hours: float
    staff: "Staff" = Relationship(back_populates="work_hours_overrides")



class Program(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    content: Optional[str] = None
    estimated_hours: float = Field(default=1.0)
    color: str = Field(default="#6366f1")
    shifts: List["Shift"] = Relationship(back_populates="program", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Leave(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id")
    date: dt_date
    start_time: dt_time
    end_time: dt_time


class Shift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt_date
    start_time: dt_time
    end_time: dt_time
    department_id: int = Field(foreign_key="department.id", ondelete="CASCADE")
    staff_id: int = Field(foreign_key="staff.id", ondelete="CASCADE")
    program_id: Optional[int] = Field(default=None, foreign_key="program.id", ondelete="SET NULL")
    created_by_user_id: int = Field(foreign_key="user.id")
    notes: Optional[str] = None

    staff: "Staff" = Relationship(back_populates="shifts")
    program: Optional["Program"] = Relationship(back_populates="shifts")
    department: "Department" = Relationship(back_populates="shifts")


class LeaveRecord(SQLModel, table=True):
    __tablename__ = "leave_record"
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", ondelete="CASCADE")
    date: dt_date
    leave_type: str = Field(default="特休")
    hours: float = Field(default=8.0)
    
    staff: "Staff" = Relationship(back_populates="leave_records")


class SchedulingWindow(SQLModel, table=True):
    __tablename__ = "scheduling_windows"
    id: Optional[int] = Field(default=None, primary_key=True)
    start_date: dt_date
    end_date: dt_date
    description: str
    is_active: bool = Field(default=True)


class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_configs"
    key: str = Field(primary_key=True, index=True)
    value: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, nullable=True)


class ChatHistory(SQLModel, table=True):
    __tablename__ = "chat_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
