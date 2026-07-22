import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

# 強制將專案根目錄 (seed_db.py 往上兩層) 設為絕對路徑的起點，並置於 sys.path 首位
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.domain import Staff, LeaveRecord

async def seed_database():
    print("[Seed] 開始執行資料庫播種作業...")
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    async with async_session_maker() as session:
        async with session.begin():
            # 1. 建立測試員工資料 (冪等操作)
            staff_data = [
                {"id": 101, "name": "測試員工A", "daily_work_hours": 8, "department_id": 1}, 
                {"id": 102, "name": "測試員工B", "daily_work_hours": 8, "department_id": 2}, 
                {"id": 103, "name": "測試員工C", "daily_work_hours": 8, "department_id": 3}
            ]
            
            for data in staff_data:
                stmt = select(Staff).where(Staff.id == data["id"])
                result = await session.execute(stmt)
                existing_staff = result.scalars().first()
                
                if not existing_staff:
                    new_staff = Staff(**data)
                    session.add(new_staff)
                    print(f"[Seed] 新增員工: {data['name']} (ID: {data['id']})")
                else:
                    print(f"[Seed] 員工已存在，跳過: {data['name']}")
                
    print("[Seed] 播種作業完成！")

if __name__ == "__main__":
    # 強制使用標準的 asyncio 事件迴圈執行
    asyncio.run(seed_database())
