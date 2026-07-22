import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from .skills_registry import SkillName

class SingleIntent(BaseModel):
    skill_name: SkillName
    extracted_arguments: Dict[str, Any]
    reasoning: str

class RouterOutput(BaseModel):
    intents: List[SingleIntent] = Field(
        ..., 
        description="解析出的所有意圖列表。如果使用者一句話包含多個指令，請拆分成多個意圖。"
    )

class SemanticSkillRouter:
    def __init__(self, llm_client):
        """
        初始化 Router，傳入你的 LLM 客戶端 (支援 OpenAI SDK 格式的 Client，如本地端 Ollama/vLLM)
        """
        self.llm_client = llm_client
        
        # 路由器 Prompt (升級為語義編譯器)
        self.system_prompt = """
        你是一個專業的電視台排班「語義編譯器 (Semantic Compiler)」。
        你的任務是：將使用者千奇百怪的台灣口語指令，「編譯」成系統標準化的 JSON 格式。
        
        【動作編譯表】：
        1. AssignProgramStaff: 排班、弄班、指派。
        2. CancelProgramShift: 註銷、踢掉、拿掉、不用排了。
        3. UndoLastAction: 復原、回上一步、弄錯了。
        4. BatchAssign: 批次排班。當涉及「每天」、「這週一到五」、「週末」、「整個月」等範圍時使用。
        5. SwapShift: 換班、互換。
        6. QuerySchedule: 查班、看班表、有排什麼。
        7. CheckDailyStatus: 問時間、有沒有空、查工時上限、剩餘小時。
        8. RegisterLeave: 請假、特休、病假、事假、補休、例假日、休假日。

        【時間正規化規則 (極度重要)】：
        請利用「當前時間參考資料」，將相對時間換算為標準格式：
        - 「明天」、「後天」、「下週三」 -> 請直接計算出具體的日期（如 "2024-05-24"）。
        - 「這週五」 -> 根據今天日期計算出該週五的日期。
        - 提到「X月份」或「X月」時 -> 請輸出 "YYYY-MM" 格式（如 "2024-07"）。請根據當前年份判斷，若該月份已過，則視為明年。
        - 如果是模糊的時間範圍（如：這週、下週、整個月），請儘可能精確化。

        【業務語義標籤 (@Tags)】：
        請在 JSON 的 `extracted_arguments` 中根據語境加入以下標籤（若適用）：
        - `@SCOPE`: "SELF" (僅針對使用者本人), "TEAM" (針對整個組或部門)。
        - `@DURATION`: "FULL" (排滿班、全天、整天), "PARTIAL" (部分時段)。

        【絕對遵守規則】：
        1. 語義對齊：請務必利用提供的「實體清單」，將使用者口中的「那個人」、「那群人」、「這個節目」自動對齊到標準名稱。
        2. 繁體中文：所有推理與 JSON 內容必須使用「繁體中文（台灣）」。
        3. 倒裝處理：不論語序如何（如：班表，幫我查，明天），請正確歸類意圖。
        4. 精確解析：如果使用者說「幫我排班」，且沒有提到別人，請預設為 `@SCOPE: SELF`。

        【強制輸出格式】：
        回傳 JSON 陣列 `intents`：
        範例 (使用者：幫我排這個月20號事假)：
        {
            "intents": [{
                "skill_name": "RegisterLeave",
                "extracted_arguments": {
                    "staff_name": "本人",
                    "leave_type": "事假",
                    "date": "2024-05-20"
                },
                "reasoning": "使用者要求請假，已根據當前時間計算具體日期"
            }]
        }
        
        【權限與範圍規則】：
        - 如果使用者提到「我」、「本人」，請填入 `staff_name: "本人"`。
        - 如果使用者身份是「管理員 (admin)」或「製作人 (producer)」，且指令包含「全部」、「所有人」、「全組」等詞彙：
            - 在「查詢」或「取消」意圖下，請將 `staff_name` 留空，並在 `reasoning` 標註「全域操作」。
            - 若提到特定部門（如：音效組），請填入 `department` 欄位。
        """

    async def route_intent(self, user_input: str, pending_context: dict = None, system_context: dict = None) -> RouterOutput:
        """
        呼叫 LLM 進行意圖分類，並返回結構化資料。
        現在支援進階的語義正規化，能自動對齊資料庫實體。
        """
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            weekday_str = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
            
            # 準備動態的 System Prompt
            dynamic_prompt = self.system_prompt
            dynamic_prompt += f"\n\n【當前時間參考資料】\n今天是：{today_str} (星期{weekday_str})\n"
            
            # 1. 注入動態語義清單 (幫助 LLM 進行翻譯與正規化)
            if system_context:
                dynamic_prompt += f"""
                
                【當前系統可用實體清單 (極度重要)】
                在提取參數時，請優先將使用者的口語「翻譯」或「對齊」到以下清單中的精確名稱：
                - 員工名單：{", ".join(system_context.get("staff_names", []))}
                - 節目名單：{", ".join(system_context.get("program_names", []))}
                - 部門名單：{", ".join(system_context.get("department_names", []))}
                
                【翻譯規則】：
                - 如果使用者說綽號或簡稱，請自動對齊到實體清單中的標準名稱。
                - 如果使用者說「XX組」，請自動對齊到對應的部門名稱。
                - 如果使用者說節目的簡稱，請自動對齊到標準節目名稱。
                """

            if pending_context:
                dynamic_prompt += f"""
                
                【上下文記憶 (極度重要)】
                使用者目前的輸入，是為了補充剛才遺漏的排班資訊，請勿當作全新的指令！
                - 正在執行的技能：{pending_context['skill_name'].value}
                - 已經收集到的參數：{pending_context['extracted_arguments']}
                
                【你的任務】：
                請從使用者的最新回覆中，提取剛才缺少的參數，並將它與「已經收集到的參數」合併。
                最後回傳完整的 JSON，技能名稱請保持為 {pending_context['skill_name'].value}。
                """

            # 組合最終的 Prompt 給本地模型
            combined_prompt = f"{dynamic_prompt}\n\n使用者最新指令: {user_input}\n\n請務必只回傳合法的 JSON 格式字串："

            # 呼叫 LLM 進行意圖解析
            parsed_dict = await self.llm_client.generate_json(
                prompt=combined_prompt,
                user_input=user_input
            )
            
            raw_intents = parsed_dict.get("intents", [])
            if not raw_intents:
                raw_intents = [parsed_dict]

            final_intents = []
            for intent_data in raw_intents:
                if pending_context and len(raw_intents) == 1:
                    final_skill = pending_context["skill_name"]
                    new_args = intent_data.get("extracted_arguments") or intent_data.get("parameters") or {}
                    final_args = {**pending_context["extracted_arguments"], **new_args}
                    final_reasoning = "系統強制繼承上一輪記憶 (Slot Filling)"
                else:
                    final_skill = intent_data.get("skill_name") or intent_data.get("skill") or SkillName.Unknown
                    final_args = intent_data.get("extracted_arguments") or intent_data.get("parameters") or {}
                    final_reasoning = intent_data.get("reasoning") or intent_data.get("reason") or "無"
                
                final_intents.append(SingleIntent(
                    skill_name=final_skill,
                    extracted_arguments=final_args,
                    reasoning=final_reasoning
                ))
            
            return RouterOutput(intents=final_intents)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return RouterOutput(intents=[SingleIntent(skill_name=SkillName.Unknown, extracted_arguments={}, reasoning=str(e))])
