import random
import string
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.models.domain import User, SchedulingWindow, SystemConfig, Staff

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="權限不足")
    return current_user


class TimeWindowCreate(BaseModel):
    start_date: date
    end_date: date
    description: str

@router.get("/time-windows")
async def get_time_windows(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    stmt = select(SchedulingWindow).order_by(SchedulingWindow.start_date.desc())
    result = await session.execute(stmt)
    return result.scalars().all()

@router.post("/time-windows")
async def create_time_window(
    payload: TimeWindowCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="起始日期不能晚於結束日期。"
        )

    new_window = SchedulingWindow(
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        is_active=True
    )

    session.add(new_window)
    await session.commit()
    await session.refresh(new_window)

    return new_window

@router.put("/time-windows/{window_id}/toggle")
async def toggle_time_window(
    window_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    window = await session.get(SchedulingWindow, window_id)
    if not window:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的時間窗。")

    window.is_active = not window.is_active
    await session.commit()

    return {"message": "狀態切換成功", "is_active": window.is_active}

class QuickTimeWindow(BaseModel):
    end_date: date

@router.post("/time-windows/quick-set")
async def quick_set_time_window(
    payload: QuickTimeWindow,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    tz = ZoneInfo("Asia/Taipei")
    today = datetime.now(tz).date()

    if payload.end_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="開放截止日不能早於今天。"
        )

    # 1. 將過去所有的時間窗全部設為失效 (保持資料庫乾淨，只有一個生效中)
    await session.execute(
        update(SchedulingWindow).values(is_active=False)
    )

    # 2. 建立一筆新的全域開放規則 (從今天起到指定的截止日)
    new_window = SchedulingWindow(
        start_date=today,
        end_date=payload.end_date,
        description=f"全域快速開放至 {payload.end_date.strftime('%Y-%m-%d')}",
        is_active=True
    )

    session.add(new_window)
    await session.commit()
    await session.refresh(new_window)

    return {"message": f"系統已成功開放排班權限至 {payload.end_date}"}


class ConfigUpdate(BaseModel):
    value: str

@router.get("/config/{key}")
async def get_config(key: str, session: AsyncSession = Depends(get_session)):
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    config = (await session.execute(stmt)).scalars().first()
    if not config:
        return {"key": key, "value": ""}
    return {"key": key, "value": config.value}

@router.post("/config/{key}")
async def update_config(key: str, payload: ConfigUpdate, session: AsyncSession = Depends(get_session)):
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    config = (await session.execute(stmt)).scalars().first()
    
    if config:
        config.value = payload.value
    else:
        # 如果是第一次設定，就新增一筆
        config = SystemConfig(
            key=key, 
            value=payload.value, 
            description="系統動態設定值"
        )
        session.add(config)
        
    await session.commit()
    return {"message": "設定更新成功", "key": key}


@router.post("/staff/{staff_id}/generate_bind_code")
async def generate_line_bind_code(staff_id: int, session: AsyncSession = Depends(get_session)):
    stmt = select(Staff).where(Staff.id == staff_id)
    staff = (await session.execute(stmt)).scalars().first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="找不到該員工")
        
    # 產生 6 位數隨機綁定碼 (全數字)
    bind_code = ''.join(random.choices(string.digits, k=6))
    
    staff.line_bind_code = bind_code
    await session.commit()
    
    return {
        "message": "綁定碼產生成功",
        "bind_code": bind_code,
        "instruction": f"請在電視台 LINE 官方帳號輸入：「綁定 {bind_code}」"
    }
