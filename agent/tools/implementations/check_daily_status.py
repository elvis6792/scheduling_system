from sqlmodel import select
from app.models.domain import Staff
from ..base import BaseTool
from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date
from app.services.scheduling_service import SchedulingService
from app.services.scheduling_policy_engine import SchedulingPolicyEngine
from app.services.exceptions import StaffNotFoundError

class CheckDailyStatusTool(BaseTool):
    name = "check_daily_status"
    description = "【推薦使用】查詢指定員工在特定日期的『剩餘可用工時』。此工具會綜合計算每日工時上限、已排班與休假時數，最終回傳一個明確的剩餘時數，適合用來判斷『某人某天是否還有空檔可以排班』。"

    def __init__(self, db_session_maker):
        super().__init__()
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context) -> dict:
        staff_name = arguments.get('staff_name')
        date_str = arguments.get('date')

        if not staff_name or not date_str:
            return {"status": "ERROR", "message": "缺少員工姓名或日期參數。"}

        target_date = resolve_smart_date(date_str)
        if not target_date:
            return {"status": "ERROR", "message": f"無法解析的日期格式: {date_str}"}

        async with self.db_session_maker() as session:
            try:
                # 1. 查詢員工
                staff_stmt = select(Staff).where(Staff.name == staff_name)
                staff = (await session.execute(staff_stmt)).scalar_one_or_none()
                if not staff:
                    raise StaffNotFoundError(f"找不到員工「{staff_name}」。")

                # 2. 呼叫 Policy Engine 計算工時
                policy_engine = SchedulingPolicyEngine(session)
                # 傳入 0 代表我們只查詢現況，不預估新班表
                hour_details = await policy_engine.check_daily_hours(staff, target_date, new_shift_hours=0)

                daily_limit = hour_details["daily_limit"]
                used_hours = hour_details["scheduled_hours"] + hour_details["leave_hours"]
                remaining_hours = daily_limit - used_hours

                # 3. 組合給 AI 看的、資訊完整的 message
                message = (
                    f"查詢成功。員工 {staff_name} 在 {target_date.isoformat()} 的工時狀態如下：\n"
                    f"- 每日工時上限: {daily_limit:.1f} 小時\n"
                    f"- 已排班時數: {hour_details['scheduled_hours']:.1f} 小時\n"
                    f"- 已請假時數: {hour_details['leave_hours']:.1f} 小時\n"
                    f"- 總計已用時數: {used_hours:.1f} 小時\n"
                    f"- 剩餘可用工時: {remaining_hours:.1f} 小時"
                )

                # 4. 回傳包含數值資料的 Rich Payload
                return {
                    "status": "SUCCESS",
                    "message": message,
                    "data": {**arguments, **hour_details, "used_hours": used_hours, "remaining_hours": remaining_hours}
                }
            except StaffNotFoundError as e:
                return {"status": "ERROR", "message": str(e)}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"status": "FATAL", "message": f"查詢工時發生未預期的錯誤：{str(e)}"}

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
                            "description": "員工姓名"
                        },
                        "date": {
                            "type": "string",
                            "description": "目標查詢日期，可以是 '明天' 或 'YYYY-MM-DD' 格式"
                        }
                    },
                    "required": ["staff_name", "date"]
                }
            }
        }