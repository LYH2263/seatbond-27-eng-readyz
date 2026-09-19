from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str = "postgresql+psycopg2://seatbond:seatbond@localhost:5442/seatbond"
    seed_on_empty: bool = True
    # 就绪探针数据库探测的硬超时（秒），超时视为不就绪
    readyz_timeout_seconds: float = 1.0


settings = Settings()
