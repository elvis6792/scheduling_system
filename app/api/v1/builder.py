from datetime import datetime
from typing import Any

class PromptBuilder:
    def __init__(self, tool_registry: Any):
        self.tool_registry = tool_registry
        self.base_role = ( # 修正：base_role 應該是一個字串，而不是元組
            "你是一個具備高度專業素養的電視台排班助理。"
        )

    def _get_temporal_context(self) -> str:
        current_time_str = datetime.now().strftime("%Y-%m-%d %A")
        return (f"【系統核心資訊】\n"
                f"當前真實時間：{current_time_str}")

    def build_planning_prompt(self, context: Any) -> str:
        """
        組裝給 Planner 看的精簡版 Prompt，包含工具 Schema 與狀態記憶。
        """
        try:
            tools_schema = self.tool_registry.get_all_schemas()
        except AttributeError:
            tools_schema = "[]"

        parts = [
            self._get_temporal_context(),
            self.base_role,
            f"【可用工具清單】\n{tools_schema}",
            ("【任務最高指導原則】\n"
             "1. 時間推算：當使用者在指令中提到任何相對時間（例如：「明天」、「後天」、「下週一」、「下個月底」），你必須「絕對依賴」上述的【當前真實時間】進行精準的數學推算。\n"
             "2. 格式轉換：推算完成後，在呼叫任何工具時，日期參數一律只允許輸出標準的 YYYY-MM-DD 格式，嚴禁傳遞自然語言或相對日期。\n"
             "3. 輸出格式：嚴格按照 JSON 格式輸出包含 `intent`, `goal`, `steps` 的執行計畫。"),
            ("【操作原則】\n"
             "當使用者要求「取消排班」時，請直接且唯一呼叫 cancel_shift 工具，並傳入日期與節目名稱。嚴禁在取消前呼叫人力查詢工具。")
        ]

        if context.observations:
            obs_text = "【目前短期進度 (剛才發生的事)】\n"
            for obs in context.observations:
                status = getattr(obs, 'status', 'UNKNOWN')
                summary = getattr(obs, 'summary', '')
                obs_text += f"- 狀態: {status}, 摘要: {summary}\n"
            parts.append(obs_text)

        return "\n\n".join(parts)