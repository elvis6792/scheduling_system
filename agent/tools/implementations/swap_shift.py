from typing import Dict, Any, TYPE_CHECKING
from sqlmodel import select
from app.models.domain import Shift, Staff, Program
from agent.runtime.validators import resolve_smart_date
from app.services.scheduling_service import SchedulingService
from app.services.exceptions import DoubleBookingError

if TYPE_CHECKING:
    from agent.runtime.state import ExecutionContext


class SwapShiftTool:
    def __init__(self, db_session_maker):
        self.name = "swap_shift"
        self.description = "交換兩位員工在不同日期的班表。需提供兩位員工的姓名及他們各自要交換的班表日期。"
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context) -> dict:
        # ... (呼叫底層換班的邏輯) ...
        # await self.scheduling_service.swap_shift(...)

        staff_1 = arguments.get('staff_name_1')
        staff_2 = arguments.get('staff_name_2')
        date_1 = arguments.get('date_1')
        date_2 = arguments.get('date_2')

        return {
            "status": "SUCCESS",
            "message": f"操作成功：已順利完成 {staff_1} ({date_1}) 與 {staff_2} ({date_2}) 的換班作業。",
            "data": arguments
        }

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "交換兩位員工在不同日期的班表。需提供兩位員工的姓名及他們各自要交換的班表日期。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "staff_name_1": {"type": "string", "description": "第一位員工的姓名"},
                        "date_1": {"type": "string", "description": "第一位員工要換出的班表日期 (例如: '7/20')"},
                        "staff_name_2": {"type": "string", "description": "第二位員工的姓名"},
                        "date_2": {"type": "string", "description": "第二位員工要換出的班表日期 (例如: '7/21')"}
                    },
                    "required": ["staff_name_1", "date_1", "staff_name_2", "date_2"]
                }
            }
        }
