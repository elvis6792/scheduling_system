from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import date, time
from app.models.domain import Role


class DepartmentBase(BaseModel):
    name: str

class DepartmentCreate(DepartmentBase):
    pass

class Department(DepartmentBase):
    id: int

    class Config:
        from_attributes = True


class StaffBase(BaseModel):
    name: str
    department_id: int
    daily_work_hours: Optional[float] = 9.0

class StaffCreate(StaffBase):
    pass

class Staff(StaffBase):
    id: int

    class Config:
        from_attributes = True

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None
    daily_work_hours: Optional[float] = None


class ProgramBase(BaseModel):
    name: str
    content: Optional[str] = None
    estimated_hours: float
    color: str

class ProgramCreate(ProgramBase):
    pass

class Program(ProgramBase):
    id: int

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: Role

class User(UserBase):
    id: int
    role: Role
    staff_id: Optional[int] = None

    class Config:
        from_attributes = True


class ShiftBase(BaseModel):
    date: date
    department_id: int
    staff_id: int
    program_id: int
    notes: Optional[str] = None

class ShiftCreate(ShiftBase):
    duration: Optional[float] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

class ShiftUpdate(ShiftCreate):
    pass

class Shift(ShiftBase):
    id: int
    start_time: time
    end_time: time
    created_by_user_id: int

    class Config:
        from_attributes = True


class LeaveRecordBase(BaseModel):
    staff_id: int
    date: date
    leave_type: str = "特休"
    hours: float = 8.0

class LeaveCreate(LeaveRecordBase):
    pass

class LeaveRecord(LeaveRecordBase):
    id: int

    class Config:
        from_attributes = True


class ShiftSwapRequest(BaseModel):
    shift_id_a: int
    shift_id_b: int


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class GenericResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Any] = None


class WorkHoursOverrideBase(BaseModel):
    staff_id: int
    date: date
    hours: float


class WorkHoursOverrideCreate(WorkHoursOverrideBase):
    pass

