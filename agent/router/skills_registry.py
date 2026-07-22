from enum import Enum
from typing import List, Dict

class SkillName(str, Enum):
    AssignProgramStaff = "AssignProgramStaff"
    CancelProgramShift = "CancelProgramShift"
    BatchAssign = "BatchAssign"
    SwapShift = "SwapShift"
    QuerySchedule = "QuerySchedule"
    CheckDailyStatus = "CheckDailyStatus"
    UndoLastAction = "UndoLastAction"
    RegisterLeave = "RegisterLeave"
    Unknown = "Unknown"

SKILL_WORKFLOWS: Dict[SkillName, List[str]] = {
    SkillName.AssignProgramStaff: ["check_daily_status", "create_shift"],
    SkillName.CancelProgramShift: ["query_schedule", "cancel_shift"],
    SkillName.BatchAssign: ["batch_check_daily_status", "batch_create_shift"],
    SkillName.SwapShift: ["swap_shift"],
    SkillName.QuerySchedule: ["query_schedule"],
    SkillName.CheckDailyStatus: ["check_daily_status"],
    SkillName.RegisterLeave: ["register_leave"],
    SkillName.UndoLastAction: [],
    SkillName.Unknown: []
}

REQUIRED_SLOTS: Dict[SkillName, List[str]] = {
    SkillName.AssignProgramStaff: ["staff_name", "date"], # 移除 program_name 必填
    SkillName.CancelProgramShift: ["date"], # 移除 program_name 必填，只要有日期就能查
    SkillName.BatchAssign: ["program_name", "staff_name", "date"],
    SkillName.SwapShift: ["program_name", "old_staff_name", "new_staff_name", "date"],
    SkillName.QuerySchedule: [],
    SkillName.CheckDailyStatus: ["staff_name", "date"],
    SkillName.RegisterLeave: ["staff_name", "date"],
}
