import math
from datetime import datetime, timedelta, time, date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.domain import Shift, Staff, LeaveRecord
from app.services.exceptions import DoubleBookingError


def calculate_hours_diff(start_time: time, end_time: time) -> float:
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(datetime.min, start_time)
    end_dt = datetime.combine(datetime.min, end_time)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    
    duration_seconds = (end_dt - start_dt).total_seconds()
    raw_hours = duration_seconds / 3600
    
    return round(raw_hours, 2)


class SchedulingPolicyEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_swap(self, shift_to_take: Shift, new_staff: Staff, shift_to_exclude_id: Optional[int] = None):
        await self.validate_overlap(shift_to_take, new_staff, shift_to_exclude_id)
        await self.validate_hours(shift_to_take, new_staff, shift_to_exclude_id)
        # In the future, we can add validate_rest here.

    async def validate_overlap(self, shift_to_take: Shift, new_staff: Staff, shift_to_exclude_id: Optional[int] = None):
        """
        Checks if a new shift time range overlaps with existing shifts for a staff member on a given day.
        """
        existing_shifts_query = select(Shift).where(
            Shift.staff_id == new_staff.id,
            Shift.date == shift_to_take.date
        )
        if shift_to_exclude_id:
            existing_shifts_query = existing_shifts_query.where(Shift.id != shift_to_exclude_id)
        
        existing_shifts_result = await self.db.execute(existing_shifts_query)
        existing_shifts = existing_shifts_result.scalars().all()

        new_start_dt = datetime.combine(shift_to_take.date, shift_to_take.start_time)
        new_end_dt = datetime.combine(shift_to_take.date, shift_to_take.end_time)
        if new_end_dt <= new_start_dt: # Handle overnight shifts
            new_end_dt += timedelta(days=1)

        for shift in existing_shifts:
            existing_start_dt = datetime.combine(shift.date, shift.start_time)
            existing_end_dt = datetime.combine(shift.date, shift.end_time)
            if existing_end_dt <= existing_start_dt: # Handle overnight shifts
                existing_end_dt += timedelta(days=1)

            if new_start_dt < existing_end_dt and existing_start_dt < new_end_dt:
                raise DoubleBookingError(
                    f"時間重疊衝突！員工 {new_staff.name} 在 {shift_to_take.date.strftime('%Y-%m-%d')} 的時段 "
                    f"({existing_start_dt.strftime('%H:%M')} - {existing_end_dt.strftime('%H:%M')}) "
                    f"與新的班次時段 ({new_start_dt.strftime('%H:%M')} - {new_end_dt.strftime('%H:%M')}) 發生重疊。"
                )

    async def validate_hours(self, shift_to_take: Shift, new_staff: Staff, shift_to_exclude_id: Optional[int] = None):
        base_daily_limit = new_staff.daily_work_hours
        effective_daily_limit = base_daily_limit - math.floor(base_daily_limit / 9)
        
        new_shift_hours = calculate_hours_diff(shift_to_take.start_time, shift_to_take.end_time)

        leave_hours = 0
        leave_record_result = await self.db.execute(
            select(LeaveRecord).where(LeaveRecord.staff_id == new_staff.id, LeaveRecord.date == shift_to_take.date)
        )
        leave_record = leave_record_result.scalars().first()
        if leave_record:
            leave_hours = leave_record.hours

        existing_shifts_query = select(Shift).where(Shift.staff_id == new_staff.id, Shift.date == shift_to_take.date)
        if shift_to_exclude_id:
            existing_shifts_query = existing_shifts_query.where(Shift.id != shift_to_exclude_id)
        
        existing_shifts_result = await self.db.execute(existing_shifts_query)
        existing_shifts = existing_shifts_result.scalars().all()
        existing_shift_hours = sum(calculate_hours_diff(s.start_time, s.end_time) for s in existing_shifts)

        total_hours = leave_hours + existing_shift_hours + new_shift_hours
        
        if total_hours > effective_daily_limit + 0.01:
            error_detail = (
                f"總工時超時！(休假 {leave_hours:.1f}h + "
                f"已排班 {existing_shift_hours:.1f}h + "
                f"本次 {new_shift_hours:.1f}h = {total_hours:.1f}h)，"
                f"已超過單日有效上限 {effective_daily_limit:.1f} 小時 (來自原始上限 {base_daily_limit:.1f}h)。"
            )
            raise DoubleBookingError(error_detail)
            
    def validate_rest(self, shift: Shift, staff: Staff):
        """
        Placeholder for validating rest period constraints.
        """
        # TODO: Implement rest period validation logic
        pass

    async def check_daily_hours(self, staff: Staff, check_date: date, new_shift_hours: float) -> dict:
        """
        Calculates the total hours for a staff on a given day, including a potential new shift.
        Returns a dictionary with the breakdown of hours.
        The daily limit returned is the 'effective' limit after deduction.
        """
        base_daily_limit = staff.daily_work_hours
        effective_daily_limit = base_daily_limit - math.floor(base_daily_limit / 9)

        # Calculate scheduled hours (gross)
        shifts_query = select(Shift).where(Shift.staff_id == staff.id, Shift.date == check_date)
        existing_shifts = (await self.db.execute(shifts_query)).scalars().all()
        scheduled_hours = sum(calculate_hours_diff(s.start_time, s.end_time) for s in existing_shifts)

        # Calculate leave hours
        leave_query = select(LeaveRecord).where(LeaveRecord.staff_id == staff.id, LeaveRecord.date == check_date)
        leave_record = (await self.db.execute(leave_query)).scalars().first()
        leave_hours = leave_record.hours if leave_record else 0

        total_hours = scheduled_hours + leave_hours + new_shift_hours
        remaining_hours = effective_daily_limit - (scheduled_hours + leave_hours)

        return {
            "scheduled_hours": scheduled_hours,
            "leave_hours": leave_hours,
            "new_shift_hours": new_shift_hours,
            "total_hours_including_new": total_hours,
            "base_daily_limit": base_daily_limit,
            "daily_limit": effective_daily_limit,
            "remaining_hours": remaining_hours
        }
