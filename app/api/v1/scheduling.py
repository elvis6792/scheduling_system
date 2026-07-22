import os
import hmac
import hashlib
import base64
import shutil
import json
from datetime import date, time, datetime, timedelta
from pathlib import Path
from calendar import monthrange
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Header, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from sqlmodel import select

from app.core.database import get_session, async_session_maker
from app.core.dependencies import (
    get_current_user, 
    verify_scheduling_window, 
    get_current_producer,
    check_date_against_scheduling_windows
)
from app.services.scheduler import (
    get_available_staff, create_shift, DoubleBookingError, 
    validate_total_hours, calculate_shift_times, validate_shift_overlap
) 
from agent.orchestrator import AgentOrchestrator
from app.models.domain import Shift, User, LeaveRecord, Program, SchedulingWindow, Staff, WorkHoursOverride
from app.models import schemas

from agent.llm.local_client import AsyncLocalLLMClient 

llm_client = AsyncLocalLLMClient()

orchestrator = AgentOrchestrator(llm_client, async_session_maker)

router = APIRouter()

def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="權限不足！此項操作僅限系統管理員階層執行。")
    return current_user

def require_producer_or_admin_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["admin", "producer"]:
        raise HTTPException(status_code=403, detail="權限不足！此項操作僅限系統管理員或製作人執行。")
    return current_user

