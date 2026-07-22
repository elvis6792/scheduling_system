from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 建立支援非同步的 SQLAlchemy Engine
engine = create_async_engine(
    settings.database_url,
    echo=False
)

# 修正 1：將名稱從 AsyncSessionLocal 改為 async_session_maker，對齊 scheduling.py 的需求
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 修正 2：將名稱從 get_db 改為 get_session，對齊所有 Router (auth, admin_mgmt) 的 Depends
async def get_session():
    """
    FastAPI 專用的依賴注入生成器。
    確保每個 Request 都有獨立的 Session，且必定會被正確關閉。
    """
    async with async_session_maker() as session:
        yield session
