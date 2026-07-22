from datetime import date
from typing import List
from app.services.scheduling_service import SchedulingService
from app.services.exceptions import StaffNotFoundError
from agent.tools.base import BaseTool
from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date

class BatchCheckDailyStatus(BaseTool):
    name = "batch_check_daily_status"
    description = "【推薦使用】批量檢查某位員工在多個指定日期，加上『新班表』後，是否會超過每日工時上限。回傳詳細的衝突報告。"

    def __init__(self, db_session_maker):
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context) -> dict:
        staff_name = arguments.get('staff_name')
        dates = arguments.get('date', []) # 這裡拿到的是日期陣列

        # ... (你原本呼叫底層批次查詢的邏輯) ...
        # 假設你的 Service 回傳了這幾天的工時加總
        # total_hours = await self.scheduling_service.get_batch_hours(staff_name, dates)
        
        # 👇 這裡請替換成你真實的時數變數與判斷邏輯
        total_hours = 36 
        is_overtime = total_hours >= 40  # 假設法規一週上限為 40 小時

        if is_overtime:
             return {
                "status": "ERROR",
                "message": f"【超時警告】{staff_name} 在這 {len(dates)} 天的總預估工時將達到 {total_hours} 小時，已超出安全上限！",
                "data": arguments
            }

        return {
            "status": "SUCCESS",
            "message": f"批次工時檢查通過。{staff_name} 在這 {len(dates)} 天排班後，總工時預估為 {total_hours} 小時，狀態安全。",
            "data": arguments # 讓參數繼續傳遞
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
                            "description": "員工姓名"
                        },
                        "program_name": {
                            "type": "string",
                            "description": "預計要安排的節目名稱，用於估算新增的時數。"
                        },
                        "date": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "要檢查的日期列表，可為 '明天' 或 'YYYY-MM-DD' 格式"
                        }
                    },
                    "required": ["staff_name", "program_name", "date"]
                }
            }
        }
