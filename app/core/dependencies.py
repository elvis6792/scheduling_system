import json
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import SECRET_KEY, ALGORITHM
from app.core.database import get_session
from app.models.domain import User, Role, SchedulingWindow, Staff
from app.services.excel_parser import ExcelParser


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class CurrentUser(User):
    """
    一個擴充過的 User 模型，用於在 Request 生命週期中攜帶額外的上下文資訊，例如部門。
    這樣就不需要到處去 join staff 表。
    """
    department_id: Optional[int] = None
    name: Optional[str] = None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登入憑證無效或已過期，請重新登入",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await session.execute(select(User).where(User.username == username))
    user_from_db = result.scalar_one_or_none()
    if user_from_db is None:
        raise credentials_exception

    # 將資料庫取出的 User 物件轉換為字典
    current_user_data = user_from_db.model_dump()
    
    # 預設值
    current_user_data["department_id"] = None
    current_user_data["name"] = user_from_db.username

    # 如果 user 有綁定 staff, 就去 staff 表撈出更多資訊
    if user_from_db.staff_id:
        staff_record = await session.get(Staff, user_from_db.staff_id)
        if staff_record:
            current_user_data["department_id"] = staff_record.department_id
            current_user_data["name"] = staff_record.name

    # 用合併後的資訊建立 CurrentUser 物件
    return CurrentUser(**current_user_data)


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：此操作僅限「系統管理員」執行！"
        )
    return current_user


async def get_current_producer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [Role.PRODUCER, Role.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：此操作僅限「排班製作人」執行！"
        )
    return current_user


def get_excel_parser() -> ExcelParser:
    return ExcelParser()


async def check_date_against_scheduling_windows(target_date: datetime.date, session: AsyncSession):
    tz = ZoneInfo("Asia/Taipei")
    today = datetime.now(tz).date()

    if target_date < today:
        return

    stmt = select(SchedulingWindow).where(SchedulingWindow.is_active == True)
    active_windows = (await session.execute(stmt)).scalars().all()

    for window in active_windows:
        if window.start_date <= target_date <= window.end_date:
            return  # Valid date, exit function
    if active_windows:
        available_windows_str = "、".join(
            [f"{w.start_date.strftime('%Y-%m-%d')} to {w.end_date.strftime('%Y-%m-%d')}" for w in active_windows]
        )
        detail_msg = (
            f"Permission denied: Scheduling for date {target_date} is not approved. "
            f"The system is currently open for scheduling only during specific periods, and your requested date is outside of the approved ranges. "
            f"Currently approved periods are: {available_windows_str}."
        )
    else:
        detail_msg = (
            f"Permission denied: Cannot process scheduling for date {target_date}. "
            f"There are currently no active scheduling periods defined in the system. "
            f"Please contact an administrator to confirm and set up scheduling windows."
        )

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_msg)


async def verify_scheduling_window(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    target_date_str = None
    if "date" in request.query_params:
        target_date_str = request.query_params["date"]
    else:
        try:
            body = await request.json()
            if "date" in body:
                target_date_str = body.get("date")
        except Exception:
            pass

    if not target_date_str:
        return

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: '{target_date_str}'. Please use YYYY-MM-DD."
        )

    await check_date_against_scheduling_windows(target_date, session)
