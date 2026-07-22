from typing import List

class LoopDetector:
    def __init__(self, history_window: int = 6):
        # 只檢查最近 N 步的軌跡
        self.history_window = history_window

    def detect_oscillation(self, action_history: List[str]) -> bool:
        """
        偵測行為軌跡中是否有重複的震盪模式
        """
        if len(action_history) < 4:
            return False
            
        recent_history = action_history[-self.history_window:]
        
        # 檢查是否存在長度為 2 或 3 的重複 Pattern
        for pattern_length in range(1, len(recent_history) // 2 + 1):
            pattern1 = recent_history[-pattern_length:]
            pattern2 = recent_history[-(pattern_length * 2):-pattern_length]
            
            if pattern1 == pattern2:
                return True
                
        return False