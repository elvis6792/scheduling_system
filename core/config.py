from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM 配置 (支援 OpenAI 或本地推論伺服器)
    openai_api_key: str = ""
    llm_api_key: str = "sk-local-dummy-key"
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "qwen2.5-coder-14b-instruct-q5_0.gguf"
    
    # 資料庫配置
    database_url: str = "sqlite+aiosqlite:///./data/scheduling.db"
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
