from dataclasses import dataclass, field
from typing import List, Dict, Any
from ..models.observation import RichObservation
from .state import ExecutionContext

@dataclass
class TurnSummary:
    """單一對話回合的長期濃縮記憶"""
    turn_id: int
    user_query: str
    intent: str
    actions_taken: List[str]
    final_result: str

class MemoryManager:
    def __init__(self):
        # 1. Global Memory：全域靜態設定、系統規則、使用者偏好
        self.global_memory: Dict[str, Any] = {
            "system_mode": "Strict API Mode",
            "allowed_channels": ["LINE", "Web"],
            "max_daily_hours_per_staff": 8
        }
        
        # 2. Session Memory：跨回合的長期歷史記憶（壓縮後的摘要）
        self.session_memory: List[TurnSummary] = []
        self._turn_counter = 0

        # 3. Persistent History：從資料庫載入的原始對話紀錄
        self.chat_history: List[Dict[str, str]] = []

    def set_chat_history(self, history: List[Dict[str, str]]):
        """設置從資料庫載入的歷史紀錄"""
        self.chat_history = history

    def get_task_scratchpad(self, context: ExecutionContext) -> List[RichObservation]:
        """
        3. Task Scratchpad (草稿區)：當前這一次多步驟任務的短期工作記憶。
        直接借用 context.observations 來實作，因為它只活在當前生命週期中。
        """
        return context.observations

    def add_to_scratchpad(self, context: ExecutionContext, observation: RichObservation):
        """將剛剛執行的工具結果寫入當前任務草稿區"""
        context.observations.append(observation)
        print(f"[Task Scratchpad] 寫入短期觀察: [{observation.tool_name}] 狀態: {observation.status}, 耗時: {observation.latency_ms}ms")

    def archive_task_to_session(self, context: ExecutionContext, final_response: str):
        """
        【關鍵機制：任務焚化爐】
        當狀態機進入 DONE 時呼叫。將當前任務中複雜的 Tool 呼叫濃縮封裝進 Session Memory，
        然後徹底清空 Task Scratchpad，確保下一輪任務開始時，LLM 的大腦乾淨無污染。
        """
        self._turn_counter += 1
        
        # 提取這一次任務執行過的所有動作摘要
        actions = []
        for obs in context.observations:
            if isinstance(obs, RichObservation):
                actions.append(f"{obs.tool_name}({obs.status})")
        
        intent = context.current_plan.intent if context.current_plan else "UNKNOWN"
        
        summary = TurnSummary(
            turn_id=self._turn_counter,
            user_query=context.user_input,
            intent=intent,
            actions_taken=actions,
            final_result=final_response
        )
        
        self.session_memory.append(summary)
        print(f"[Memory Manager] 任務結束。濃縮封裝第 {self._turn_counter} 回合歷史，草稿區已清空。")
        
        # 徹底清空當前任務的短期記憶與行為軌跡
        context.observations.clear()
        context.action_history.clear()
        context.current_plan = None

    def build_full_turn_history(self, context: ExecutionContext) -> List[Dict[str, str]]:
        """組合長期與短期記憶，建立完整的對話歷史給 LLM 參考"""
        history = []
        
        # 1. 優先加入從 DB 載入的持久記憶 (取最近 10 筆)
        history.extend(self.chat_history[-10:])
        
        # 2. 如果 Session Memory 還有額外的摘要，可以視需求加入 (目前先以原始對話為主)

        return history

    def build_long_term_prompt_fragment(self) -> str:
        """將長期 Session 記憶轉化為極簡的 Prompt 片段（省 Token 核心）"""
        if not self.session_memory:
            return "【歷史記憶】：無前情提要。"
            
        # 為了防止 Context 膨脹，我們永遠只拿最近 2 回合的「濃縮精華」
        recent_turns = self.session_memory[-2:]
        fragment = "【前情提要（歷史對話濃縮）】\n"
        for turn in recent_turns:
            fragment += f"- 用戶之前說：「{turn.user_query}」\n"
            fragment += f"  系統執行的核心動作：{', '.join(turn.actions_taken)}\n"
            fragment += f"  系統最終對用戶的回覆：「{turn.final_result}」\n"
        return fragment

    def build_short_term_prompt_fragment(self, context: ExecutionContext) -> str:
        """將草稿區的進度轉化為 LLM 目前的作戰地圖"""
        if not context.observations:
            return "【當前任務進度】：這是新任務的第一步，尚未執行任何工具。"
            
        fragment = "【當前任務進度（剛才已完成的步驟）】\n"
        for idx, obs in enumerate(context.observations):
            if isinstance(obs, RichObservation):
                fragment += f"{idx+1}. 工具 [{obs.tool_name}] 執行結果為 {obs.status} -> {obs.summary}\n"
                if obs.error_code:
                    fragment += f"   系統錯誤代碼: {obs.error_code}\n"
        return fragment