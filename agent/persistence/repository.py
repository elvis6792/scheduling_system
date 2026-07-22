from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Staff, Shift, LeaveRecord, ChatHistory

class SchedulingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_staff_by_id(self, staff_id: int) -> Optional[Staff]:
        return await self.session.get(Staff, staff_id)

    async def get_staff_by_name(self, name: str) -> Optional[Staff]:
        stmt = select(Staff).where(Staff.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_chat_message(self, user_id: int, role: str, content: str):
        msg = ChatHistory(user_id=user_id, role=role, content=content)
        self.session.add(msg)
        await self.session.commit()

    async def get_recent_chat_history(self, user_id: int, limit: int = 10):
        stmt = select(ChatHistory).where(ChatHistory.user_id == user_id).order_by(ChatHistory.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)
        msgs = result.scalars().all()
        # 回傳由舊到新的順序
        msgs_list = list(msgs)
        msgs_list.sort(key=lambda x: x.timestamp)
        return msgs_list

    async def clear_old_chat_history(self, days: int = 30):
        """刪除超過指定天數（預設 30 天，約一個月）的歷史紀錄"""
        cutoff = datetime.now() - timedelta(days=days)
        stmt = delete(ChatHistory).where(ChatHistory.timestamp < cutoff)
        await self.session.execute(stmt)
        await self.session.commit()

    async def check_leave_record(self, staff_id: int, target_date: date) -> bool:
        stmt = select(LeaveRecord).where(
            and_(
                LeaveRecord.staff_id == staff_id,
                LeaveRecord.date == target_date
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

    async def create_shift(self, staff_id: int, target_date: date, program_id: int) -> Shift:
        new_shift = Shift(
            staff_id=staff_id,
            date=target_date,
            program_id=program_id
        )
        self.session.add(new_shift)
        await self.session.flush()
        return new_shift

    async def cancel_shift(self, shift_id: int) -> bool:
        shift = await self.session.get(Shift, shift_id)
        if shift:
            await self.session.delete(shift)
            await self.session.flush()
            return True
        return False
