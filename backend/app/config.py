from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str = "postgresql+psycopg2://seatbond:seatbond@localhost:5442/seatbond"
    seed_on_empty: bool = True
    # /api/readyz 数据库探测的硬超时（秒），含建连与查询
    readiness_timeout_seconds: float = 2.0


settings = Settings()
