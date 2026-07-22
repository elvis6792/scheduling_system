from sqlmodel import select
from app.models.domain import Staff, Program, Shift
from agent.tools.base import BaseTool
from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date
from app.services.scheduling_service import SchedulingService
from app.services.exceptions import DoubleBookingError, StaffNotFoundError, ProgramNotFoundError

class BatchCreateShift(BaseTool):
    def __init__(self, db_session_maker):
        self.name = "batch_create_shift"
        self.description = "為指定員工在多個日期批次新增同一個節目的班表。⚠️ 核心指令：只要使用者一次提供【兩個以上的日期】（例如：下週一三五、7/20到7/22），請優先且唯一使用此工具，絕對禁止手動拆解成多次單日排班！"
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context) -> dict:
        staff_name = arguments.get("staff_name")
        program_name = arguments.get("program_name")
        date_strs = arguments.get("date", [])
        user_id = context.user_id

        if not all([staff_name, program_name, date_strs, user_id]):
            return {"status": "ERROR", "message": "缺少必要的參數 (員工、節目、日期、使用者ID)。"}

        async with self.db_session_maker() as session:
            try:
                # 1. 查詢 Staff 和 Program 的 ID
                staff_stmt = select(Staff).where(Staff.name == staff_name)
                staff = (await session.execute(staff_stmt)).scalar_one_or_none()
                if not staff:
                    raise StaffNotFoundError(f"找不到員工「{staff_name}」。")

                prog_stmt = select(Program).where(Program.name.like(f"%{program_name}%"))
                program = (await session.execute(prog_stmt)).scalars().first()
                if not program:
                    raise ProgramNotFoundError(f"找不到節目「{program_name}」。")

                # 2. 解析日期字串
                parsed_dates = [resolve_smart_date(d) for d in date_strs if d]
                if not parsed_dates:
                    return {"status": "ERROR", "message": "無法解析任何有效的日期。"}

                # 3. 呼叫底層服務
                service = SchedulingService(session)
                db_result = await service.batch_assign(
                    staff_id=staff.id,
                    program_id=program.id,
                    dates=parsed_dates,
                    user_id=user_id
                )

                # 4. 計算總工時 (這裡僅為範例，真實邏輯應更複雜)
                # 假設我們只計算本次新增的總時數
                total_hours = len(db_result.get("shifts", [])) * program.estimated_hours

                return {
                    "status": "SUCCESS",
                    "message": f"成功為 {staff_name} 排定 {db_result.get('created_count', 0)} 筆班表。本次新增總工時為 {total_hours:.1f} 小時。",
                    "data": {
                        "program_name": program.name,
                        "staff_name": staff.name,
                        "shifts": [s.id for s in db_result.get("shifts", [])]
                    }
                }
            except (StaffNotFoundError, ProgramNotFoundError, DoubleBookingError) as e:
                return {"status": "ERROR", "message": f"排班失敗：{str(e)}"}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"status": "FATAL", "message": f"系統發生未預期的錯誤：{str(e)}"}

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program_name": {
                            "type": "string",
                            "description": "要排班的節目名稱"
                        },
                        "staff_name": {
                            "type": "string",
                            "description": "要為其排班的員工姓名"
                        },
                        "date": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要新增班表的日期列表。⚠️ 注意：請絕對不要傳入『下週一』等相對詞彙！你必須自己推算日期，並將其全部轉換為 'YYYY-MM-DD' 的絕對格式再傳入此陣列！"
                        }
                    },
                    "required": ["program_name", "staff_name", "date"]
                }
            }
        }
