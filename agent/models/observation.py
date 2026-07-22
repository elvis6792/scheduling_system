from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class RichObservation:
    """
    全景觀測資料模型。
    完整記錄單一工具執行的所有面向，包含結果、效能、成本與元資料。
    """
    tool_name: str
    status: str  # SUCCESS, ERROR, FATAL, VALIDATION_FAILED
    summary: str
    latency_ms: float = 0.0
    
    # Optional fields
    raw_data: Optional[Any] = None
    error_code: Optional[str] = None
    token_usage: Optional[int] = None
    confidence: Optional[float] = None