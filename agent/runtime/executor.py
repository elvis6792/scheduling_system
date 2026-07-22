from typing import Dict, Any, List
from ..router.skill_router import SemanticSkillRouter, RouterOutput, SkillName
from ..router.skills_registry import SKILL_WORKFLOWS
from ..tools.registry import ToolRegistry
import asyncio

# Import tool implementations
from ..tools.implementations.cancel_shift import CancelShiftTool
from ..tools.implementations.check_daily_status import CheckDailyStatusTool
from ..tools.implementations.create_shift import CreateShiftTool

class Executor:
    def __init__(self, llm_client):
        self.router = SemanticSkillRouter(llm_client)
        self.tool_registry = ToolRegistry() 
        
        # Register tools
        self.tool_registry.register(CancelShiftTool())
        self.tool_registry.register(CheckDailyStatusTool())
        self.tool_registry.register(CreateShiftTool())

    async def execute_skill(self, router_output: RouterOutput) -> Any:
        skill_name = router_output.skill_name
        extracted_args = router_output.extracted_arguments

        if skill_name == SkillName.Unknown:
            return {"status": "failed", "message": "無法識別的使用者意圖，請提供更明確的指令。"}
        
        # 根據技能名稱，從靜態工作流中獲取對應的工具列表
        tool_names_in_workflow = SKILL_WORKFLOWS.get(skill_name)
        if not tool_names_in_workflow:
            return {"status": "failed", "message": f"技能 {skill_name} 尚未定義工作流。"}

        results = []
        for tool_name in tool_names_in_workflow:
            tool_instance = self.tool_registry.get_tool(tool_name)
            if not tool_instance:
                results.append({"status": "failed", "message": f"工具 {tool_name} 未註冊。"})
                return {"status": "failed", "message": f"執行技能 {skill_name} 時，工具 {tool_name} 未找到。"}
            
            print(f"DEBUG: 執行工具 {tool_name} with args {extracted_args}")
            
            try:
                tool_result = await tool_instance.run(**extracted_args)
                results.append({"tool": tool_name, "status": "success", "result": tool_result})
            except Exception as e:
                results.append({"tool": tool_name, "status": "error", "message": str(e)})
                # 如果工作流中的任何工具執行失敗，整個技能執行失敗
                return {"status": "failed", "message": f"工具 {tool_name} 執行失敗: {str(e)}", "details": results}
        
        return {"status": "success", "skill_executed": skill_name, "results": results}

    async def process_user_request(self, user_input: str) -> Dict[str, Any]:
        print(f"DEBUG: 接收到使用者請求: {user_input}")
        
        # 1. 意圖路由
        router_output = await self.router.route_intent(user_input)
        print(f"DEBUG: 路由結果 - 技能: {router_output.skill_name}, 參數: {router_output.extracted_arguments}, 原因: {router_output.reasoning}")

        # 2. 執行技能
        execution_result = await self.execute_skill(router_output)
        print(f"DEBUG: 執行結果: {execution_result}")
        
        return execution_result
