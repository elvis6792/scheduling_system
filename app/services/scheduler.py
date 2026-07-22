from datetime import date, time, datetime, timedelta
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Sequence, Tuple

from app.models.domain import Staff, LeaveRecord, Shift, WorkHoursOverride
from app.services.exceptions import DoubleBookingError
from app.services.scheduling_policy_engine import calculate_hours_diff

async def validate_total_hours(
    session: AsyncSession, 
    staff_id: int, 
    shift_date: date, 
    new_shift_hours: float,
    shift_id_to_exclude: Optional[int] = None,
    pending_hours: float = 0.0
):
    # 優先查詢當日的工時覆寫設定
    override_stmt = select(WorkHoursOverride).where(
        WorkHoursOverride.staff_id == staff_id,
        WorkHoursOverride.date == shift_date,
    )
    override = (await session.execute(override_stmt)).scalars().first()

    if override:
        base_daily_limit = override.hours
    else:
        # 如果沒有覆寫，則使用員工的基本設定
        staff_member = await session.get(Staff, staff_id)
        if not staff_member:
            # 找不到員工資料時的備用預設值
            base_daily_limit = 8.0
        else:
            base_daily_limit = staff_member.daily_work_hours
    # ------------------------------------------

    # Apply deduction to the limit itself, as per user's clarification
    effective_daily_limit = base_daily_limit - math.floor(base_daily_limit / 9)

    leave_hours = 0
    leave_record = (await session.execute(
        select(LeaveRecord).where(LeaveRecord.staff_id == staff_id, LeaveRecord.date == shift_date)
    )).scalars().first()
    if leave_record:
        leave_hours = leave_record.hours

    existing_shifts_query = select(Shift).where(Shift.staff_id == staff_id, Shift.date == shift_date)
    if shift_id_to_exclude:
        existing_shifts_query = existing_shifts_query.where(Shift.id != shift_id_to_exclude)
    
    existing_shifts = (await session.execute(existing_shifts_query)).scalars().all()
    existing_shift_hours = sum(calculate_hours_diff(s.start_time, s.end_time) for s in existing_shifts)

    # Sum of GROSS hours
    total_hours = leave_hours + existing_shift_hours + new_shift_hours + pending_hours
    
    if total_hours > effective_daily_limit + 0.01:
        error_detail = (
            f"總工時超時！(休假 {leave_hours:.1f}h + "
            f"已排班 {existing_shift_hours:.1f}h + "
            f"本次 {new_shift_hours:.1f}h"
            f"{f' + 待辦 {pending_hours:.1f}h' if pending_hours > 0 else ''} = {total_hours:.1f}h)，"
            f"已超過單日有效上限 {effective_daily_limit:.1f} 小時 (來自原始上限 {base_daily_limit:.1f}h)。"
        )
        raise DoubleBookingError(error_detail)


