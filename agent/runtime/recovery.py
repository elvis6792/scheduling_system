from .state import AgentState, ExecutionContext, RecoveryReason

class RecoveryEngine:
    """
    自癒中心。
    當系統在執行過程中遇到錯誤時，Runtime 會將控制權轉交給此中心。
    RecoveryEngine 會根據錯誤的類型與重試次數，決定下一步的策略。
    """
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def handle_recovery(self, context: ExecutionContext, reason: RecoveryReason):
        """
        根據錯誤原因決定下一步策略：重試、放棄、或向使用者求助。
        此方法會直接修改 context.state，將狀態機導向下一階段。
        """
        context.retry_count += 1
        print(f"[自癒中心] 啟動第 {context.retry_count}/{self.max_retries} 次修復程序。原因: {reason.value}")

        if context.retry_count >= self.max_retries:
            print("[自癒失敗] 已達最大重試次數，放棄任務。")
            context.state = AgentState.DONE
            return f"抱歉，系統在處理時遇到連續的參數錯誤，任務已被強制終止，未寫入任何資料。請確認指令格式。"

        # 偵測到迴圈，需要重新規劃
        if reason == RecoveryReason.LOOP_DETECTED:
            print("[策略] 偵測到行為震盪，強制重新規劃路徑。")
            context.current_plan = None # 清空舊計畫
            context.action_history.clear() # 清空軌跡
            context.state = AgentState.PLAN

        elif reason in [RecoveryReason.INVALID_ARGUMENT, RecoveryReason.MISSING_PARAMETER, RecoveryReason.BUSINESS_CONFLICT, RecoveryReason.TOOL_ERROR, RecoveryReason.VALIDATION_ERROR]:
            # 帶著錯誤觀察重新規劃
            print("[策略] 參數、業務邏輯或工具執行出錯，帶著錯誤觀察重新規劃。")
            context.current_plan = None # 清空舊計畫
            context.state = AgentState.PLAN
            
        else: # 其他未明確處理的錯誤
            print(f"[策略] 發生未定義的恢復策略錯誤 ({reason.value})，轉向使用者求助。")
            context.pending_ask_user_msg = f"系統遇到一個問題 ({reason.value})，需要您的協助。"
            context.state = AgentState.ASK_USER
        
        return None