from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date
from app.services.scheduling_service import SchedulingService
from ..base import BaseTool


class QuerySchedule(BaseTool):
    def __init__(self, db_session_maker):
        self.name = "query_schedule"
        self.description = (
            "查詢班表，回傳用於後續操作的班表 ID (`shift_ids`)，以及一份詳細的結構化班表清單 (`data`)。 "
            "這是執行「取消」或「修改」等操作前的【第一步】。 "
            "⚠️ 絕對禁止：如果使用者詢問的是『剩餘工時』、『時數上限』、『是否還有空檔可以排班』，"
            "請絕對不要使用此工具，必須改用 `check_daily_status` 工具！"
        )
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context: ExecutionContext) -> dict:
        staff_name = arguments.get("staff_name")
        date_str = arguments.get("date")
        program_name = arguments.get("program_name")
        department = arguments.get("department")

        parsed_dates = []
        if date_str:
            dates_to_check = date_str if isinstance(date_str, list) else [date_str]
            resolved_dates = [resolve_smart_date(d) for d in dates_to_check if d]
            parsed_dates = [d for d in resolved_dates if d]

        async with self.db_session_maker() as session:
            service = SchedulingService(session)
            shifts_data = await service.query_shifts(
                staff_name=staff_name,
                program_name=program_name,
                department_name=department,
                dates=parsed_dates
            )

        # Transform shifts_data into a list of dictionaries as expected by the new logic
        processed_shifts = []
        if shifts_data:
            for shift in shifts_data:
                processed_shifts.append({
                    "shift_id": shift.id,
                    "date": shift.date.isoformat(),
                    "department": shift.department.name if shift.department else None,
                    "staff_name": shift.staff.name if shift.staff else None,
                    "program_name": shift.program.name if shift.program else None,
                    "time": f"{shift.start_time.strftime('%H:%M')}~{shift.end_time.strftime('%H:%M')}"
                })
        
        shifts = processed_shifts # Assign the processed shifts to the 'shifts' variable

        if not shifts:
            return {
                "status": "NOT_FOUND",
                "message": f"系統裡找不到 {arguments.get('staff_name', '')} 在指定日期的排班資料喔。",
                "data": arguments # 把原來的參數原封不動還回去，讓後續狀態機有資料可以報錯
            }

        # 1. 組合給 LLM 看的「白話文情報」
        details = []
        for s in shifts:
            # 兼容 dict 或 ORM 物件
            staff = s.get('staff_name', '未知') if isinstance(s, dict) else getattr(s, 'staff_name', '未知')
            prog = s.get('program_name', '未知節目') if isinstance(s, dict) else getattr(s, 'program_name', '未知節目')
            details.append(f"{staff}負責「{prog}」")
            
        shift_details = "、".join(details)
        
        # 把查詢的「對象」跟「日期」直接塞進句子裡，讓 LLM 知道這就是它要找的東西！
        target_name = arguments.get('department') or arguments.get('staff_name') or "指定目標"
        target_date = arguments.get('date', '指定日期')
        
        message = f"成功查到「{target_name}」在 {target_date} 的 {len(shifts)} 筆排班資料：{shift_details}。"

        # 2. 抽取第一筆資料作為黃金參數 (應付大部分單一排班的連鎖操作)
        first_shift = shifts[0]
        
        # 3. 回傳標準化 Rich Payload
        return {
            "status": "SUCCESS",
            "message": message,
            "data": {
                "shifts": shifts, # 保留完整陣列，應付未來可能需要的批次刪除邏輯
                
                # 強制把第一筆的黃金參數拉到最外層
                "program_name": first_shift.get("program_name"),
                "staff_name": first_shift.get("staff_name"),
                "department": first_shift.get("department"),
                "date": first_shift.get("date")
            }
        }

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
                            "description": "【可選】員工姓名"
                        },
                        "program_name": {
                            "type": "string",
                            "description": "【可選】節目名稱"
                        },
                        "department": {
                            "type": "string",
                            "description": "【可選】部門名稱"
                        },
                        "date": {
                            "type": "string",
                            "description": "【可選】日期，可以是 '明天' 或 'YYYY-MM-DD' 格式"
                        }
                    },
                    "required": []
                }
            }
        }