async def calculate_shift_times(
    session: AsyncSession,
    staff_id: int,
    shift_date: date,
    duration: float,
    shift_id_to_exclude: Optional[int] = None,
    pending_hours: float = 0.0
) -> Tuple[time, time]:
    # 取得員工資料，以決定工作日的起訖
    staff_member = await session.get(Staff, staff_id)
    if not staff_member:
        raise ValueError(f"calculate_shift_times: 找不到員工 ID: {staff_id}")

    work_start_dt = datetime.combine(shift_date, time(9, 0)) # 預設工作開始時間

    # 1. 收集所有已佔用的時間區段 (休假 + 已排班)
    occupied_slots = []
    
    # 加入休假時段
    leave_record = (await session.execute(
        select(LeaveRecord).where(LeaveRecord.staff_id == staff_id, LeaveRecord.date == shift_date)
    )).scalars().first()
    if leave_record and leave_record.hours > 0:
        # 假設休假都從工作開始時間算
        leave_start_dt = work_start_dt
        leave_end_dt = leave_start_dt + timedelta(hours=leave_record.hours)
        occupied_slots.append((leave_start_dt, leave_end_dt))

    # 加入已排班時段
    existing_shifts_query = select(Shift).where(Shift.staff_id == staff_id, Shift.date == shift_date)
    if shift_id_to_exclude:
        existing_shifts_query = existing_shifts_query.where(Shift.id != shift_id_to_exclude)
    existing_shifts = (await session.execute(existing_shifts_query)).scalars().all()
    for shift in existing_shifts:
        shift_start_dt = datetime.combine(shift_date, shift.start_time)
        shift_end_dt = datetime.combine(shift_date, shift.end_time)
        if shift_end_dt < shift_start_dt: # 處理跨夜班
            shift_end_dt += timedelta(days=1)
        occupied_slots.append((shift_start_dt, shift_end_dt))

    # 2. 排序佔用區段，並找出可插入的空檔
    occupied_slots.sort()

    # 將工作開始時間視為第一個空檔的起點
    last_end_time = work_start_dt
    
    # 加上待辦時數，預留空位
    if pending_hours > 0:
        # 找出所有佔用區段的最晚結束時間
        if occupied_slots:
            latest_occupied_end = max(slot[1] for slot in occupied_slots)
            last_end_time = max(last_end_time, latest_occupied_end)
        
        # 從最晚時間點開始，為 pending_hours 預留位置
        last_end_time += timedelta(hours=pending_hours)

    # 3. 遍歷已排序的佔用區段，尋找第一個足夠大的空檔
    for start, end in occupied_slots:
        # 計算當前空檔的長度
        gap_duration = (start - last_end_time).total_seconds() / 3600
        if gap_duration >= duration:
            # 找到足夠的空檔，直接返回
            new_end_dt = last_end_time + timedelta(hours=duration)
            return last_end_time.time(), new_end_dt.time()
        # 更新下一個空檔的起點
        last_end_time = max(last_end_time, end)
    
    # 4. 如果遍歷完所有佔用區段後仍有空間，則將新班表安排在最後
    # (此處不需檢查總工時，validate_total_hours 會把關)
    new_end_dt = last_end_time + timedelta(hours=duration)
    return last_end_time.time(), new_end_dt.time()



async def get_available_staff(
    session: AsyncSession, 
    target_date: date,
    department_id: Optional[int] = None,
) -> List[dict]:
    staff_query = select(Staff)
    if department_id:
        staff_query = staff_query.where(Staff.department_id == department_id)
    all_staff_result = await session.execute(staff_query)
    all_staff = all_staff_result.scalars().all()
    staff_ids = [s.id for s in all_staff]
    
    if not staff_ids:
        return []

    leaves_query = select(LeaveRecord).where(
        LeaveRecord.staff_id.in_(staff_ids),
        LeaveRecord.date == target_date
    )
    all_leaves_result = await session.execute(leaves_query)
    all_leaves = all_leaves_result.scalars().all()
    leave_hours_map = {leave.staff_id: leave.hours for leave in all_leaves}

    shifts_query = select(Shift).where(
        Shift.staff_id.in_(staff_ids),
        Shift.date == target_date
    )
    all_shifts_result = await session.execute(shifts_query)
    all_shifts = all_shifts_result.scalars().all()
    
    shift_hours_map = {} # This will store total gross shift hours
    for shift in all_shifts:
        hours = calculate_hours_diff(shift.start_time, shift.end_time)
        shift_hours_map[shift.staff_id] = shift_hours_map.get(shift.staff_id, 0) + hours
    
    detailed_staff_status = []
    for staff in all_staff:
        base_daily_limit = staff.daily_work_hours
        effective_daily_limit = base_daily_limit - math.floor(base_daily_limit / 9)
        
        leave_hours = leave_hours_map.get(staff.id, 0)
        total_gross_shift_hours = shift_hours_map.get(staff.id, 0)
        
        remaining_available_hours = effective_daily_limit - (leave_hours + total_gross_shift_hours)
        
        detailed_staff_status.append({
            **staff.__dict__,
            "id": staff.id,
            "daily_limit": effective_daily_limit, # Return the effective limit
            "base_daily_limit": base_daily_limit, # Also return the base for clarity
            "leave_hours": leave_hours,
            "total_gross_shift_hours": total_gross_shift_hours,
            "remaining_available_hours": round(max(0.0, remaining_available_hours), 2),
            "is_available": remaining_available_hours > 0.01
        })
            
    return detailed_staff_status


