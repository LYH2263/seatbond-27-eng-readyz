import threading

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _connect_args(timeout: float) -> dict:
    # 就绪探针需要有界的建连等待，避免数据库不可达时长时间挂起。
    if settings.database_url.startswith("postgresql"):
        return {"connect_timeout": max(1, int(timeout))}
    return {}


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.readiness_timeout_seconds),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 探针专用引擎：NullPool 保证每次探测使用独立短连接，
# 超时残留的连接不会长期占用业务连接池。
probe_engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args=_connect_args(settings.readiness_timeout_seconds),
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseUnavailable(RuntimeError):
    """数据库不可用（连接失败或探测超时）。"""


def ping_database(timeout: float | None = None) -> None:
    """对数据库做一次只读轻量探测（SELECT 1），失败抛 DatabaseUnavailable。

    在独立短连接上执行，并以独立线程加硬超时；不建表、不持座、不写业务表。
    """
    timeout = settings.readiness_timeout_seconds if timeout is None else timeout
    outcome: dict = {}

    def _probe() -> None:
        try:
            with probe_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # DBAPI/驱动错误统一归为不可用
            outcome["error"] = exc

    worker = threading.Thread(target=_probe, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise DatabaseUnavailable(f"database probe timed out after {timeout:g}s")
    error = outcome.get("error")
    if error is not None:
        # 取错误首行，保留简要原因，避免驱动堆栈噪音进入响应正文
        reason = str(error).strip().splitlines()[0] if str(error).strip() else repr(error)
        raise DatabaseUnavailable(reason) from error
