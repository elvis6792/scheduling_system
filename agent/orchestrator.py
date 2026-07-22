from agent.runtime.state import AgentState
from agent.runtime.runtime import AgentRuntime
from agent.runtime.planner import Planner
from agent.runtime.memory import MemoryManager
from agent.runtime.recovery import RecoveryEngine
from agent.runtime.dispatcher import Dispatcher
from agent.runtime.validators import InputValidator, BusinessValidator
from agent.tools.registry import ToolRegistry
from agent.tools.implementations.cancel_shift import CancelShiftTool
from agent.tools.implementations.check_daily_status import CheckDailyStatusTool
from agent.tools.implementations.create_shift import CreateShiftTool
from agent.tools.implementations.register_leave import RegisterLeaveTool
from agent.tools.implementations.batch_check_daily_status import BatchCheckDailyStatus
from agent.tools.implementations.batch_create_shift import BatchCreateShift
from agent.tools.implementations.query_schedule import QuerySchedule
from agent.tools.implementations.swap_shift import SwapShiftTool # Placeholder for future implementation
from agent.tools.implementations.resolve_entity import EntityResolverTool
from agent.workers.shift_worker import ShiftWorker
from agent.workers.staff_worker import StaffWorker
from agent.prompts.builder import PromptBuilder
from agent.persistence.repository import SchedulingRepository
from agent.runtime.state import ExecutionContext

class SessionStore:
    def __init__(self):
        self._store: dict[str, ExecutionContext] = {}

    def get_or_create(self, context: dict) -> ExecutionContext:
        session_id = context["session_id"]
        if session_id not in self._store:
            self._store[session_id] = ExecutionContext(
                session_id=session_id,
                user_input="",
                state=AgentState.IDLE,
                user_id=context.get("user_id"),
                user_name=context.get("user_name"),
                role=context.get("role"),
                department_id=context.get("department_id"),
                staff_id=context.get("staff_id")
            )
        else:
            # 更新現有 Session 的使用者資訊，確保 user_id 等欄位同步
            exec_ctx = self._store[session_id]
            exec_ctx.user_id = context.get("user_id", exec_ctx.user_id)
            exec_ctx.user_name = context.get("user_name", exec_ctx.user_name)
            exec_ctx.role = context.get("role", exec_ctx.role)
            exec_ctx.department_id = context.get("department_id", exec_ctx.department_id)
            exec_ctx.staff_id = context.get("staff_id", exec_ctx.staff_id)

        return self._store[session_id]

    def save(self, context: ExecutionContext):
        self._store[context.session_id] = context
        
    def clear(self, session_id: str):
        if session_id in self._store:
            del self._store[session_id]

