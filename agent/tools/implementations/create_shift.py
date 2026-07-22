import datetime
from typing import TYPE_CHECKING

from sqlmodel import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.runtime.validators import resolve_smart_date
from app.services.exceptions import ProgramNotFoundError, StaffNotFoundError, ShiftAssignmentError, DoubleBookingError
from app.services.scheduling_service import SchedulingService
from ..base import BaseTool

if TYPE_CHECKING:
    from agent.runtime.state import ExecutionContext


class CreateShiftTool(BaseTool):
    name = "create_shift"
    description = "建立排班紀錄，將特定節目指派給特定員工。具備強大的模糊名稱匹配能力，接受綽號或簡稱。"

    def __init__(self, db_session_maker: async_sessionmaker):
        super().__init__()
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context: "ExecutionContext") -> dict:
        staff_name = arguments.get('staff_name')
        program_name = arguments.get('program_name')
        date_str = arguments.get('date')
        user_id = context.user_id

        if not all([staff_name, program_name, date_str, user_id]):
            return {"status": "ERROR", "message": "缺少必要的參數 (員工姓名、節目名稱、日期) 或使用者資訊。"}

        try:
            target_date = resolve_smart_date(date_str)
            if not target_date:
                raise ValueError(f"無法解析的日期格式: {date_str}")

            async with self.db_session_maker() as session:
                # 將所有業務邏輯委派給 SchedulingService
                service = SchedulingService(session)
                new_shift = await service.assign_shift(
                    staff_name=staff_name,
                    program_name=program_name,
                    target_date=target_date,
                    user_id=user_id,
                    notes="由 AI 助理排班"
                )

                return {
                    "status": "SUCCESS",
                    "message": f"操作成功：已為 {new_shift.staff.name} 在 {target_date.isoformat()} 排入「{new_shift.program.name}」。新班表 ID 為 {new_shift.id}。",
                    "data": arguments
                }

        except (ProgramNotFoundError, StaffNotFoundError, ValueError, DoubleBookingError) as e:
            return {"status": "ERROR", "message": str(e)}
        except ShiftAssignmentError as e:
            return {"status": "ERROR", "message": f"排班失敗：{str(e)}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "FATAL", "message": f"執行排班時發生未預期的嚴重錯誤：{str(e)}"}

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "staff_name": {
                            "type": "string",
                            "description": "員工名稱或綽號，例如：徐智淵、小淵"
                        },
                        "program_name": {
                            "type": "string",
                            "description": "節目名稱或簡稱，例如：人間菩提、菩提"
                        },
                        "date": {
                            "type": "string",
                            "description": "日期字串。請直接傳入使用者的口語（例如：今天、明天、後天），或是 YYYY-MM-DD 格式"
                        }
                    },
                    "required": ["staff_name", "program_name", "date"]
                }
            }
        }