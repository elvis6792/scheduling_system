import json
import time
import re
from typing import Callable, AsyncContextManager, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .state import AgentState, ExecutionContext, RecoveryReason
import datetime

import calendar

def extract_golden_params(data) -> dict:
    """
    通用黃金參數過濾器：遞迴掃描任何工具的回傳值，只提煉系統關心的核心業務欄位。
    相容所有工具的嵌套結構（List, Dict, 或特定的 Wrapper）。
    """
    golden_keys = {"program_name", "staff_name", "department", "date", "staff_id", "department_id"}
    extracted = {}
    
    if isinstance(data, dict):
        # 1. 如果有常見的資料容器，優先往深處挖
        for container in ["shifts", "shifts_data", "data", "result"]:
            if container in data and isinstance(data[container], (list, dict)):
                return extract_golden_params(data[container])
        
        # 2. 展平目前層級的字典，只挑選黃金參數
        for k, v in data.items():
            if k in golden_keys and v:
                extracted[k] = v
                
    elif isinstance(data, list) and len(data) > 0:
        # 如果是陣列，通常第一筆資料最具代表性（例如最新查到的那筆班表）
        return extract_golden_params(data[0])
        
    return extracted


def expand_fuzzy_dates(date_arg) -> list:
    """
    將模糊日期（如 2024-05 或 七月）展開為該月的所有日期列表。
    """
    if isinstance(date_arg, list):
        return date_arg
        
    d_str = str(date_arg).strip()
    today = datetime.date.today()
    
    # 1. 處理 YYYY-MM 格式 (由 LLM 產出，代表整個月)
    month_match = re.match(r"^(\d{4})-(\d{2})$", d_str)
    if month_match:
        year, month = int(month_match.group(1)), int(month_match.group(2))
        _, last_day = calendar.monthrange(year, month)
        return [datetime.date(year, month, day).strftime("%Y-%m-%d") for day in range(1, last_day + 1)]

    # 2. 處理「X月」或「X月份」
    cn_to_num = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
    digit_month_match = re.search(r"(\d{1,2}|[一二三四五六七八九十]{1,2})\s*月", d_str)
    if digit_month_match:
        m_raw = digit_month_match.group(1)
        target_month = int(m_raw) if m_raw.isdigit() else cn_to_num.get(m_raw)
        if target_month:
            year = today.year
            _, last_day = calendar.monthrange(year, target_month)
            return [datetime.date(year, target_month, day).strftime("%Y-%m-%d") for day in range(1, last_day + 1)]

    # 3. 保留對極少數特殊詞的支援 (防禦性)
    if d_str == "今年":
        return [datetime.date(today.year, m, d).strftime("%Y-%m-%d") 
                for m in range(1, 13) 
                for d in range(1, calendar.monthrange(today.year, m)[1] + 1)]
    
    # 4. 如果是標準日期或無法識別，直接回傳
    return [d_str]

from agent.utils.date_utils import resolve_colloquial_date

from .recovery import RecoveryEngine
from .dispatcher import Dispatcher
from .loop_detector import LoopDetector
from .memory import MemoryManager
from .planner import Planner, ExecutionPlan, ToolStep
from ..models.observation import RichObservation
from .validators import InputValidator, BusinessValidator, ValidationError, global_time_interceptor
from ..tools.registry import ToolRegistry

from agent.router.skills_registry import SkillName, SKILL_WORKFLOWS
from agent.router.skill_router import SemanticSkillRouter


# 放寬每張卡片的「絕對必填欄位」，讓 Agent 有機會自己去查
REQUIRED_SLOTS = {
    # 把 program_name 拿掉，讓意圖可以順利進入 PLAN 階段
    SkillName.AssignProgramStaff: ["staff_name", "date"],
    SkillName.CancelProgramShift: ["date"],
    SkillName.BatchAssign: ["program_name", "staff_name", "date"],
}

