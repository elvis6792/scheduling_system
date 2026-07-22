import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.v1.auth import router as auth_router
from app.api.v1.admin_mgmt import router as admin_router
from app.api.v1.scheduling import router as scheduling_router
from app.api.v1.system import router as system_router
from app.api.v1.line import router as line_router
from app.core.tasks import sync_disaster_leave_job, cleanup_chat_history_job
from app.api.v1.scheduling import orchestrator
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在啟動排班系統主服務...")
    
    app.state.agent = orchestrator
    logger.info("Agent Orchestrator loaded.")
    
    scheduler = AsyncIOScheduler(timezone="Asia/Taipei")
    
    scheduler.add_job(
        sync_disaster_leave_job,
        trigger=CronTrigger(hour="21", minute="0"),
        id="typhoon_watcher_task",
        name="觀測人事行政總處明日防災假並全自動排休",
        replace_existing=True
    )

    scheduler.add_job(
        cleanup_chat_history_job,
        trigger=CronTrigger(hour="3", minute="0"), # 每天凌晨 3 點執行
        id="cleanup_chat_history_task",
        name="定期清理對話紀錄 (保留一個月)",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("[背景排程調度器] 已啟動。")
    
    app.state.scheduler = scheduler

    yield 

    logger.info("正在關閉排班系統主服務...")
    scheduler.shutdown(wait=True)
    logger.info("服務已卸載。")


app = FastAPI(
    title="AI排班系統",
    version="2.5.0-Proactive",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router, prefix="/api/v1", tags=["Auth 身份驗證"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin 組織管理"])
app.include_router(scheduling_router, prefix="/api/v1", tags=["Scheduling 排班引擎"])
app.include_router(system_router, prefix="/api/v1", tags=["System 系統功能"])
app.include_router(line_router, prefix="/api/v1", tags=["LINE Integration"])


@app.get("/")
def root():
    return {"message": "Scheduling system backend server is running normally."}
