from typing import Dict, List
from .base import BaseTool

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry.")
        return self._tools[name]

    def get_tools(self) -> Dict[str, BaseTool]:
        """回傳所有註冊的工具字典"""
        return self._tools

    def get_tool_names(self) -> List[str]:
        """回傳所有合法工具的名稱清單，供 Planner 驗證使用"""
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[dict]:
        """一鍵獲取所有工具的標準 Schema，供 PromptBuilder 使用"""
        return [tool.get_openai_schema() for tool in self._tools.values()]
