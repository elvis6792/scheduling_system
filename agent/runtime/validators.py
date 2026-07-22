import re
import dateparser
from datetime import date, timedelta, datetime
from typing import Any, AsyncContextManager, Callable, Dict, Tuple, List, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import LeaveRecord, Shift, Staff, Program, Department
from .state import ToolStep, RecoveryReason
from agent.persistence.repository import SchedulingRepository
from app.services.scheduler import validate_total_hours, DoubleBookingError

class ValidationError(Exception):
    """驗證失敗的基底類別"""
    def __init__(self, reason: RecoveryReason, message: str):
        self.reason = reason
        self.message = message
        super().__init__(self.message)

class InputValidationError(ValidationError):
    """輸入格式錯誤"""
    pass

class BusinessValidationError(ValidationError):
    """業務邏輯衝突"""
    pass

def is_valid_date(date_str: Any) -> bool:
    if not date_str:
        return False
    return isinstance(date_str, (str, list, date, datetime))

def resolve_smart_date(date_str: Any) -> Any:
    """
    智能時間解析器：結合精準映射與 NLP 解析。
    支援字串、日期物件或清單（取首項）。
    """
    if not date_str:
        return None
        
    # 1. 處理日期/時間物件
    if isinstance(date_str, (date, datetime)):
        return date_str.date() if isinstance(date_str, datetime) else date_str
        
    # 2. 處理清單 (遞迴取第一個)
    if isinstance(date_str, list):
        for item in date_str:
            res = resolve_smart_date(item)
            if res: return res
        return None
        
    # 3. 強制轉為字串處理
    d_str = str(date_str).strip()
    today = date.today()
    
    # 處理贅字
    clean_str = d_str.replace("的", "").strip()

    # 直接映射口語日期
    quick_match = {
        "前天": today - timedelta(days=2),
        "昨天": today - timedelta(days=1),
        "今天": today,
        "明天": today + timedelta(days=1),
        "後天": today + timedelta(days=2),
        "大後天": today + timedelta(days=3)
    }
    
    if clean_str in quick_match:
        return quick_match[clean_str]

    # 簡化邏輯：優先信任 LLM 傳入的格式，僅保留核心映射與解析
    if clean_str in quick_match:
        return quick_match[clean_str]

    # NLP 處理 (這部分作為最後防線，處理 LLM 漏掉的細節)
    parsed = dateparser.parse(
        clean_str, 
        languages=['zh', 'zh-Hant'],
        settings={
            'PREFER_DATES_FROM': 'future', 
            'RELATIVE_BASE': datetime.combine(today, datetime.min.time()),
            'TIMEZONE': 'Asia/Taipei',
            'RETURN_AS_TIMEZONE_AWARE': False
        }
    )
    if parsed:
        return parsed.date()
        
    # 標準 ISO 格式或 M/D 格式
    try:
        if "/" in clean_str and "-" not in clean_str:
            parts = clean_str.split("/")
            if len(parts) == 2:
                return date(today.year, int(parts[0]), int(parts[1]))
        return date.fromisoformat(clean_str)
    except:
        return None

class InputValidator:
    def __init__(self):
        self.forbidden_keywords = ["隨便", "個人", "找個人", "某人", "音效師", "誰都可以", "WILL_BE_FILLED_LATER"]

    def validate(self, step: ToolStep, context: "ExecutionContext") -> None:
        args = step.arguments

        for key, value in args.items():
            if isinstance(value, str) and any(kw in value for kw in self.forbidden_keywords):
                raise InputValidationError(
                    reason=RecoveryReason.INVALID_ARGUMENT,
                    message=f"參數 '{key}' 包含無效的代名詞或佔位符 ('{value}')。"
                )

        if "date" in args and args["date"]:
            if not is_valid_date(args["date"]):
                raise InputValidationError(
                    reason=RecoveryReason.INVALID_ARGUMENT,
                    message=f"日期格式錯誤 ('{args['date']}')。"
                )

