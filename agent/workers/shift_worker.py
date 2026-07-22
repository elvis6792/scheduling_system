from typing import Dict, Any
from datetime import datetime
from agent.persistence.repository import SchedulingRepository
from sqlalchemy.ext.asyncio import async_sessionmaker

class ShiftWorker:
    def __init__(self, db_session_maker: async_sessionmaker):
        self.db_session_maker = db_session_maker

    async def create_shift(self, staff_id: int, date: str, program_id: int = 0) -> Dict[str, Any]:
        """執行真實的資料庫寫入作業"""
        async with self.db_session_maker() as session:
            repo = SchedulingRepository(session)
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            
            # 檢查員工是否存在
            staff = await repo.get_staff_by_id(staff_id)
            if not staff:
                raise ValueError(f"員工 ID {staff_id} 不存在系統中。")

            # 執行建立
            shift = await repo.create_shift(staff_id, target_date, program_id)
            
            await session.commit()
            
            return {
                "status": "success",
                "message": f"已成功建立員工 {staff.name} 於 {date} 的排班紀錄，排班 ID: {shift.id}"
            }

    async def cancel_shift(self, shift_id: int, reason: str = "") -> Dict[str, Any]:
        async with self.db_session_maker() as session:
            repo = SchedulingRepository(session)
            success = await repo.cancel_shift(shift_id)
            if success:
                await session.commit()
                return {"status": "success", "message": f"排班紀錄 {shift_id} 已成功取消。"}
            else:
                await session.rollback()
                raise ValueError(f"找不到指定的排班紀錄 ID: {shift_id}")