class AgentOrchestrator:
    def __init__(self, llm_client, async_session_maker):
        self.session_store = SessionStore()
        self.llm_client = llm_client
        self.async_session_maker = async_session_maker

        self.shift_worker = ShiftWorker(self.async_session_maker)
        self.staff_worker = StaffWorker(self.async_session_maker)

        self.tool_registry = ToolRegistry()
        
        self.tool_registry.register(CheckDailyStatusTool(self.async_session_maker))
        self.tool_registry.register(CancelShiftTool(self.async_session_maker))
        self.tool_registry.register(CreateShiftTool(self.async_session_maker))
        self.tool_registry.register(RegisterLeaveTool(self.async_session_maker))
        self.tool_registry.register(BatchCheckDailyStatus(self.async_session_maker))
        self.tool_registry.register(BatchCreateShift(self.async_session_maker))
        self.tool_registry.register(QuerySchedule(self.async_session_maker))
        self.tool_registry.register(SwapShiftTool(self.async_session_maker)) # Register SwapShiftTool once implemented
        self.tool_registry.register(EntityResolverTool(self.async_session_maker))

        self.dispatcher = Dispatcher()
        self.dispatcher.register_worker("shift_worker", self.shift_worker)
        self.dispatcher.register_worker("staff_worker", self.staff_worker)

        self.memory = MemoryManager()
        self.prompt_builder = PromptBuilder(self.tool_registry)
        self.planner = Planner(llm_client, self.prompt_builder, self.tool_registry)
        self.input_validator = InputValidator()
        
        # 不在此處提早實例化 Repository，直接將工廠 (db_session_maker) 傳入 Validator
        self.business_validator = BusinessValidator(self.async_session_maker)

        self.recovery = RecoveryEngine(max_retries=3)

        self.pending_context = None
        self.unprocessed_intents_queue = []

        self.runtime = AgentRuntime(
            planner=self.planner,
            tool_registry=self.tool_registry,
            dispatcher=self.dispatcher,
            memory_manager=self.memory,
            input_validator=self.input_validator,
            business_validator=self.business_validator,
            recovery_engine=self.recovery
        )

    async def chat(self, user_message: str, context: dict = None, **kwargs) -> str:
        if context is None:
            # 支援舊版直接傳入 session_id 的呼叫方式 (如 line.py 或 tasks.py)
            context = {
                "session_id": kwargs.get("session_id", "default_session"),
                "user_name": kwargs.get("user_name", "System"),
                "role": kwargs.get("role", "admin"),
                "department_id": kwargs.get("department_id"),
                "staff_id": kwargs.get("staff_id"),
                "user_id": kwargs.get("user_id")
            }

        exec_context = self.session_store.get_or_create(context)
        exec_context.user_input = user_message
        if exec_context.user_id:
            async with self.async_session_maker() as session:
                repo = SchedulingRepository(session)
                past_msgs = await repo.get_recent_chat_history(exec_context.user_id, limit=10)
                
                # 將歷史訊息注入 MemoryManager
                history_data = [
                    {"role": msg.role, "content": msg.content}
                    for msg in past_msgs
                ]
                self.memory.set_chat_history(history_data)

        # 2. 儲存使用者的話
        if exec_context.user_id:
            async with self.async_session_maker() as session:
                repo = SchedulingRepository(session)
                await repo.save_chat_message(exec_context.user_id, "user", user_message)
        
        print(f"\n[用戶 {exec_context.user_name} ({exec_context.session_id}) 說]: {user_message}")
        print(f"[當前狀態]: {exec_context.state.name}")

        # 4. 構建動態語義上下文 (Staff, Program 清單)
        system_context = {}
        async with self.async_session_maker() as session:
            from app.models.domain import Staff, Program, Department
            from sqlalchemy import select
            staff_list = (await session.execute(select(Staff.name))).scalars().all()
            prog_list = (await session.execute(select(Program.name))).scalars().all()
            dept_list = (await session.execute(select(Department.name))).scalars().all()
            system_context = {
                "staff_names": list(staff_list),
                "program_names": list(prog_list),
                "department_names": list(dept_list)
            }

        reply_message, updated_pending_context, self.unprocessed_intents_queue = await self.runtime.run(
            exec_context, 
            self.pending_context, 
            self.unprocessed_intents_queue,
            system_context=system_context # 傳入語義清單
        )
        self.pending_context = updated_pending_context

        # 3. 儲存 AI 的回覆
        if exec_context.user_id:
            async with self.async_session_maker() as session:
                repo = SchedulingRepository(session)
                await repo.save_chat_message(exec_context.user_id, "assistant", reply_message)
        
        # 狀態機執行完畢後的 Session 收尾與儲存
        
        # 狀態機執行完畢後的 Session 收尾與儲存
        if exec_context.state == AgentState.DONE:
            exec_context.state = AgentState.IDLE
            exec_context.retry_count = 0
            
            # 徹底清空上一回合的執行計畫與短期觀測，防止跨回合污染
            exec_context.current_plan = None
            if hasattr(exec_context, 'observations'):
                exec_context.observations.clear()
                
            self.session_store.save(exec_context)
            
        elif exec_context.state == AgentState.ASK_USER:
            self.session_store.save(exec_context)
        else:
            # 防禦未知的中斷狀態
            self.session_store.save(exec_context)

        return reply_message