import json
import re
from typing import Dict, Any
from openai import AsyncOpenAI
from core.config import settings

class AsyncLocalLLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )
        self.model = settings.llm_model

    async def generate_json(self, prompt: str, user_input: str) -> Dict[str, Any]:
        """
        異步呼叫本地 GGUF 模型，並強制執行 JSON 結構提取與安全反序列化。
        """
        user_message = f"使用者輸入：{user_input}\n請輸出 JSON 計畫。"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                seed=42,
            )

            raw_content = response.choices[0].message.content
            return self._parse_json_safely(raw_content)

        except Exception as e:
            print(f"[LLM Client] 推論伺服器呼叫失敗: {str(e)}")
            return {"intent": "UNKNOWN", "goal": "API 呼叫失敗", "steps": []}

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        
        # 移除 Markdown 標記
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        
        # 嘗試萃取大括號範圍 (防禦 LLM 夾雜前言後語)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[LLM Client] JSON 結構解析失敗: {str(e)}。原文擷取: {text[:100]}...")
            return {"intent": "UNKNOWN", "goal": "解析失敗", "steps": []}

    async def generate_text(self, prompt: str, user_input: str = "") -> str:
        """
        用於生成一般的自然語言回覆，不強制輸出 JSON。
        """
        messages = [
            {"role": "system", "content": prompt}
        ]
        if user_input:
            messages.append({"role": "user", "content": user_input})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"[LLM Client] 生成文字時發生錯誤: {e}")
            return "抱歉，我已經完成任務，但在整理回覆時遇到了點問題。"
