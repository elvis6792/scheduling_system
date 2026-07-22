import json
import re
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Define data structures locally for now to decouple from state
class ToolStep(BaseModel):
    tool_name: str
    arguments: dict

    # 供 Runtime 執行後寫入的欄位
    status: str = "PENDING"
    result: Optional[Any] = None

class ExecutionPlan(BaseModel):
    intent: str
    goal: str
    steps: List[ToolStep]
    current_step_index: int = 0

class Planner:
    def __init__(self, llm_client: Any, prompt_builder: Any, tool_registry: Any):
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.tool_registry = tool_registry

    async def generate_plan(self, context: Any) -> ExecutionPlan:
        prompt = self.prompt_builder.build_planning_prompt(context)
        
        raw_response = await self.llm.generate_json(prompt, context.user_input)
        
        if isinstance(raw_response, dict):
            parsed_data = raw_response
        else:
            cleaned_response = raw_response
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1)
                
            try:
                parsed_data = json.loads(cleaned_response.strip())
            except json.JSONDecodeError:
                print(f"JSON 解析失敗！LLM 原始回應:\n{raw_response}")
                raise ValueError("解析失敗，LLM 未輸出合法 JSON。")

        valid_tool_names = self.tool_registry.get_tool_names()
        steps = []
        
        for step in parsed_data.get("steps", []):
            tool_name = step.get("tool_name", "unknown")
            arguments = step.get("arguments", {})
            
            # 驗證工具名稱
            if tool_name not in valid_tool_names:
                raise ValueError(f"ToolValidationError: LLM 試圖呼叫非法工具 '{tool_name}'。\\n合法工具清單為: {valid_tool_names}")
                
            steps.append(ToolStep(tool_name=tool_name, arguments=arguments))
            
        return ExecutionPlan(
            intent=parsed_data.get("intent", "UNKNOWN"),
            goal=parsed_data.get("goal", "未定義目標"),
            steps=steps
        )