# 用來把英文欄位翻譯給使用者聽的對照表
SLOT_TRANSLATION = {
    "program_name": "節目名稱",
    "staff_name": "員工姓名",
    "date": "日期",
    "department": "部門",
    "staff_1": "第一位員工",
    "staff_2": "第二位員工"
}


class AgentRuntime:
    def __init__(
        self,
        planner: Planner,
        tool_registry: ToolRegistry,
        dispatcher: Dispatcher,
        memory_manager: MemoryManager,
        input_validator: InputValidator,
        business_validator: BusinessValidator,
        recovery_engine: RecoveryEngine,
    ):
        self.loop_detector = LoopDetector()
        self.memory_manager = memory_manager
        self.planner = planner
        self.input_validator = input_validator
        self.business_validator = business_validator
        self.tool_registry = tool_registry
        self.dispatcher = dispatcher
        self.recovery_engine = recovery_engine
        self.last_action_memory = None

        self.llm = self.planner.llm # 注入 LLM Client 以便生成最終回覆
        self.router = SemanticSkillRouter(self.llm)

    async def _resolve_entities_for_intents(self, intents: list, context: ExecutionContext) -> list:
        """
        在規劃前對意圖中的實體進行解析。
        使用 resolve_entity 工具來釐清 'staff_name' 或 'target_entity' 是員工還是部門。
        """
        # A set of skills that require entity resolution for their target.
        SKILLS_REQUIRING_RESOLUTION = {
            SkillName.AssignProgramStaff,
            SkillName.CancelProgramShift,
            SkillName.QuerySchedule,
            SkillName.RegisterLeave,
        }

        resolver_tool = self.tool_registry.get_tool("resolve_entity")

        for intent in intents:
            if intent.skill_name not in SKILLS_REQUIRING_RESOLUTION:
                continue

            args = intent.extracted_arguments
            # The router might extract 'staff_name', 'department', or a generic 'target_entity'.
            # We prioritize resolving a generic target, then fall back to 'staff_name'.
            target_name = args.get("target_entity") or args.get("staff_name")

            # 代名詞「我」、「你」、「本人」、「自己」、「使用者」的直接解析 (無需調用資料庫，直接從 context 抓取)
            if target_name in ["我", "你", "本人", "自己", "使用者"] and context.staff_id:
                args["staff_name"] = context.user_name
                args.pop("target_entity", None)
                continue

            # If no target is found, or if 'department' is already specified, we can skip.
            if not target_name or args.get("department"):
                continue
            
            # Call the resolver tool directly
            resolution_result = await resolver_tool.execute({"target_name": target_name}, context)
            status = resolution_result.get("status")
            
            if status == "SUCCESS":
                resolved = resolution_result["result"]
                entity_type = resolved.get("entity_type")

                # Remove the original ambiguous argument
                args.pop("target_entity", None)
                args.pop("staff_name", None)

                # Add the new, specific arguments
                if entity_type == "department":
                    args["department"] = resolved["name"]
                    # We can also add department_id for more precise queries later
                    args["department_id"] = resolved["id"]
                elif entity_type == "staff":
                    args["staff_name"] = resolved["name"]
                    args["staff_id"] = resolved["id"]
            
            elif status in ["AMBIGUOUS_ENTITY", "NOT_FOUND"]:
                # 改用 Python 內建的 ValueError，並使用 .get() 確保安全
                raise ValueError(resolution_result.get("message", "查無此目標或有多筆相符資料，請提供更詳細的名稱。"))
            
            elif status == "ERROR":
                # For internal tool errors, raise a more generic error.
                raise Exception(f"實體解析工具發生內部錯誤: {resolution_result.get('message')}")

        return intents

    async def run(self, context: ExecutionContext, pending_context: Dict[str, Any] = None, unprocessed_intents_queue: list = [], system_context: dict = None) -> Tuple[str, Dict[str, Any] | None, list]:
        """
        狀態機主迴圈。支援中斷 (ASK_USER) 與重啟。
        如果狀態是 ASK_USER 被傳進來，代表使用者已經回答了，我們將根據回覆繼續或中止。
        """
        # 更嚴謹的 ASK_USER 中斷恢復機制
        if context.state == AgentState.ASK_USER:
            user_msg = context.user_input.strip()
            
            # 若是在等待確認危險操作
            if context.current_plan and context.current_plan.steps:
                if any(kw in user_msg for kw in ["確認", "好", "yes", "確定", "ok"]):
                    # 標記當前步驟已授權，並直接跳至分發階段
                    context.current_plan.steps[context.current_plan.current_step_index].is_confirmed = True
                    context.state = AgentState.DISPATCH
                elif any(kw in user_msg for kw in ["取消", "不要", "no", "拒絕"]):
                    context.state = AgentState.DONE
                    context.current_plan = None # 清空計畫
                    return "好的，已為您取消該操作。", None, [] # 清空 pending_context 和 queue
                else:
                    # 遇到 Context Switch (切換話題)，直接中斷舊計畫，重啟新任務
                    context.current_plan = None # 清空計畫
                    context.state = AgentState.UNDERSTAND
            else:
                # 若是缺少參數等一般詢問，直接進入意圖解析重新規劃
                context.state = AgentState.UNDERSTAND
        elif context.state == AgentState.IDLE:
            context.state = AgentState.UNDERSTAND

        max_ticks = 100
        ticks = 0

        router_result = None

        while context.state != AgentState.DONE and ticks < max_ticks:
            ticks += 1
            
            if ticks >= 100:
                print(f"[Runtime] 觸發安全機制：執行步驟過長 (已達 {ticks} 步上限)，強制終止並清理狀態。")
                context.state = AgentState.DONE
                context.current_plan = None
                return "系統安全機制觸發：任務已強制終止，請重新發起請求。", None, []
            
            # 1. 狀態：UNDERSTAND (意圖解析)
            if context.state == AgentState.UNDERSTAND:
                router_result = await self.router.route_intent(context.user_input, pending_context=pending_context, system_context=system_context)

                # 參數對齊器：將 LLM 可能輸出的同義 Key 對齊到系統內部名稱
                for intent in router_result.intents:
                    args = intent.extracted_arguments
                    if "date_range" in args and "date" not in args:
                        args["date"] = args.pop("date_range")
                    if "time" in args and "date" not in args:
                        args["date"] = args.pop("time")
                    if "target_staff" in args and "staff_name" not in args:
                        args["staff_name"] = args.pop("target_staff")

                self.validated_intents = [] 
                
                for intent in router_result.intents:
                    if intent.skill_name not in SKILL_WORKFLOWS and intent.skill_name != SkillName.UndoLastAction:
                        continue
                        
                    if intent.skill_name == SkillName.Unknown:
                        continue
                    
                    self.validated_intents.append(intent)

                try:
                    self.validated_intents = await self._resolve_entities_for_intents(self.validated_intents, context)
                except ValueError as e:  # 將 ValidationError 改成 ValueError
                    # 實體解析失敗 (e.g. 找不到, 或有多個選項)
                    context.state = AgentState.DONE
                    # 直接將解析工具回傳的清晰錯誤訊息回傳給使用者
                    return str(e), None, []

                for intent in self.validated_intents:
                    required_keys = REQUIRED_SLOTS.get(intent.skill_name, [])
                    missing_keys = [k for k in required_keys if k not in intent.extracted_arguments or not intent.extracted_arguments[k]]
                    
                    if missing_keys:
                        pending_context = {
                            "skill_name": intent.skill_name,
                            "extracted_arguments": intent.extracted_arguments
                        }
                        missing_tw = [SLOT_TRANSLATION.get(k, k) for k in missing_keys]
                        context.state = AgentState.DONE
                        return f"還缺少「{'、'.join(missing_tw)}」，請問詳細資訊為何？", pending_context, unprocessed_intents_queue

                if not self.validated_intents:
                    # 如果沒有任何可執行的意圖，啟動「通用問答模式」
                    
                    # 提取最近的對話歷史
                    history_text = "\n".join([
                        f"{'使用者' if obs.get('role') == 'user' else '你'}: {obs.get('content')}"
                        for obs in self.memory_manager.build_full_turn_history(context)
                    ])

                    fallback_prompt = (
                        f"【對話歷史】\n{history_text}\n\n"
                        f"【最新問題】\n使用者: {context.user_input}\n\n"
                        f"【你的任務】你是一個專業的排班助理，請根據上面的對話歷史，用自然、口語化的繁體中文（台灣）回答使用者的最新問題。如果問題與排班無關，可以禮貌地表示無法回答。"
                    )
                    fallback_reply = await self.llm.generate_text(fallback_prompt, context.user_input)
                    context.state = AgentState.DONE
                    return fallback_reply, None, []

                pending_context = None
                context.state = AgentState.PLAN

            # 2. 狀態：PLAN (排定計畫)
            elif context.state == AgentState.PLAN:
                
                plan_steps_list = []
                combined_goal = "" 
                
                for intent in self.validated_intents:
                    # 在印出 Log 和進入 PLAN 前，強制洗掉所有口語時間
                    try:
                        if intent.extracted_arguments:
                            intent.extracted_arguments = global_time_interceptor(intent.extracted_arguments)
                    except ValueError as e:
                        # 如果 dateparser 都看不懂，直接退回給使用者，不進入後續流程
                        context.state = AgentState.DONE
                        return f"時間解析失敗，已攔截。原因：{str(e)}", None, []

                    if intent.skill_name == SkillName.UndoLastAction:
                        if not self.last_action_memory:
                            context.state = AgentState.DONE
                            return "抱歉，我沒有找到上一個可以復原的動作紀錄喔。", None, []
                        
                        last_skill = self.last_action_memory["skill_name"]
                        last_args = self.last_action_memory["extracted_arguments"]
                        
                        if last_skill == SkillName.AssignProgramStaff:
                            plan_steps_list.append(ToolStep(tool_name="cancel_shift", arguments=last_args))
                            print(f"[反轉引擎啟動]: 將 Assign 轉換為 Cancel")
                            
                        elif last_skill == SkillName.CancelProgramShift:
                            plan_steps_list.append(ToolStep(tool_name="check_daily_status", arguments=last_args))
                            plan_steps_list.append(ToolStep(tool_name="create_shift", arguments=last_args))
                            print(f"[反轉引擎啟動]: 將 Cancel 轉換為 Assign")
                        
                        self.last_action_memory = None
                        continue

                    raw_date = intent.extracted_arguments.get("date", [])
                    expanded_dates = expand_fuzzy_dates(raw_date)
                    combined_goal += intent.reasoning + "; "

                    if len(expanded_dates) > 1 or intent.skill_name == SkillName.BatchAssign:
                        # 只有在排班意圖下才強制使用 batch_create_shift
                        # 若是取消或查詢等意圖，應將展開後的日期清單塞回原參數，讓後續對應工具處理
                        if intent.skill_name in [SkillName.AssignProgramStaff, SkillName.BatchAssign]:
                            plan_steps_list.append(ToolStep(
                                tool_name="batch_create_shift",
                                arguments={
                                    "staff_name": intent.extracted_arguments.get("staff_name"),
                                    "program_name": intent.extracted_arguments.get("program_name"),
                                    "date": expanded_dates
                                }
                            ))
                            continue
                        else:
                            # 針對取消或其他意圖，將 date 參數改為日期清單
                            intent.extracted_arguments["date"] = expanded_dates
                    elif expanded_dates:
                        # 只有在非列表的情況下，才進行單一日期解析
                        intent.extracted_arguments["date"] = resolve_colloquial_date(expanded_dates[0])

                    # 根據意圖與參數，動態決定工具流程
                    if intent.skill_name == SkillName.CancelProgramShift:
                        # 如果取消指令中「沒有」提供具體的員工姓名，代表是範圍刪除
                        # 此時應跳過 query_schedule，直接讓 cancel_shift 處理
                        if "staff_name" not in intent.extracted_arguments or not intent.extracted_arguments["staff_name"]:
                            print("[智慧排程] 偵測到範圍註銷指令，跳過查詢步驟，直接執行 cancel_shift。")
                            plan_steps_list.append(ToolStep(tool_name="cancel_shift", arguments=intent.extracted_arguments))
                        else:
                            # 如果有提供員工姓名，則維持先查後刪的標準安全流程
                            for tool_name in SKILL_WORKFLOWS[intent.skill_name]:
                                plan_steps_list.append(ToolStep(tool_name=tool_name, arguments=intent.extracted_arguments))
                    else:
                        # 其他所有技能，維持原有的靜態工作流
                        required_tools = SKILL_WORKFLOWS.get(intent.skill_name, [])
                        for tool_name in required_tools:
                            plan_steps_list.append(ToolStep(
                                tool_name=tool_name,
                                arguments=intent.extracted_arguments
                            ))

                context.current_plan = ExecutionPlan(
                    intent="Multi-step execution", # 給定一個總稱
                    goal=combined_goal,
                    steps=plan_steps_list,
                    current_step_index=0
                )
                
                context.state = AgentState.VALIDATE
                
            elif context.state == AgentState.VALIDATE:
                current_step = context.current_plan.steps[context.current_plan.current_step_index]
                
                try:
                    self.input_validator.validate(current_step, context)
                    await self.business_validator.validate(current_step, context)
    
                    try:
                        tool_instance = self.tool_registry.get_tool(current_step.tool_name)
                    except ValueError as e:
                        error_msg = f"Agent 試圖呼叫不存在的工具: {current_step.tool_name}" # type: ignore
                        return error_msg, None, []
                        
                    context.state = AgentState.DISPATCH
                except Exception as e:
                    error_msg = str(e)

                    # 1. 攔截業務邏輯與參數錯誤，不進入盲目的自癒重試
                    # 補上 "超時", "上限", "超過"、"權限不足" 等關鍵字
                    business_errors = ["時數驗證失敗", "找不到", "AMBIGUOUS_ENTITY", "格式錯誤", "業務衝突", "超時", "超過", "上限", "權限不足"]
                    if any(err in error_msg for err in business_errors):
                        
                        # 2. 清理系統前綴字眼，讓對話更乾淨
                        clean_msg = error_msg.replace("AMBIGUOUS_ENTITY: ", "").replace("業務衝突：", "")
                        
                        # 3. 注入到 Observation 讓 LLM 組織語言，而不是直接回傳死板的字串
                        observation = RichObservation(
                            tool_name=current_step.tool_name,
                            status="ERROR",
                            summary=f"業務邏輯攔截: {clean_msg}",
                            latency_ms=0,
                            raw_data={"error": clean_msg}
                        )
                        self.memory_manager.add_to_scratchpad(context, observation)
                        
                        # 標記為 DONE，讓迴圈走到最後由 LLM 產生回覆
                        context.state = AgentState.DONE
                        continue
                        
                    # 只有真正的系統底層錯誤，才交給自癒中心去嘗試修復
                    self._trigger_recovery(context, RecoveryReason.VALIDATION_ERROR)
                
            elif context.state == AgentState.DISPATCH:
                context.state = AgentState.EXECUTE
                
            elif context.state == AgentState.EXECUTE:
                current_step = context.current_plan.steps[context.current_plan.current_step_index]

                tool = self.tool_registry.get_tool(current_step.tool_name)

                try:
                    start_time = time.time()
                    tool_result = await tool.execute(current_step.arguments, context)
                    latency = (time.time() - start_time) * 1000

                    # 優先提取人類可讀的 message 給 LLM 看，如果沒有才退回顯示 raw data
                    tool_msg = tool_result.get("message", str(tool_result))

                    # 將結果封裝成 Observation 並寫入記憶體
                    observation = RichObservation(
                        tool_name=current_step.tool_name,
                        status=tool_result.get("status", "UNKNOWN"),
                        summary=f"[{current_step.tool_name}] 執行結果: {tool_msg}",
                        latency_ms=latency,
                        raw_data=tool_result
                    )
                    self.memory_manager.add_to_scratchpad(context, observation)
                    
                    current_step.status = "SUCCESS"
                    context.state = AgentState.OBSERVE

                except Exception as e:
                    # 觸發自癒機制
                    self._trigger_recovery(context, RecoveryReason.TOOL_ERROR)
                
            elif context.state == AgentState.OBSERVE:
                plan = context.current_plan
                
                if plan.current_step_index < len(plan.steps) - 1:
                    last_observation = context.observations[-1]
                    
                    if last_observation.status.upper() != "SUCCESS":
                        context.state = AgentState.DONE
                        continue

                    current_step = plan.steps[plan.current_step_index]
                    next_step = plan.steps[plan.current_step_index + 1]
                    
                    # 通用黃金參數提煉 + 安全雪球繼承
                    
                    # 1. 提煉通用黃金參數 (不管前一個是哪個工具，只抓排班系統看得懂的核心欄位)
                    golden_params = {}
                    if last_observation.raw_data:
                        golden_params = extract_golden_params(last_observation.raw_data)

                    # 2. 安全繼承：先繼承「當前步驟」原本就擁有的參數
                    for key, value in current_step.arguments.items():
                        if key not in next_step.arguments:
                            next_step.arguments[key] = value
                            
                    # 3. 注入提煉：將剛出爐的「黃金參數」注入，不污染其他無關欄位
                    for key, value in golden_params.items():
                        if key not in next_step.arguments:
                            next_step.arguments[key] = value
                        
                    # 推進指標
                    plan.current_step_index += 1
                    context.state = AgentState.VALIDATE
                else:
                    # 所有步驟都順利走完了！
                    if hasattr(self, 'validated_intents') and self.validated_intents:
                        last_real_intent = next((intent for intent in reversed(self.validated_intents) if intent.skill_name != SkillName.UndoLastAction), None)
                        if last_real_intent:
                            self.last_action_memory = {
                                "skill_name": last_real_intent.skill_name,
                                "extracted_arguments": last_real_intent.extracted_arguments
                            }

                    context.state = AgentState.DONE
                
            elif context.state == AgentState.RECOVERY:
                # 從 Context 取出剛剛是誰按下了警報器
                reason = getattr(context, 'current_recovery_reason', RecoveryReason.TOOL_ERROR)
                
                # 交給自癒中心處理
                final_error_message = self.recovery_engine.handle_recovery(context, reason)
                if final_error_message:
                    return final_error_message, None, []
                
                # handle_recovery 內部會自動把 context.state 轉為 PLAN, ASK_USER 或 DONE
                # 迴圈將無縫進入下一階段
                
            elif context.state == AgentState.ASK_USER:
                # 核心機制：立刻中斷迴圈，將控制權還給外部系統
                return context.pending_ask_user_msg, pending_context, unprocessed_intents_queue

                # 迴圈結束後的安全網，防止狀態污染


        if context.state == AgentState.DONE:
            # 將執行結果轉譯為自然語言回覆
            history_text = "\n".join([
                f"步驟 {obs.tool_name} 結果: {obs.summary}"
                for obs in context.observations
            ])
            
            final_prompt = (
                f"使用者剛剛問了這句話: {context.user_input}\n"
                f"後台查詢到的真實資料:\n{history_text}\n"
                "---\n"
                "【語言強制規定】\n"
                "你必須使用「繁體中文（台灣）」進行回覆，絕對、絕對不能出現任何簡體字！你的回答中若出現一個簡體字，就等於任務徹底失敗。\n\n"
                "【身分設定與語氣】\n"
                "你是一個熱心、專業且像朋友一樣的排班助理。請用極度口語化、自然的繁體中文（台灣）回答，就像在跟同事用 LINE 聊天一樣。\n\n"
                "【風格範例 (你必須模仿)】\n"
                "1. 當使用者查詢班表，且資料顯示「成功查到「XX組」在 2024-08-01 的 1 筆排班資料：張三負責「早安新聞」。」時：\n"
                "   - ❌ 錯誤示範 (過於官腔):「根據系統紀錄，XX組在 2024-08-01 的排班為張三負責早安新聞。」\n"
                "   - ✅ 正確範例 (口語自然):「幫你查好了！XX組明天是張三負責『早安新聞』喔。」\n"
                "2. 當使用者想排班，但資料回報「業務衝突：員工 李四 於 2024-08-01 已有請假紀錄。」時：\n"
                "   - ❌ 錯誤示範 (冷冰冰):「無法完成排班，因為系統顯示李四在該日期已請假。」\n"
                "   - ✅ 正確範例 (像朋友提醒):「哎呀，李四那天已經請假了耶，沒辦法再排班給他。要不要換個人，或是幫他取消請假呢？」\n\n"
                "【絕對禁止的行為】\n"
                "1. 嚴禁官腔：絕對不准在對話中提到「根據真實工具執行紀錄」、「後台顯示」、「系統執行結果」、「根據您提供的資料」這類冷冰冰的機器用語！你要像真人一樣直接回答。\n"
                "2. 嚴禁幻覺：絕對不可以自己發明或猜測未出現的部門、職稱、節目或員工。\n\n"
                "【回報原則 (極度重要：這將成為你的長期記憶)】\n"
                "1. 盤點戰果：仔細看上方的「真實資料」，如果有成功，請直接自信地宣告任務完成。\n"
                "2. 詳細報讀：不論是排班、修改還是「刪除」，你必須在回覆中清楚列出執行細節（人員姓名、日期、節目名稱）。\n"
                "   - 例如：「已為您將 7/1 到 7/31 某部門的所有排班（共 15 筆）全部註銷完畢。」\n"
                "3. 數據精確度：在回報工時或時數時，請務必保留原始數據中的單位（如 8.0h, 0.5h）。\n"
                "4. 動作存檔：你的這段回覆會被存入資料庫作為日後查詢的依據，請務必確保關鍵資訊（誰、什麼時候、做了什麼）準確無誤。\n"
            )

            # 呼叫 LLM 產生最終回覆 (使用 planner 裡的 llm client)
            # 注意：這裡不要用 generate_json，我們需要的是純文字對話
            final_reply = await self.llm.generate_text(final_prompt, context.user_input)

            context.pending_ask_user_msg = ""
            return final_reply, None, []

        return getattr(context, "pending_ask_user_msg", "任務結束。"), pending_context, unprocessed_intents_queue

    def _check_for_loops(self, context: ExecutionContext) -> bool:
        """紀錄軌跡並使用 LoopDetector 檢查"""
        if not context.current_plan or not context.current_plan.steps:
            return False
            
        current_step = context.current_plan.steps[context.current_plan.current_step_index]
        action_signature = f"{current_step.tool_name}_{json.dumps(current_step.arguments, sort_keys=True)}"
        
        context.action_history.append(action_signature)
        
        if self.loop_detector.detect_oscillation(context.action_history):
            print(f"[Loop Detected] 偵測到 Agent 行為震盪，強制介入！")
            return True
        return False

    def _trigger_recovery(self, context: ExecutionContext, reason: RecoveryReason):
        print(f"[Runtime] 觸發自癒警報，原因: {reason.value}")
        context.current_recovery_reason = reason
        context.state = AgentState.RECOVERY