@router.post("/work-hours-override")
async def set_work_hours_override(
    override: schemas.WorkHoursOverrideCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    為特定員工設定某天的工作時數上限。
    """
    # 權限檢查：只有 Admin, Producer 可以幫別人改；Staff 只能改自己的。
    if current_user.role not in ["admin", "producer"]:
        if current_user.staff_id != override.staff_id:
             raise HTTPException(status_code=403, detail="權限不足：您只能調整自己的上班時數。")

    # 查找是否已存在該員工、該日期的覆寫設定
    stmt = select(WorkHoursOverride).where(
        WorkHoursOverride.staff_id == override.staff_id,
        WorkHoursOverride.date == override.date,
    )
    existing_override = (await session.execute(stmt)).scalars().first()

    if existing_override:
        # 更新現有設定
        existing_override.hours = override.hours
        message = f"更新成功：已將員工 {override.staff_id} 在 {override.date} 的工時上限更新為 {override.hours} 小時。"
    else:
        # 建立新的覆寫設定
        new_override = WorkHoursOverride(**override.model_dump())
        session.add(new_override)
        message = f"建立成功：已為員工 {override.staff_id} 在 {override.date} 設定工時上限為 {override.hours} 小時。"

    await session.commit()
    return {"message": message}


@router.get("/work-hours-override")
async def get_work_hours_overrides(
    start_date: date,
    end_date: date,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    獲取指定日期範圍內的所有工時覆寫設定。
    """
    stmt = select(WorkHoursOverride).where(
        WorkHoursOverride.date >= start_date,
        WorkHoursOverride.date <= end_date,
    )
    results = (await session.execute(stmt)).scalars().all()
    return results


@router.post("/leaves")
async def add_leave(
    leave: schemas.LeaveCreate, 
    session: AsyncSession = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    try:
        exist_stmt = select(LeaveRecord).where(LeaveRecord.staff_id == leave.staff_id, LeaveRecord.date == leave.date)
        existing = (await session.execute(exist_stmt)).scalars().first()

        await validate_total_hours(
            session=session,
            staff_id=leave.staff_id,
            shift_date=leave.date,
            new_shift_hours=leave.hours, # 將請假時數視為一種特殊的 "shift"
        )

        if existing:
            existing.leave_type = leave.leave_type
            existing.hours = leave.hours
        else:
            new_leave = LeaveRecord(**leave.model_dump())
            session.add(new_leave)

        await session.commit()
        return {"message": "休假登錄成功"}
    except DoubleBookingError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail="伺服器內部錯誤")


@router.delete("/leaves/{leave_id}")
async def remove_leave(leave_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(require_producer_or_admin_role)):
    leave = await session.get(LeaveRecord, leave_id)
    if leave:
        await session.delete(leave)
        await session.commit()
    return {"message": "休假紀錄已移除"}


@router.get("/leaves")
async def get_leaves(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    
    stmt = select(LeaveRecord).join(Staff, LeaveRecord.staff_id == Staff.id)

    # 權限控管：精準分流 admin, producer, staff
    if current_user.role == "staff":
        # 1. 員工 (staff)：強制只能看自己所屬部門的休假
        if current_user.department_id:
            stmt = stmt.where(Staff.department_id == int(current_user.department_id))
        else:
            # 防呆：如果員工沒綁部門，就回傳空查詢，避免報錯
            stmt = stmt.where(Staff.department_id == -1)
    # 2. 管理員 (admin) 與 製作人 (producer)：預設可看全公司，無需額外過濾
    # (前端若需篩選，應在呼叫 API 時帶入 staff_id 或 department_id 等參數，但此 API 目前不支援)
        
    results = (await session.execute(stmt)).scalars().all()
    print(f"🔥🔥🔥 DEBUG: [{current_user.name}] 查到 {len(results)} 筆休假 🔥🔥🔥")
    
    return results


@router.post("/leaves/upload")
async def upload_leave_excel(file: UploadFile = File(...), current_user: User = Depends(require_producer_or_admin_role)):
    if not file.filename.endswith('.xlsx'): 
        raise HTTPException(status_code=400, detail="無效的檔案格式")
    return {"message": "檔案已接收"}



@router.get("/staff/available")
async def api_get_available_staff(
    date: date = Query(..., description="排班日期 (YYYY-MM-DD)"),
    department_id: int = Query(..., description="部門 ID"),
    session: AsyncSession = Depends(get_session)
):
    try:
        available_staff = await get_available_staff(
            session=session,
            target_date=date,
            department_id=department_id
        )
        return available_staff
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/shifts", dependencies=[Depends(verify_scheduling_window)])
async def assign_shift(
    shift: schemas.ShiftCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_producer_or_admin_role)
):
    try:
        duration: Optional[float] = None
        # Case 1: Manual scheduling with start and end time
        if shift.start_time and shift.end_time:
            start_dt = datetime.combine(shift.date, shift.start_time)
            end_dt = datetime.combine(shift.date, shift.end_time)
            if end_dt <= start_dt: # Handle overnight shifts
                end_dt += timedelta(days=1)
            duration = (end_dt - start_dt).total_seconds() / 3600
            
            # Since times are explicit, we must check for overlaps
            await validate_shift_overlap(
                session=session,
                staff_id=shift.staff_id,
                shift_date=shift.date,
                new_start_time=shift.start_time,
                new_end_time=shift.end_time
            )

        # Case 2: Auto-scheduling with duration
        elif shift.duration:
            duration = shift.duration
        
        # Case 3: Invalid input
        else:
            raise ValueError("排班請求格式錯誤：必須提供 'duration' 或 'start_time' 與 'end_time'。")

        # After determining duration, validate total work hours
        await validate_total_hours(
            session=session,
            staff_id=shift.staff_id,
            shift_date=shift.date,
            new_shift_hours=duration
        )

        new_shift = await create_shift(
            session=session,
            shift_date=shift.date,
            duration=duration,
            department_id=shift.department_id,
            staff_id=shift.staff_id,
            program_id=shift.program_id,
            created_by_user_id=current_user.id,
            notes=shift.notes,
            start_time=shift.start_time,
            end_time=shift.end_time
        )
        
        await session.commit()
        
        return {"message": "排班成功", "shift_id": new_shift.id}
    except (DoubleBookingError, ValueError) as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await session.rollback()
        # Log the exception for debugging
        print(f"An unexpected error occurred in assign_shift: {e}")
        raise HTTPException(status_code=500, detail="伺服器發生未預期的錯誤")


@router.get("/shifts/month")
async def get_monthly_shifts(year: int, month: int, department_id: Optional[int] = None, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    _, last_day = monthrange(year, month)
    
    # 乾淨俐落，不需要 selectinload
    stmt = select(Shift).where(
        Shift.date >= date(year, month, 1), 
        Shift.date <= date(year, month, last_day)
    )
    
    # 權限控管：精準分流 admin, producer, staff
    if current_user.role == "staff":
        # 1. 員工 (staff)：強制只能看自己所屬部門的班表
        if current_user.department_id:
            stmt = stmt.where(Shift.department_id == int(current_user.department_id))
        else:
            # 防呆：如果員工沒綁部門，就回傳空查詢，避免報錯
            stmt = stmt.where(Shift.department_id == -1)

    else:
        # 2. 管理員 (admin) 與 製作人 (producer)：預設可看全公司
        # 只有當前端「下拉選單」有傳入特定的 department_id 時，才進行過濾
        if department_id:
            stmt = stmt.where(Shift.department_id == int(department_id))

    results = (await session.execute(stmt)).scalars().all()
    print(f"🔥🔥🔥 DEBUG: [{current_user.name}] 查到 {len(results)} 筆班表 🔥🔥🔥")
    return results


@router.get("/shifts")
async def get_shifts(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    department_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    print(f"🔥🔥🔥 吐真劑啟動 (get_shifts) | 當前 Token 身分 -> ID: {current_user.id}, 角色: {current_user.role}, 部門: {current_user.department_id} 🔥🔥🔥")
    stmt = select(Shift)
    if start_date:
        stmt = stmt.where(Shift.date >= start_date)
    if end_date:
        stmt = stmt.where(Shift.date <= end_date)

    # 權限控管
    if current_user.role != "admin":
        # 非 Admin 強制只能看自己部門
        stmt = stmt.where(Shift.department_id == current_user.department_id)
    elif department_id:
        # Admin 可以指定看某部門
        stmt = stmt.where(Shift.department_id == department_id)
    
    result = await session.execute(stmt)
    return result.scalars().all()


@router.delete("/shifts/{shift_id:int}")
async def delete_shift(shift_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(require_producer_or_admin_role)):
    shift = await session.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="找不到紀錄")

    if current_user.role != "admin":
        await check_date_against_scheduling_windows(shift.date, session)

    await session.delete(shift)
    await session.commit()
    return {"message": "註銷成功"}



@router.put("/shifts/{shift_id:int}", dependencies=[Depends(verify_scheduling_window)])
async def update_shift(
    shift_id: int,
    update_data: schemas.ShiftUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_producer_or_admin_role)
):
    shift = await session.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="找不到紀錄")

    try:
        duration: Optional[float] = None
        # Determine duration and validate input
        if update_data.start_time and update_data.end_time:
            start_dt = datetime.combine(update_data.date, update_data.start_time)
            end_dt = datetime.combine(update_data.date, update_data.end_time)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            duration = (end_dt - start_dt).total_seconds() / 3600
        elif update_data.duration:
            duration = update_data.duration
        else:
            raise ValueError("更新請求格式錯誤：必須提供 'duration' 或 'start_time' 與 'end_time'。")

        # Validate total work hours for the day
        await validate_total_hours(
            session=session,
            staff_id=update_data.staff_id,
            shift_date=update_data.date,
            new_shift_hours=duration,
            shift_id_to_exclude=shift_id
        )

        update_dict = update_data.model_dump(exclude_unset=True)

        # If start/end times are provided manually, use them directly
        if 'start_time' in update_dict and 'end_time' in update_dict:
            await validate_shift_overlap(
                session=session,
                staff_id=update_data.staff_id,
                shift_date=update_data.date,
                new_start_time=update_data.start_time,
                new_end_time=update_data.end_time,
                shift_id_to_exclude=shift_id
            )
        # If only duration is provided, find the next available slot
        elif 'duration' in update_dict:
            start_time, end_time = await calculate_shift_times(
                session=session,
                staff_id=update_data.staff_id,
                shift_date=update_data.date,
                duration=duration,
                shift_id_to_exclude=shift_id
            )
            update_dict['start_time'] = start_time
            update_dict['end_time'] = end_time

        if 'duration' in update_dict:
            del update_dict['duration']

        for key, value in update_dict.items():
            setattr(shift, key, value)

        await session.commit()
        await session.refresh(shift)
        return {"message": "修改完成"}

    except (DoubleBookingError, ValueError) as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await session.rollback()
        print(f"An unexpected error occurred in update_shift: {e}")
        raise HTTPException(status_code=500, detail="伺服器發生未預期的錯誤")



