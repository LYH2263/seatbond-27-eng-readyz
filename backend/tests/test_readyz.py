"""就绪/存活探针测试。

不依赖真实数据库：TestClient 不进入上下文管理器即不执行 lifespan
（不建表、不连库），readyz 的数据库探测通过 dependency_overrides 替换为替身。
"""

import threading

import pytest
from fastapi.testclient import TestClient

from app.api.router import get_readiness_probe
from app.main import app
from app.services import healthcheck
from app.services.healthcheck import DbProbeTimeout


@pytest.fixture
def client():
    # 不使用 with => 不触发 lifespan，全程不接触真实数据库
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_probe(probe):
    app.dependency_overrides[get_readiness_probe] = lambda: probe


def test_health_liveness_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_ok_when_db_probe_passes(client):
    _override_probe(lambda: None)
    resp = client.get("/api/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_readyz_fails_when_db_unreachable(client):
    def refuse():
        raise ConnectionError("connection refused")

    _override_probe(refuse)
    resp = client.get("/api/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "db_unreachable"


def test_readyz_fails_when_db_probe_times_out(client):
    def slow():
        raise DbProbeTimeout("数据库探测超时")

    _override_probe(slow)
    resp = client.get("/api/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "db_timeout"


def test_liveness_still_ok_when_readyz_fails(client):
    def refuse():
        raise ConnectionError("connection refused")

    _override_probe(refuse)
    assert client.get("/api/readyz").status_code == 503
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_probe_database_times_out_on_hanging_db(monkeypatch):
    release = threading.Event()

    def hang():
        release.wait(timeout=10)

    monkeypatch.setattr(healthcheck, "_select_one", hang)
    try:
        with pytest.raises(DbProbeTimeout):
            healthcheck.probe_database(timeout_seconds=0.05)
    finally:
        release.set()  # 释放后台线程，避免拖慢测试进程退出


def test_probe_database_propagates_connection_error(monkeypatch):
    def refuse():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(healthcheck, "_select_one", refuse)
    with pytest.raises(ConnectionError):
        healthcheck.probe_database(timeout_seconds=1.0)
