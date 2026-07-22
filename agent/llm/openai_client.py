import json
import re
from typing import Dict, Any
from openai import AsyncOpenAI
from core.config import settings

class AsyncOpenAIClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model

    async def generate_json(self, prompt: str, user_input: str) -> Dict[str, Any]:
        """
        封裝呼叫 OpenAI API，並確保回傳絕對安全的 Dict，
        接軌 V5 Planner 的介面需求。
        """
        system_prompt = prompt
        user_message = f"""使用者輸入：{user_input}
請輸出 JSON 計畫。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # 降低隨機性，提高 JSON 穩定性
                seed=42
            )
            
            raw_content = response.choices[0].message.content
            return self._parse_json_safely(raw_content)
            
        except Exception as e:
            print(f"[LLM Client] API 呼叫失敗: {str(e)}")
            # 發生 API 錯誤時，回傳空計畫，交由 V5 引擎的空計畫防禦網接手
            return {"intent": "UNKNOWN", "goal": "API 呼叫失敗", "steps": []}

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """剝離 Markdown 標籤，防止 JSONDecodeError"""
        text = text.strip()
        # 移除可能出現的 ```json 與 ``` 標籤
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[LLM Client] JSON 解析失敗: {str(e)}。原文: {text}")
            return {"intent": "UNKNOWN", "goal": "解析失敗", "steps": []}
