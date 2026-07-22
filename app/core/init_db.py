import asyncio
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.core.security import get_password_hash
from app.models.domain import User, Role, Department, Staff, Program, ChatHistory


async def init_db():

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        
        result = await session.execute(select(User).where(User.username == "admin"))
        existing_admin = result.scalar_one_or_none()
        
        if not existing_admin:
             print("[INFO] 偵測到全新資料庫，開始注入預設核心資料...")
             
             # 1. 建立部門
             dept1 = Department(name="燈光組")
             dept2 = Department(name="音效組")
             dept3 = Department(name="攝影組")
             dept4 = Department(name="動畫組")
             dept5 = Department(name="管理部")
             session.add_all([dept1, dept2, dept3, dept4, dept5])
             await session.flush()
             
             # 2. 建立員工實體
             admin_staff = Staff(name="系統管理員", department_id=dept5.id, daily_work_hours=8.0)
             staff1 = Staff(name="測試攝影師A", department_id=dept3.id, daily_work_hours=8.0)
             session.add_all([admin_staff, staff1])
             await session.flush()
             
             # 3. 建立登入帳號，並強制綁定剛剛建立的 staff_id
             admin = User(
                 username="admin",
                 hashed_password=get_password_hash("password123"),
                 role=Role.ADMIN,
                 staff_id=admin_staff.id  # 讓 admin 擁有實體身分
             )
             session.add(admin)
 
             # 4. 預設節目
             default_program = Program(
                 name="例行早安會議",
                 content="每日例行團隊技術交流與進度同步",
                 estimated_hours=2.0,
                 color="#3b82f6"
             )
             session.add(default_program)
             
             await session.commit()
             print("[SUCCESS] 預設資料與 admin 帳號注入成功！")
        else:
            print("[INFO] 資料庫已存在基礎資料，跳過注入步驟。")


if __name__ == "__main__":
    asyncio.run(init_db())
