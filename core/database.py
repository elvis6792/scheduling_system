from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings

# 建立支援非同步的 SQLAlchemy Engine，關閉 echo 避免 Log 轟炸
engine = create_async_engine(
    settings.database_url,
    echo=False
)

# 設定 Session 工廠，關閉 expire_on_commit 以支援跨 async 呼叫的物件存取
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db():
    """
    FastAPI 專用的依賴注入生成器。
    確保每個 Request 都有獨立的 Session，且必定會被正確關閉。
    """
    async with AsyncSessionLocal() as session:
        yield session
