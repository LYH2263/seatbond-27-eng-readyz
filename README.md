# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |
| API 文档 | http://localhost:9100/docs |
| Postgres | localhost:5442 |

健康检查：见下节「探针」。

## 探针（liveness / readiness）

服务区分存活探针与就绪探针，编排平台应分别配置，避免「进程在、库挂了」时仍把流量打进来：

| 路径 | 语义 | 检查内容 |
| --- | --- | --- |
| `GET /api/health` | 存活探针（liveness） | 仅表示进程能响应 HTTP，**不**检查数据库。失败才重启实例。 |
| `GET /api/readyz` | 就绪探针（readiness） | 进程存活 **且** 数据库可连接（只读 `SELECT 1`，带超时）。失败只摘流量、不重启。 |

就绪探针只做只读探测：不建表、不创建持座、不写任何业务表；数据库不可用或探测超过
`READINESS_TIMEOUT_SECONDS`（默认 2 秒）时返回非就绪状态码。

**就绪（HTTP 200）**

```json
{"status": "ready", "checks": {"database": "ok"}}
```

**未就绪（HTTP 503，数据库不可达或探测超时）**

```json
{"status": "not_ready", "reason": "database unavailable: ..."}
```

`status` 为稳定字段（`ready` / `not_ready`），`reason` 为简要原因文本，仅供排障，勿据此字段做逻辑判断。

示例：

```bash
curl -i http://localhost:9100/api/health   # 只要进程在恒为 200
curl -i http://localhost:9100/api/readyz   # 数据库挂掉或超时时为 503
```

## 页面

- `/halls` — 影厅
- `/showtimes` — 场次
- `/seatmap` — 座位图（大网格热力）
- `/hold` — 锁座
- `/orders` — 订单
- `/conflicts` — 冲突

## 使用说明

1. 在影厅与场次页确认厅图与排期。
2. 打开座位图查看占用热力，在锁座页输入连座人数并提交。
3. 订单页查看持座结果；冲突页查看重叠请求。

## 开发与测试

```bash
docker compose exec api pytest -q
```