async def create_shift(
    session: AsyncSession,
    shift_date: date,
    duration: float,
    department_id: int,
    staff_id: int,
    program_id: int,
    created_by_user_id: int,
    notes: Optional[str] = None,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None
) -> Shift:
    
    staff_member = await session.get(Staff, staff_id)
    if not staff_member:
        raise ValueError(f"找不到員工 ID: {staff_id}")
    if staff_member.department_id != department_id:
        raise ValueError(f"資料完整性衝突：員工 {staff_member.name} (ID: {staff_id}) 並不屬於您指定的部門 (ID: {department_id})。")

    # The calling service is now responsible for validations (total hours, overlaps).
    # This function will either use provided times or calculate them if not provided.
    if start_time is None or end_time is None:
        start_time, end_time = await calculate_shift_times(session, staff_id, shift_date, duration)

    new_shift = Shift(
        date=shift_date,
        start_time=start_time,
        end_time=end_time,
        department_id=department_id,
        staff_id=staff_id,
        program_id=program_id,
        created_by_user_id=created_by_user_id,
        notes=notes
    )
    session.add(new_shift)
    try:
        await session.flush() # Flush to get ID, commit is handled by the calling service
        return new_shift
    except IntegrityError:
        await session.rollback()
        raise DoubleBookingError("排班衝突：該時段已被搶先指派！請重新整理後再試。")


async def validate_shift_overlap(
    session: AsyncSession,
    staff_id: int,
    shift_date: date,
    new_start_time: time,
    new_end_time: time,
    shift_id_to_exclude: Optional[int] = None
):
    """
    Checks if a new shift time range overlaps with existing shifts for a staff member on a given day.
    """
    # Query for existing shifts
    existing_shifts_query = select(Shift).where(
        Shift.staff_id == staff_id,
        Shift.date == shift_date
    )
    if shift_id_to_exclude:
        existing_shifts_query = existing_shifts_query.where(Shift.id != shift_id_to_exclude)
    
    existing_shifts = (await session.execute(existing_shifts_query)).scalars().all()

    # Combine new shift times with the date for comparison
    new_start_dt = datetime.combine(shift_date, new_start_time)
    new_end_dt = datetime.combine(shift_date, new_end_time)
    if new_end_dt <= new_start_dt: # Handle overnight shifts
        new_end_dt += timedelta(days=1)

    for shift in existing_shifts:
        existing_start_dt = datetime.combine(shift_date, shift.start_time)
        existing_end_dt = datetime.combine(shift_date, shift.end_time)
        if existing_end_dt <= existing_start_dt: # Handle overnight shifts
            existing_end_dt += timedelta(days=1)

        # Overlap check: (A.start < B.end) and (B.start < A.end)
        if new_start_dt < existing_end_dt and existing_start_dt < new_end_dt:
            staff = await session.get(Staff, staff_id)
            staff_name = staff.name if staff else f"ID {staff_id}"
            raise DoubleBookingError(
                f"時間重疊衝突！員工 {staff_name} 在 {shift_date.strftime('%Y-%m-%d')} 的時段 "
                f"({existing_start_dt.strftime('%H:%M')} - {existing_end_dt.strftime('%H:%M')}) "
                f"與新的班次時段 ({new_start_dt.strftime('%H:%M')} - {new_end_dt.strftime('%H:%M')}) 發生重疊。"
            )
