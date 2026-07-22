from sqlalchemy.ext.asyncio import async_sessionmaker
from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date
from app.models.domain import Staff, LeaveRecord
from app.services.scheduler import validate_total_hours, DoubleBookingError
from sqlalchemy import select
from ..base import BaseTool
import traceback

class RegisterLeaveTool(BaseTool):
    name = "register_leave"
    description = "登錄員工休假（如特休、病假、事假等）。支援單一日期或日期清單。"

    def __init__(self, db_session_maker: async_sessionmaker):
        super().__init__()
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context: ExecutionContext) -> dict:
        staff_name = arguments.get("staff_name")
        date_input = arguments.get("date")
        leave_type = arguments.get("leave_type", "特休")
        hours = float(arguments.get("hours", 8.0))

        if not staff_name or not date_input:
            return {"status": "ERROR", "message": "缺少必要的參數：員工姓名與日期。"}

        try:
            # 統一轉為清單處理
            if isinstance(date_input, str):
                date_list = [date_input]
            elif isinstance(date_input, list):
                date_list = date_input
            else:
                date_list = [str(date_input)]

            target_dates = []
            for d in date_list:
                parsed = resolve_smart_date(d)
                if parsed:
                    target_dates.append(parsed)
            
            if not target_dates:
                return {"status": "ERROR", "message": f"無法解析任何有效的日期：{date_input}"}

            async with self.db_session_maker() as session:
                # 1. 查找員工
                staff_stmt = select(Staff).where(Staff.name == staff_name)
                staff_res = await session.execute(staff_stmt)
                staff = staff_res.scalars().first()
                if not staff:
                    return {"status": "ERROR", "message": f"找不到員工「{staff_name}」。"}

                results = []
                for target_date in target_dates:
                    # 2. 驗證總時數
                    try:
                        await validate_total_hours(
                            session=session,
                            staff_id=staff.id,
                            shift_date=target_date,
                            new_shift_hours=hours
                        )
                    except DoubleBookingError as e:
                        results.append(f"{target_date}: 衝突 ({str(e)})")
                        continue

                    # 3. 執行登錄
                    exist_stmt = select(LeaveRecord).where(
                        LeaveRecord.staff_id == staff.id, 
                        LeaveRecord.date == target_date
                    )
                    existing = (await session.execute(exist_stmt)).scalars().first()

                    if existing:
                        existing.leave_type = leave_type
                        existing.hours = hours
                    else:
                        new_leave = LeaveRecord(
                            staff_id=staff.id,
                            date=target_date,
                            leave_type=leave_type,
                            hours=hours
                        )
                        session.add(new_leave)
                    results.append(f"{target_date}: 成功")

                await session.commit()
                
                success_count = sum(1 for r in results if "成功" in r)
                msg = f"已為 {staff.name} 處理 {len(target_dates)} 筆休假登錄，其中 {success_count} 筆成功。"
                if success_count < len(target_dates):
                    msg += f" 失敗原因：{'; '.join([r for r in results if '成功' not in r])}"
                
                return {"status": "SUCCESS" if success_count > 0 else "ERROR", "message": msg, "data": arguments}

        except Exception as e:
            traceback.print_exc()
            return {"status": "FATAL", "message": f"執行休假登錄時發生嚴重錯誤：{str(e)}"}

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "staff_name": {"type": "string", "description": "員工姓名"},
                        "date": {"type": "string", "description": "日期或日期清單"},
                        "leave_type": {"type": "string", "description": "假別 (如：特休、事假)"},
                        "hours": {"type": "number", "description": "時數 (預設 8)"}
                    },
                    "required": ["staff_name", "date"]
                }
            }
        }
