from ..runtime.state import RecoveryReason

class WorkerError(Exception):
    """Worker 執行失敗的基底類別"""
    def __init__(self, reason: RecoveryReason, message: str):
        self.reason = reason
        self.message = message
        super().__init__(self.message)