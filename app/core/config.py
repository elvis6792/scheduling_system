import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # LLM 配置 (支援 OpenAI 或本地推論伺服器)
    openai_api_key: str = ""
    llm_api_key: str = "sk-local-dummy-key"
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "qwen2.5-coder-14b-instruct-q5_0.gguf"
    
    # 資料庫配置
    database_url: str = "sqlite+aiosqlite:///./data/scheduling.db"
    
    # JWT 安全金鑰與演算法
    SECRET_KEY: str = "your_super_secret_key_change_me"
    ALGORITHM: str = "HS256"

    # CORS 跨來源資源共享
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://0.0.0.0:5173",
        "*" # 開放給區網內所有裝置測試
    ]

    # LINE Integration
    LINE_CHANNEL_SECRET: str = ""
    LINE_CHANNEL_ACCESS_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
