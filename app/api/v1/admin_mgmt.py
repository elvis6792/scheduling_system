from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.domain import Department, Staff, Program, User, Shift, LeaveRecord, WorkHoursOverride
from app.models import schemas
from app.core.database import get_session
from app.core.security import get_password_hash
from app.core.dependencies import get_current_user, get_current_admin

router = APIRouter()


# ==========================================
# [職責標籤：組織架構配置介面]
# 管理公司部門維度，支援跨模組的層級關聯。
# ==========================================
@router.get("/departments", response_model=list[schemas.Department])
async def get_departments(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    result = await session.execute(select(Department))
    return result.scalars().all()

@router.post("/departments", response_model=schemas.Department, status_code=status.HTTP_201_CREATED)
async def create_department(dept: schemas.DepartmentCreate, session: AsyncSession = Depends(get_session), admin: User = Depends(get_current_admin)):
    existing = await session.execute(select(Department).where(Department.name == dept.name))
    if existing.scalar_one_or_none(): raise HTTPException(status_code=400, detail="部門名稱已存在")
    new_dept = Department(name=dept.name); session.add(new_dept); await session.commit(); await session.refresh(new_dept)
    return new_dept

@router.delete("/departments/{dept_id}")
async def delete_department(dept_id: int, session: AsyncSession = Depends(get_session), admin: User = Depends(get_current_admin)):
    dept = await session.get(Department, dept_id)
    if not dept: raise HTTPException(status_code=404, detail="找不到該部門")
    
    # 顯式刪除關聯資料
    await session.execute(delete(Staff).where(Staff.department_id == dept_id))
    await session.execute(delete(Shift).where(Shift.department_id == dept_id))

    await session.delete(dept); await session.commit()
    return {"message": "部門已刪除"}


# ==========================================
# [職責標籤：人力資源配置介面]
# 維護員工基礎資料 (Staff)，並處理其與登入帳號 (User) 的生命週期綁定。
# ==========================================
@router.get("/staff")
async def get_all_staff(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Staff)
    
    # 只有 staff 需要被限制，admin 與 producer 暢通無阻
    if current_user.role == "staff":
        if current_user.department_id:
            stmt = stmt.where(Staff.department_id == int(current_user.department_id))
        else:
            stmt = stmt.where(Staff.department_id == -1)
            
    results = (await session.execute(stmt)).scalars().all()
    return results

class StaffWithUserCreate(schemas.StaffBase):
    username: str
    password: str
    role: str

@router.post("/staff")
async def create_staff_with_user(
    data: StaffWithUserCreate, 
    session: AsyncSession = Depends(get_session)
):
    # 檢查帳號是否重複
    exist_user = (await session.execute(select(User).where(User.username == data.username))).scalars().first()
    if exist_user:
        raise HTTPException(status_code=400, detail="此登入帳號已被使用，請換一個")

    # 建立人員 (Staff) 實體
    new_staff = Staff(name=data.name, department_id=data.department_id, daily_work_hours=data.daily_work_hours)
    session.add(new_staff)
    await session.flush() # 刷新以獲取 new_staff.id

    # 建立使用者 (User) 實體，並綁定 Staff 與角色
    new_user = User(
        username=data.username,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        staff_id=new_staff.id
    )
    session.add(new_user)
    await session.commit()
    
    return {"message": "人員與帳號同步建立成功"}

@router.delete("/staff/{staff_id}", dependencies=[Depends(get_current_admin)])
async def delete_staff(staff_id: int, session: AsyncSession = Depends(get_session)):
    staff = await session.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="找不到該名人員")
        
    try:
        # 1. 顯式刪除所有關聯資料 (避免 SQLite 外鍵約束衝突)
        await session.execute(delete(Shift).where(Shift.staff_id == staff_id))
        await session.execute(delete(LeaveRecord).where(LeaveRecord.staff_id == staff_id))
        await session.execute(delete(WorkHoursOverride).where(WorkHoursOverride.staff_id == staff_id))
        
        # 2. 找出綁定的帳號並刪除
        user_stmt = select(User).where(User.staff_id == staff_id)
        user = (await session.execute(user_stmt)).scalars().first()
        if user:
            await session.delete(user)
            
        # 3. 刪除人員實體
        await session.delete(staff)
        await session.commit()
        return {"message": "人員及其帳號與排班紀錄已同步註銷"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"刪除失敗：{str(e)}")

@router.put("/staff/{staff_id}", response_model=schemas.Staff, dependencies=[Depends(get_current_admin)])
async def update_staff(
    staff_id: int,
    staff_update: schemas.StaffUpdate,
    session: AsyncSession = Depends(get_session)
):
    db_staff = await session.get(Staff, staff_id)
    if not db_staff:
        raise HTTPException(status_code=404, detail="找不到該名人員")
    
    update_data = staff_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_staff, key, value)
    
    session.add(db_staff)
    await session.commit()
    await session.refresh(db_staff)
    return db_staff


# ==========================================
# [職責標籤：製作任務配置介面]
# 定義排班系統中的任務實體 (Program)，包含製作內容、估算工時與識別色。
# ==========================================
@router.get("/programs", response_model=list[schemas.Program])
async def get_programs(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    res = await session.execute(select(Program))
    return res.scalars().all()

@router.post("/programs", response_model=schemas.Program)
async def create_program(prog: schemas.ProgramCreate, session: AsyncSession = Depends(get_session), admin: User = Depends(get_current_admin)):
    new_prog = Program.model_validate(prog)
    try:
        session.add(new_prog)
        await session.commit()
        await session.refresh(new_prog)
        return new_prog
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail=f"新增失敗：名為「{new_prog.name}」的節目已存在，請使用其他名稱。"
        )

@router.delete("/programs/{program_id}")
async def delete_program(program_id: int, session: AsyncSession = Depends(get_session), admin: User = Depends(get_current_admin)):
    prog = await session.get(Program, program_id)
    if not prog: raise HTTPException(status_code=404, detail="找不到該節目")
    
    # 顯式刪除關聯班表
    await session.execute(delete(Shift).where(Shift.program_id == program_id))

    await session.delete(prog); await session.commit()
    return {"message": "節目已刪除"}


# ==========================================
# [職責標籤：系統訪問安全性介面]
# 提供管理員維護登入帳號 (User) 的通道，包含密碼雜湊轉換與預設帳號保護邏輯。
# ==========================================
@router.get("/users")
async def get_users(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    res = await session.execute(select(User))
    return [{"id": u.id, "username": u.username, "role": u.role} for u in res.scalars().all()]

@router.post("/users")
async def create_user(user: schemas.UserCreate, session: AsyncSession = Depends(get_session), admin: User = Depends(get_current_admin)):
    existing = await session.execute(select(User).where(User.username == user.username))
    if existing.scalar_one_or_none(): raise HTTPException(status_code=400, detail="帳號名稱已存在")
    new_user = User(username=user.username, hashed_password=get_password_hash(user.password), role=user.role)
    session.add(new_user); await session.commit()
    return {"message": "帳號建立成功"}

@router.delete("/users/{user_id}", dependencies=[Depends(get_current_admin)])
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="找不到該帳號")
        
    if user.username == "admin":
        raise HTTPException(status_code=403, detail="預設系統管理員帳號不可刪除")

    # 找出綁定的人員並刪除
    if user.staff_id:
        staff = await session.get(Staff, user.staff_id)
        if staff:
            await session.delete(staff)
            
    await session.delete(user)
    await session.commit()
    return {"message": "帳號及其綁定人員已同步註銷"}
