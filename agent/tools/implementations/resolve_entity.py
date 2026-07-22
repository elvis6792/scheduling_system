from typing import Any, Dict
from app.services.scheduling_service import SchedulingService
from agent.tools.base import BaseTool
from agent.runtime.state import ExecutionContext
from app.services.exceptions import AmbiguousEntityError, StaffNotFoundError, DoubleBookingError
from app.models.domain import Staff, Department

class EntityResolverTool(BaseTool):
    name: str = "resolve_entity"
    description: str = "【系統內部工具】在執行任務前，釐清使用者指令中的目標（例如「音效組」或「徐智淵」）到底是「部門」還是「員工」。此工具能處理模糊輸入，並在找到多個可能目標時回報，以利後續追問。"

    def __init__(self, async_session_maker):
        self.async_session_maker = async_session_maker

    async def execute(self, arguments: dict, context: ExecutionContext) -> Dict[str, Any]:
        target_name = arguments.get("target_name")
        if not target_name:
            return {"status": "ERROR", "message": "缺少 target_name 參數。"}

        async with self.async_session_maker() as session:
            service = SchedulingService(session)
            try:
                entity = await service.resolve_entity(target_name=target_name)
                
                if isinstance(entity, Department):
                    return {
                        "status": "SUCCESS",
                        "result": {
                            "entity_type": "department",
                            "id": entity.id,
                            "name": entity.name
                        }
                    }
                elif isinstance(entity, Staff):
                    return {
                        "status": "SUCCESS",
                        "result": {
                            "entity_type": "staff",
                            "id": entity.id,
                            "name": entity.name,
                            "department_id": entity.department_id
                        }
                    }
                else:
                    return {"status": "ERROR", "message": "未知的實體類型。"}

            except AmbiguousEntityError as e:
                names_str = "、".join([match["name"] for match in e.matches])
                return {
                    "status": "AMBIGUOUS_ENTITY",
                    "message": f"找到多位符合「{target_name}」的員工（{names_str}），請具體說明是哪一位？",
                    "options": e.matches
                }
            except StaffNotFoundError as e:
                return {
                    "status": "NOT_FOUND",
                    "message": str(e)
                }
            except Exception as e:
                return {
                    "status": "ERROR",
                    "message": f"解析實體時發生未知錯誤：{e}"
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
                        "target_name": {
                            "type": "string",
                            "description": "要解析的實體名稱，例如 '王大明' 或 '音效組'。",
                        },
                    },
                    "required": ["target_name"],
                },
            },
        }
