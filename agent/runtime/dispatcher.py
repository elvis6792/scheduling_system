from typing import Dict, Any
from .state import ToolStep, RecoveryReason
from ..workers.exceptions import WorkerError
from ..models.observation import RichObservation
import traceback
import time

class Dispatcher:
    def __init__(self):
        # 註冊所有可用的 Workers
        self.workers: Dict[str, Any] = {}
        
    def register_worker(self, name: str, worker_instance: Any):
        self.workers[name] = worker_instance

    async def dispatch(self, step: ToolStep) -> RichObservation:
        """
        接收 ToolStep，找到對應的 Worker，執行並將結果封裝成 RichObservation
        """
        start_time = time.time()
        tool_name = step.tool_name
        args = step.arguments
        
        try:
            # 核心路由表
            if tool_name == "cancel_shift":
                worker = self.workers.get("shift_worker")
                result_data = await worker.cancel_shift(
                    shift_id=args.get("shift_id"), 
                    reason=args.get("reason", "未提供原因")
                )
                summary = "排班取消成功。"
                
            elif tool_name == "create_shift":
                worker = self.workers.get("shift_worker")
                result_data = await worker.create_shift(**args)
                summary = "排班建立成功。"
                
            elif tool_name == "check_daily_status":
                worker = self.workers.get("staff_worker")
                result_data = await worker.check_daily_status(**args)
                summary = f"查詢成功，找到員工資料。"
                
            else:
                raise ValueError(f"Dispatcher 無法路由未知的工具: {tool_name}")

            # 執行成功，組裝全景觀測資料
            latency = (time.time() - start_time) * 1000
            return RichObservation(
                tool_name=tool_name,
                status="SUCCESS",
                summary=summary,
                latency_ms=latency,
                raw_data=result_data
            )

        except WorkerError as e:
            # 攔截 Worker 拋出的業務錯誤
            latency = (time.time() - start_time) * 1000
            return RichObservation(
                tool_name=tool_name,
                status="ERROR",
                summary=e.message,
                error_code=e.reason.value,
                latency_ms=latency
            )
        except Exception as e:
            # 攔截不可預期的系統崩潰
            print(f"工具執行崩潰: {e}")
            traceback.print_exc()
            
            latency = (time.time() - start_time) * 1000
            return RichObservation(
                tool_name=tool_name,
                status="FATAL",
                summary=f"系統底層錯誤: {str(e)}",
                error_code="SYSTEM_CRASH",
                latency_ms=latency
            )