@router.post("/shifts/swap")
async def swap_shifts(
    swap_req: schemas.ShiftSwapRequest, 
    session: AsyncSession = Depends(get_session), 
    current_user: User = Depends(require_producer_or_admin_role)
):
    # 1. 提取兩筆排班紀錄
    shift_a = await session.get(Shift, swap_req.shift_id_a)
    shift_b = await session.get(Shift, swap_req.shift_id_b)

    if not shift_a or not shift_b:
        raise HTTPException(status_code=404, detail="找不到指定的排班紀錄，無法互換。")

    if shift_a.date != shift_b.date:
        raise HTTPException(status_code=400, detail="只能互換同一天的班表。")

    if current_user.role != "admin":
        await check_date_against_scheduling_windows(shift_a.date, session)

    temp_staff_id = shift_a.staff_id
    shift_a.staff_id = shift_b.staff_id
    shift_b.staff_id = temp_staff_id

    await session.commit()
    return {"message": "同步互換完成"}



@router.post("/agent/chat")
async def web_agent_chat(
    req: schemas.ChatRequest, 
    session: AsyncSession = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    print(f"🔥🔥🔥 吐真劑啟動 (web_agent_chat) | 當前 Token 身分 -> ID: {current_user.id}, 角色: {current_user.role}, 部門: {current_user.department_id} 🔥🔥🔥")
    # 建立完整的上下文，不再只有 session_id
    agent_context = {
        "session_id": str(current_user.id),
        "user_id": current_user.id,
        "user_name": current_user.name,
        "role": current_user.role,
        "department_id": current_user.department_id,
        "staff_id": current_user.staff_id
    }
    
    response = await orchestrator.chat(
        user_message=req.message, 
        context=agent_context
    )
    return {"reply": response}



@router.get("/staff/list")
async def get_all_staff_api(session: AsyncSession = Depends(get_session)):
    """提供前端載入人員清單與下拉選單"""
    result = await session.execute(select(Staff))
    staff_list = result.scalars().all()
    return {
        "status": "success",
        "data": [
            {"id": staff.id, "name": staff.name, "daily_limit": staff.daily_work_hours}
            for staff in staff_list
        ]
    }
