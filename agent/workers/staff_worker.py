from sqlalchemy.ext.asyncio import async_sessionmaker
from agent.persistence.repository import SchedulingRepository
from sqlmodel import select
from app.models.domain import Staff, Department

class StaffWorker:
    """無頭執行者：只管對資料庫下指令，不管 AI 怎麼想"""
    def __init__(self, db_session_maker: async_sessionmaker):
        self.db_session_maker = db_session_maker
    
    async def check_daily_status(self, **kwargs):
        """純粹的資料庫查詢邏輯"""
        department_name = kwargs.get("department")
        print(f"[Worker 執行中] LLM 傳來的搜尋條件: {department_name}")

        async with self.db_session_maker() as session:
            if department_name:
                stmt = select(Staff).join(Department).where(Department.name.like(f"%{department_name}%"))
            else:
                stmt = select(Staff)

            result = await session.execute(stmt)
            staff_list = result.scalars().all()

            if not staff_list:
                final_data = f"查無 {department_name or '任何'} 人員資料。"
                print(f"[Worker 準備回傳給大腦的資料]: {final_data}")
                return {"status": "success", "data": final_data}

            staff_names = [staff.name for staff in staff_list]

            final_data = f"目前可調度的真實人員有：{', '.join(staff_names)}"
            print(f"[Worker 準備回傳給大腦的資料]: {final_data}")
            
            return {"status": "success", "data": final_data}