class BusinessValidator:
    def __init__(self, db_session_maker: "async_sessionmaker"):
        self.db_session_maker = db_session_maker

    async def validate(self, step: ToolStep, context: "ExecutionContext") -> None:
        user_role = context.role
        user_dept_id = context.department_id
        user_staff_id = context.staff_id

        # 禁止非 Admin 角色進行任何「時數上限」或「系統配置」的調整
        forbidden_params = ["work_hours", "hours_limit", "daily_hours", "max_hours"]
        if any(p in step.arguments for p in forbidden_params):
            if user_role != "admin":
                raise BusinessValidationError(
                    reason=RecoveryReason.BUSINESS_CONFLICT, 
                    message="權限不足：僅有系統管理員可以臨時調整上班時數或系統參數。"
                )

        async with self.db_session_maker() as session:
            repo = SchedulingRepository(session)
            
            if step.tool_name in ["create_shift", "check_daily_status", "cancel_shift", "query_schedule", "batch_create_shift", "batch_check_daily_status", "register_leave"]:
                staff_name = step.arguments.get("staff_name")
                
                if not staff_name and user_role == "staff" and user_staff_id:
                    my_staff = await session.get(Staff, user_staff_id)
                    if my_staff:
                        staff_name = my_staff.name
                        step.arguments["staff_name"] = staff_name

                if not staff_name and not step.arguments.get("department") and user_role == "staff":
                    my_staff = await session.get(Staff, user_staff_id)
                    if my_staff:
                        step.arguments["staff_name"] = my_staff.name
                        staff_name = my_staff.name

                if not staff_name: return

                stmt = select(Staff)

                # 權限邏輯：
                # 1. 查詢/狀態檢查：Admin 與 Producer 豁免部門限制
                if user_role not in ["admin", "producer"]:
                    if step.tool_name in ["check_daily_status", "query_schedule", "batch_check_daily_status"]:
                        if not user_dept_id:
                            raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message="您未綁定部門。")
                        
                        req_dept = step.arguments.get("department")
                        if req_dept:
                            dept_stmt = select(Department).where(Department.name.like(f"%{req_dept}%"))
                            dept_obj = (await session.execute(dept_stmt)).scalars().first()
                            if dept_obj and dept_obj.id != user_dept_id:
                                raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message="權限不足：無法跨部門查詢。")
                        stmt = stmt.where(Staff.department_id == user_dept_id)

                # 2. 新增班表/請假：Admin 與 Producer 豁免「只能幫自己排」的限制
                if user_role not in ["admin", "producer"]:
                    if step.tool_name in ["create_shift", "batch_create_shift", "register_leave"]:
                        if not user_staff_id:
                            raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message="您未綁定員工身分。")
                        
                        stmt = stmt.where(Staff.id == user_staff_id)
                        my_staff_record = await session.get(Staff, user_staff_id)
                        if my_staff_record and staff_name and my_staff_record.name != staff_name:
                             raise BusinessValidationError(
                                reason=RecoveryReason.BUSINESS_CONFLICT, 
                                message=f"權限不足：您僅能操作自己的班表 ({my_staff_record.name})。"
                            )

                # 3. 刪除/取消班表：這是最嚴格的一環
                if step.tool_name == "cancel_shift":
                    # Admin 擁有絕對權限，直接跳過檢查
                    if user_role == "admin":
                        pass 
                    # Producer: 可以刪除任何人，但前提是「這筆班是他排的」
                    elif user_role == "producer":
                        # 注意：這裡我們先不做 Staff ID 限制，因為他可以刪別人的，但要在底層工具檢查 created_by
                        # 為了讓意圖通過驗證，我們在這裡放行，但註記需要 Ownership 檢查
                        pass
                    # 一般員工：只能刪除自己的
                    else:
                        if not user_staff_id:
                            raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message="您未綁定員工身分。")
                        stmt = stmt.where(Staff.id == user_staff_id)

                if staff_name:
                    stmt = stmt.where(Staff.name.like(f"%{staff_name}%"))

                result = await session.execute(stmt)
                staff_list = result.scalars().all()
                
                if len(staff_list) > 1:
                    raise BusinessValidationError(reason=RecoveryReason.INVALID_ARGUMENT, message=f"AMBIGUOUS_ENTITY: 找到多位符合「{staff_name}」的員工。")
                elif len(staff_list) == 0:
                    raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message=f"找不到員工「{staff_name}」。")
                else:
                    step.arguments["staff_name"] = staff_list[0].name

            # 工時與請假驗證 (簡化並增強)
            if step.tool_name in ["create_shift", "register_leave"]:
                date_val = step.arguments.get("date")
                staff_name = step.arguments.get("staff_name")
                if not staff_name or not date_val: return

                staff = (await session.execute(select(Staff).where(Staff.name == staff_name))).scalar_one()
                target_date = resolve_smart_date(date_val)
                if not target_date: return

                if step.tool_name == "create_shift":
                    if await repo.check_leave_record(staff.id, target_date):
                        raise BusinessValidationError(reason=RecoveryReason.BUSINESS_CONFLICT, message=f"員工 {staff.name} 於 {target_date} 已有請假紀錄。")

def preprocess_taiwan_dates(date_str: str, reference_date: datetime) -> str:
    """
    僅進行基本的口語正規化，不再進行複雜的日期計算（已移交給 LLM）。
    """
    return str(date_str).replace("週", "周").replace("禮拜", "周").replace("拜", "周")

def global_time_interceptor(extracted_args: dict, reference_date: datetime = None) -> dict:
    """
    時間攔截器：優先信任 YYYY-MM-DD，其餘交給 dateparser。
    """
    if not reference_date: reference_date = datetime.now()
    if 'date' in extracted_args:
        raw = extracted_args['date']
        dates = raw if isinstance(raw, list) else [raw]
        res = []
        for d in dates:
            if not d: continue
            d_str = str(d).strip()
            
            # 1. 優先匹配標準格式 (LLM 產出的預期格式)
            if re.match(r"^\d{4}-\d{2}-\d{2}$", d_str):
                res.append(d_str)
                continue
            
            # 匹配月份格式 YYYY-MM，直接保留，不讓 dateparser 補位
            if re.match(r"^\d{4}-\d{2}$", d_str):
                res.append(d_str)
                continue
            
            # 2. 口語正規化後交給 dateparser
            pre = preprocess_taiwan_dates(d_str, reference_date)
            parsed = dateparser.parse(
                pre, 
                settings={
                    'RELATIVE_BASE': reference_date, 
                    'PREFER_DATES_FROM': 'future', 
                    'TIMEZONE': 'Asia/Taipei',
                    'RETURN_AS_TIMEZONE_AWARE': False
                }
            )
            if parsed:
                res.append(parsed.strftime('%Y-%m-%d'))
            else:
                # 3. 如果包含月份等模糊詞且無法解析，保留原文交給後續的 expand_fuzzy_dates 處理
                if any(kw in d_str for kw in ["月", "年", "本", "下", "上"]):
                    res.append(d_str)
                else:
                    print(f"[Time Interceptor] 無法解析日期: {d_str}")
                    # 不拋出錯誤，讓它維持原樣嘗試進入下一步，或由 LLM 在下一輪修正
                    res.append(d_str)

        extracted_args['date'] = res if isinstance(raw, list) else (res[0] if res else None)
    return extracted_args
