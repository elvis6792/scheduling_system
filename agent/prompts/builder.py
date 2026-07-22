import json

class PromptBuilder:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def build_planning_prompt(self, context) -> str:
        # 直接拿取所有標準化的 Schema
        schemas = self.tool_registry.get_all_schemas()
        
        if not schemas:
            tool_descriptions = "警告：系統目前尚未註冊任何可用工具。"
        else:
            # 將 Schema 轉成漂亮的 JSON 字串餵給 LLM
            tool_descriptions = json.dumps(schemas, ensure_ascii=False, indent=2)

        return f"""
你是一個極度嚴謹的「自動化排班 API 呼叫器」。

【可用工具清單與規格 (Available Tools)】
你【只能】從下列工具中挑選，絕對禁止發明任何不在清單上的工具名稱：
{tool_descriptions}

【嚴格行為準則】
1. 禁止 Workflow Planning：絕不能輸出「確認需求」、「搜尋資料」、「篩選結果」等自然語言步驟。
2. 步驟 (steps) 只能包含精確的 API 工具呼叫。

【輸出格式約束】
請嚴格輸出以下 JSON 格式。每個步驟必須包含 "tool_name" 和 "arguments"。
{{
  "intent": "任務意圖",
  "goal": "最終目標",
  "steps": [
    {{
      "tool_name": "<必須是清單中的工具名稱>",
      "arguments": {{ ...符合該工具參數定義的 JSON 物件... }}
    }}
  ]
}}
"""
