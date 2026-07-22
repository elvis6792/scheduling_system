import math
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.domain import Shift, Staff, Program, LeaveRecord, Department
from app.services.scheduling_policy_engine import (
    SchedulingPolicyEngine,
)
from app.services.exceptions import DoubleBookingError, StaffNotFoundError, ProgramNotFoundError, AmbiguousEntityError
from typing import List, Tuple, Optional
from datetime import date, time, datetime, timedelta
from sqlmodel import select

class SchedulingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.policy_engine = SchedulingPolicyEngine(db)

    async def assign_shift(
        self,
        staff_name: str,
        program_name: str,
        target_date: date,
        user_id: int,
        notes: Optional[str] = None
    ) -> Shift:
        """
        核心排班服務：接收名稱，解析 ID，驗證規則，並建立班表。
        """
        # 1. 解析實體 ID
        staff_stmt = select(Staff).where(Staff.name.like(f"%{staff_name}%"))
        staff = (await self.db.execute(staff_stmt)).scalars().first()
        if not staff:
            raise StaffNotFoundError(f"找不到員工「{staff_name}」。")

        prog_stmt = select(Program).where(Program.name.like(f"%{program_name}%"))
        program = (await self.db.execute(prog_stmt)).scalars().first()
        if not program:
            raise ProgramNotFoundError(f"找不到節目「{program_name}」。")

        # 2. 呼叫底層的 scheduler (這部分可以逐步整合進來)
        from app.services.scheduler import create_shift as create_shift_service

        new_shift = await create_shift_service(
            session=self.db,
            shift_date=target_date,
            duration=program.estimated_hours,
            department_id=staff.department_id,
            staff_id=staff.id,
            program_id=program.id,
            created_by_user_id=user_id,
            notes=notes
        )

        # 關鍵修復：在 commit 後，刷新 new_shift 物件以載入關聯的 staff 和 program。
        # 這樣回傳給工具層的物件才會包含完整的資訊。
        await self.db.commit()
        await self.db.refresh(new_shift, ["staff", "program"])

        # 3. 回傳建立好的 Shift 物件
        return new_shift


    async def swap_shifts(self, shift1_id: int, shift2_id: int) -> dict:
        pass

    async def batch_assign(self, staff_id: int, program_id: int, dates: List[date], user_id: int) -> dict:
        """
        Creates multiple shifts for a staff member on specified dates for a given program.
        Validates all potential shifts before committing.
        """
        try:
            staff = await self.db.get(Staff, staff_id)
            if not staff:
                raise ValueError(f"Staff with id {staff_id} not found")

            program = await self.db.get(Program, program_id)
            if not program:
                raise ValueError(f"Program with id {program_id} not found")

            new_shifts = []
            validation_errors = []

            # Pre-calculate pending hours for validation
            pending_hours_per_day = {}
            for d in dates:
                pending_hours_per_day[d] = pending_hours_per_day.get(d, 0) + program.estimated_hours

            # 1. Validation phase
            for d in dates:
                # 預計在當天新增的「毛」工時
                raw_new_hours_on_day = pending_hours_per_day[d]

                # 取得當天已排班的「淨」工時
                hour_details = await self.policy_engine.check_daily_hours(staff, d, raw_new_hours_on_day)
                existing_net_hours = hour_details['scheduled_hours']
                leave_hours = hour_details['leave_hours']

                # 模擬排班後的「總毛工時」，並計算出最終的「總淨工時」
                total_raw_hours = existing_net_hours + raw_new_hours_on_day
                total_net_hours = total_raw_hours - math.floor(total_raw_hours / 9)

                # 用最終的「總淨工時」加上「休假時數」來判斷是否超時
                if (total_net_hours + leave_hours) > staff.daily_work_hours:
                    error_detail = (
                        f"{d.strftime('%Y-%m-%d')}: 將超時 (已排班 {existing_net_hours:.1f}h + "
                        f"休假 {leave_hours:.1f}h + "
                        f"本次批次 {raw_new_hours_on_day:.1f}h = {total_net_hours + leave_hours:.1f}h)，"
                        f"已超過單日 {staff.daily_work_hours:.1f} 小時上限。"
                    )
                    validation_errors.append(error_detail)
            
            if validation_errors:
                raise DoubleBookingError("工時驗證失敗：\n- " + "\n- ".join(validation_errors))

            # 2. Creation phase
            created_shifts_on_day = {}
            for d in dates:
                # Calculate pending hours for this specific shift creation
                # This is the sum of hours of other new shifts on the same day
                pending_hours = created_shifts_on_day.get(d, 0)

                start_time, end_time = await self._calculate_shift_times(
                    staff_id=staff.id,
                    shift_date=d,
                    duration=program.estimated_hours,
                    pending_hours=pending_hours
                )
                
                new_shift = Shift(
                    date=d,
                    staff_id=staff.id,
                    program_id=program.id,
                    start_time=start_time,
                    end_time=end_time,
                    department_id=staff.department_id,
                    created_by_user_id=user_id
                )
                new_shifts.append(new_shift)
                
                # Add current shift's hours to the created total for the day
                created_shifts_on_day[d] = created_shifts_on_day.get(d, 0) + program.estimated_hours

            self.db.add_all(new_shifts)
            await self.db.commit()

            return {"created_count": len(new_shifts), "shifts": new_shifts}

        except Exception as e:
            await self.db.rollback()
            raise e

    async def _calculate_shift_times(
        self, staff_id: int, shift_date: date, duration: float, pending_hours: float = 0.0
    ) -> Tuple[time, time]:
        work_start_dt = datetime.combine(shift_date, time(9, 0))
        occupied_slots = []

        leave_result = await self.db.execute(select(LeaveRecord).where(LeaveRecord.staff_id == staff_id, LeaveRecord.date == shift_date))
        leave_record = leave_result.scalars().first()
        if leave_record and leave_record.hours > 0:
            leave_start_dt = work_start_dt
            leave_end_dt = leave_start_dt + timedelta(hours=leave_record.hours)
            occupied_slots.append((leave_start_dt, leave_end_dt))

        shifts_result = await self.db.execute(select(Shift).where(Shift.staff_id == staff_id, Shift.date == shift_date))
        existing_shifts = shifts_result.scalars().all()
        for shift in existing_shifts:
            shift_start_dt = datetime.combine(shift_date, shift.start_time)
            shift_end_dt = datetime.combine(shift_date, shift.end_time)
            if shift_end_dt < shift_start_dt:
                shift_end_dt += timedelta(days=1)
            occupied_slots.append((shift_start_dt, shift_end_dt))

        occupied_slots.sort()
        last_end_time = work_start_dt

        if pending_hours > 0:
            if occupied_slots:
                latest_occupied_end = max(slot[1] for slot in occupied_slots)
                last_end_time = max(last_end_time, latest_occupied_end)
            last_end_time += timedelta(hours=pending_hours)

        for start, end in occupied_slots:
            gap_duration = (start - last_end_time).total_seconds() / 3600
            if gap_duration >= duration:
                new_end_dt = last_end_time + timedelta(hours=duration)
                return last_end_time.time(), new_end_dt.time()
            last_end_time = max(last_end_time, end)
        
        new_end_dt = last_end_time + timedelta(hours=duration)
        return last_end_time.time(), new_end_dt.time()

    # ... (keep swap_shifts and other methods if any)

    async def resolve_entity(self, target_name: str) -> Optional[Staff | Department]:
        # Check for staff
        staff_stmt = select(Staff).where(Staff.name.like(f"%{target_name}%"))
        staff_results = (await self.db.execute(staff_stmt)).scalars().all()

        # Check for department
        dept_stmt = select(Department).where(Department.name.like(f"%{target_name}%"))
        dept_results = (await self.db.execute(dept_stmt)).scalars().all()

        total_found = len(staff_results) + len(dept_results)

        if total_found > 1:
            matches = [{"name": s.name, "type": "staff"} for s in staff_results] + \
                      [{"name": d.name, "type": "department"} for d in dept_results]
            raise AmbiguousEntityError(f"找到多個符合「{target_name}」的目標。", matches=matches)

        if len(staff_results) == 1:
            return staff_results[0]
        
        if len(dept_results) == 1:
            return dept_results[0]

        # Ambiguous or not found
        raise StaffNotFoundError(f"在系統中找不到名為「{target_name}」的員工或部門。")


    async def query_shifts(self, staff_name: Optional[str] = None, program_name: Optional[str] = None, department_name: Optional[str] = None, dates: Optional[List[date]] = None) -> List[Shift]:
        """
        Dynamically queries for shifts based on provided criteria.
        """
        stmt = select(Shift).options(
            selectinload(Shift.staff), 
            selectinload(Shift.program),
            selectinload(Shift.department)
        )

        if dates:
            stmt = stmt.where(Shift.date.in_(dates))

        if department_name:
            dept_stmt = select(Department.id).where(Department.name.like(f"%{department_name}%"))
            dept_id = (await self.db.execute(dept_stmt)).scalars().first()
            if not dept_id:
                return []
            stmt = stmt.where(Shift.department_id == dept_id)

        if staff_name:
            staff_stmt = select(Staff.id).where(Staff.name.like(f"%{staff_name}%"))
            staff_id = (await self.db.execute(staff_stmt)).scalars().first()
            if not staff_id:
                return []
            stmt = stmt.where(Shift.staff_id == staff_id)

        if program_name:
            prog_stmt = select(Program.id).where(Program.name.like(f"%{program_name}%"))
            prog_id = (await self.db.execute(prog_stmt)).scalars().first()
            if not prog_id:
                return []
            stmt = stmt.where(Shift.program_id == prog_id)
        
        stmt = stmt.order_by(Shift.date, Shift.start_time)

        result = await self.db.execute(stmt)
        return result.scalars().unique().all()

    async def cancel_shifts(self, shift_ids: List[int]) -> int:
        """
        Deletes shifts based on a list of shift IDs.
        Returns the number of deleted shifts.
        """
        if not shift_ids:
            return 0

        shifts_to_delete = (await self.db.execute(
            select(Shift).where(Shift.id.in_(shift_ids))
        )).scalars().all()
        
        count = len(shifts_to_delete)
        if count > 0:
            for shift in shifts_to_delete:
                await self.db.delete(shift)
            await self.db.commit()
            
        return count
