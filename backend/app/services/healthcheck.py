"""数据库就绪探测：轻量只读查询，带硬超时，供 /api/readyz 使用。"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from sqlalchemy import text

from app.database import engine


class DbProbeTimeout(Exception):
    """数据库探测在限定时间内未返回。"""


def _select_one() -> None:
    """只读探测语句：仅验证连接可用，不建表、不创建持座、不写业务表。"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def probe_database(timeout_seconds: float) -> None:
    """在独立线程中执行只读探测并限时返回。

    - 超时抛出 DbProbeTimeout；
    - 连接失败等底层异常原样向上抛；
    - 超时后工作线程在后台自行结束，不阻塞探针响应。
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_select_one)
        future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise DbProbeTimeout(f"数据库探测超过 {timeout_seconds:.2f}s 未返回") from exc
    finally:
        pool.shutdown(wait=False)
