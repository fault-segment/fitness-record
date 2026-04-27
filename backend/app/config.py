from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    tidb_host: str = "127.0.0.1"
    tidb_port: int = 4000
    tidb_user: str = "root"
    tidb_password: str = ""
    tidb_database: str = "diet_recorder"
    tidb_ca_path: str = ""
    wechat_appid: str = ""
    wechat_secret: str = ""
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    bge_model_path: str = "data/bge-small-zh-v1.5"  # 本地路径，留空则从 HuggingFace 下载


settings = Settings()
