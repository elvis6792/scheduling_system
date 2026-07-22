from sqlalchemy.ext.asyncio import async_sessionmaker
from agent.runtime.state import ExecutionContext
from agent.runtime.validators import resolve_smart_date
from app.services.scheduling_service import SchedulingService
from ..base import BaseTool
import traceback


class CancelShiftTool(BaseTool):
    name = "cancel_shift"
    description = "取消排班紀錄。只需要提供日期與節目名稱，工具會自動進資料庫找出對應的班表並刪除。"

    def __init__(self, db_session_maker: async_sessionmaker):
        super().__init__()
        self.db_session_maker = db_session_maker

    async def execute(self, arguments: dict, context) -> dict:
        program_name = arguments.get("program_name")
        date_input = arguments.get("date") # 可能為字串或清單
        staff_name = arguments.get("staff_name")
        department_name = arguments.get("department")

        if not date_input:
            return {"status": "ERROR", "message": "缺少必要的參數：請提供日期。"}
            
        # 安全性檢查 - 只有系統管理員可以執行「全量註銷」
        # 如果沒有提供任何過濾條件（節目、員工、部門），則視為全量刪除
        if not program_name and not staff_name and not department_name:
            if context.role != "admin":
                return {
                    "status": "ERROR", 
                    "message": "權限不足：您目前的權限等級不允許執行「全量註銷」。若要刪除特定日期的所有班表，請聯絡系統管理員，或提供具體的節目名稱進行刪除。"
                }

        try:
            # 支援多日期解析
            if isinstance(date_input, list):
                target_dates = []
                for d in date_input:
                    parsed = resolve_smart_date(d)
                    if parsed:
                        target_dates.append(parsed)
                if not target_dates:
                    raise ValueError(f"無法解析日期清單中的任何日期: {date_input}")
            else:
                target_date = resolve_smart_date(date_input)
                if not target_date:
                    raise ValueError(f"無法解析日期: {date_input}")
                target_dates = [target_date]

            async with self.db_session_maker() as session:
                service = SchedulingService(session)
                
                # 1. 查詢要取消的班表 (支援多日期)
                shifts_to_cancel = await service.query_shifts(
                    staff_name=staff_name,
                    program_name=program_name,
                    department_name=department_name,
                    dates=target_dates
                )

                if not shifts_to_cancel:
                    return {
                        "status": "NOT_FOUND",
                        "message": "在指定條件下找不到任何可取消的班表。"
                    }

                # 安全性檢查：製作人只能刪除「由自己創建」的班表
                if context.role == "producer":
                    original_count = len(shifts_to_cancel)
                    shifts_to_cancel = [s for s in shifts_to_cancel if s.created_by_user_id == context.user_id]
                    
                    if not shifts_to_cancel:
                        return {
                            "status": "ERROR",
                            "message": f"權限不足：找到的 {original_count} 筆班表均非由您 (User ID: {context.user_id}) 排定，因此無法執行刪除。製作人僅能刪除自己親自排定的班表。"
                        }
                    elif len(shifts_to_cancel) < original_count:
                        print(f"[安全稽核] 製作人嘗試批量刪除，已自動過濾掉 {original_count - len(shifts_to_cancel)} 筆非本人排定的班表。")

                shift_ids = [shift.id for shift in shifts_to_cancel]
                
                # 暫存第一個要被刪除的班表資訊
                first_shift_details = None
                if shifts_to_cancel:
                    first_shift = shifts_to_cancel[0]
                    first_shift_details = {
                        "program_id": first_shift.program_id,
                        "program_name": first_shift.program.name if first_shift.program else None,
                        "staff_id": first_shift.staff_id,
                        "staff_name": first_shift.staff.name if first_shift.staff else None,
                        "date": first_shift.date.isoformat(),
                    }
                # ----------------------------------------------

                # 2. 執行取消
                deleted_count = await service.cancel_shifts(shift_ids=shift_ids)

            if deleted_count > 0:
                # 為了回傳訊息，組合一個易讀的目標名稱
                if staff_name:
                    target_desc = f"員工 {staff_name}"
                elif program_name:
                    target_desc = f"「{program_name}」節目"
                elif department_name:
                    target_desc = f"{department_name} 部門"
                else:
                    target_desc = "當日所有項目"

                date_desc = f"{len(target_dates)} 個日期" if len(target_dates) > 1 else str(target_dates[0])
                date_range_info = f"從 {target_dates[0]} 到 {target_dates[-1]}" if len(target_dates) > 1 else str(target_dates[0])
                
                return {
                    "status": "SUCCESS",
                    "message": f"操作成功：已將 {target_desc} 在 {date_range_info} 的 {deleted_count} 筆排班紀錄順利註銷。",
                    "data": {
                        **first_shift_details,
                        "deleted_count": deleted_count,
                        "date_range": date_range_info
                    }
                }
            else:
                return {
                    "status": "NOT_FOUND",
                    "message": "在資料庫中找不到對應的班表進行刪除，可能已被他人操作。",
                }
        except ValueError as e:
            return {"status": "ERROR", "message": str(e)}
        except Exception as e:
            traceback.print_exc()
            return {"status": "FATAL", "message": f"取消班表時發生未預期的嚴重錯誤：{str(e)}"}

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
                            "description": "節目名稱或簡稱，例如：人間菩提"
                        },
                        "date": {
                            "type": "string",
                            "description": "日期字串。請直接傳入使用者的口語（例如：今天、明天、後天），或是 YYYY-MM-DD 格式"
                        },
                        "staff_name": {
                            "type": "string",
                            "description": "【可選】指定要取消班表的員工姓名。若不提供，則會取消該節目在當天的所有班表。"
                        },
                        "department": {
                            "type": "string",
                            "description": "【可選】指定要取消班表的部門。若不提供，則會取消該節目在當天的所有班表。"
                        }
                    },
                    "required": ["program_name", "date"]
                }
            }
        }
