"""探针测试：health 仅表存活，readyz 额外要求数据库可连接。

用测试替身（fake engine / fake ping）模拟数据库连接失败与无响应超时，
不依赖真实 Postgres。
"""
import threading
import time

import pytest
from fastapi.testclient import TestClient

import app.database as db_mod
from app.api import router as router_mod
from app.database import DatabaseUnavailable, ping_database
from app.main import app

client = TestClient(app)


# ---- HTTP 层：/api/health 与 /api/readyz 语义区分 ----


def test_health_is_liveness_only():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_ready_when_database_reachable(monkeypatch):
    monkeypatch.setattr(router_mod, "ping_database", lambda: None)
    resp = client.get("/api/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_readyz_not_ready_on_connection_failure_but_health_still_ok(monkeypatch):
    """替身模拟连接失败：readyz 必须 503，存活探针仍 200。"""

    def fake_ping():
        raise DatabaseUnavailable("connection refused (simulated)")

    monkeypatch.setattr(router_mod, "ping_database", fake_ping)

    ready = client.get("/api/readyz")
    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "not_ready"
    assert "connection refused" in body["reason"]

    # 进程仍在响应，不能因为数据库挂了把存活探针判失败
    alive = client.get("/api/health")
    assert alive.status_code == 200
    assert alive.json() == {"status": "ok"}


def test_readyz_not_ready_on_timeout_but_health_still_ok(monkeypatch):
    """替身模拟探测超时：readyz 必须 503，存活探针仍 200。"""

    def fake_ping():
        raise DatabaseUnavailable("database probe timed out after 2s (simulated)")

    monkeypatch.setattr(router_mod, "ping_database", fake_ping)

    ready = client.get("/api/readyz")
    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "not_ready"
    assert "timed out" in body["reason"]

    assert client.get("/api/health").status_code == 200


# ---- 探测函数层：用假 engine 验证真实的超时/错误处理 ----


class _FailingEngine:
    """模拟数据库连接立即失败。"""

    def connect(self):
        raise RuntimeError("connection refused (simulated)")


class _StuckConnection:
    def __enter__(self):
        # 模拟数据库 TCP 可连但不响应，阻塞时间远超探测超时
        threading.Event().wait(5)
        return self

    def __exit__(self, *exc):
        return False


class _StuckEngine:
    def connect(self):
        return _StuckConnection()


def test_ping_database_raises_when_connection_fails(monkeypatch):
    monkeypatch.setattr(db_mod, "probe_engine", _FailingEngine())
    with pytest.raises(DatabaseUnavailable, match="connection refused"):
        ping_database(timeout=1)


def test_ping_database_raises_when_probe_hangs(monkeypatch):
    monkeypatch.setattr(db_mod, "probe_engine", _StuckEngine())
    start = time.monotonic()
    with pytest.raises(DatabaseUnavailable, match="timed out"):
        ping_database(timeout=0.2)
    # 必须在超时附近返回，而不是等到假连接的 5 秒结束
    assert time.monotonic() - start < 1.0
