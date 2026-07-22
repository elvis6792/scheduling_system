from abc import ABC, abstractmethod
from typing import Any

class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, arguments: dict) -> Any:
        """執行工具的具體邏輯"""
        pass

    @abstractmethod
    def get_openai_schema(self) -> dict:
        """
        統一對外輸出 OpenAI Function Calling 標準格式。
        所有繼承此類別的工具都必須實作這個方法。
        """
        pass
