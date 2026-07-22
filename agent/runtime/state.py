from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class AgentState(Enum):
    IDLE = auto()           # 閒置/初始化
    UNDERSTAND = auto()     # 意圖解析
    GOAL_SETTING = auto()   # 設定高階目標
    PLAN = auto()           # 產生多步驟計畫
    VALIDATE = auto()       # 輸入與業務邏輯驗證
    DISPATCH = auto()       # 分派任務給特定 Worker
    EXECUTE = auto()        # 執行工具
    OBSERVE = auto()        # 收集執行結果與中介資料
    RECOVERY = auto()       # 自癒中心
    ASK_USER = auto()       # 掛起任務，等待人類回覆
    DONE = auto()           # 任務完成或優雅終止

class RecoveryReason(Enum):
    LOOP_DETECTED = "LOOP_DETECTED"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    BUSINESS_CONFLICT = "BUSINESS_CONFLICT" # 業務衝突
    TOOL_ERROR = "TOOL_ERROR"
    JSON_ERROR = "JSON_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

@dataclass
class ToolStep:
    """代表計畫中的單一執行步驟"""
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "PENDING"  # PENDING, SUCCESS, ERROR, SKIPPED
    is_confirmed: bool = False # 此步驟是否已獲人類授權

@dataclass
class ExecutionPlan:
    """多步驟執行計畫書"""
    intent: str
    goal: str
    steps: List[ToolStep] = field(default_factory=list)
    current_step_index: int = 0

@dataclass
class ExecutionContext:
    """全域執行上下文 (傳遞於所有 State 之間)"""
    session_id: str
    user_input: str
    state: AgentState = AgentState.IDLE
    
    # 使用者身份
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[int] = None
    staff_id: Optional[int] = None
    
    # 記憶與觀測
    current_plan: Optional[ExecutionPlan] = None
    observations: List[Any] = field(default_factory=list)
    
    # 控制與中斷狀態
    retry_count: int = 0
    pending_ask_user_msg: str = ""  # 要問使用者的問題
    current_recovery_reason: Optional[RecoveryReason] = None
    
    # 行為軌跡
    action_history: List[str] = field(default_factory=list)