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

## 探针（健康检查）

| 探针 | 路径 | 语义 | 成功响应 | 失败响应 |
| --- | --- | --- | --- | --- |
| 存活探针 | `GET /api/health` | 仅表示进程存活，不触碰数据库 | `200 {"status":"ok"}` | 进程不可用即无响应 |
| 就绪探针 | `GET /api/readyz` | 进程存活 **且** 数据库可连接（只读 `SELECT 1`，带超时） | `200 {"status":"ready"}` | `503 {"status":"not_ready","reason":"db_unreachable"}` 或 `{"status":"not_ready","reason":"db_timeout"}` |

- 编排时 liveness 用 `/api/health`、readiness 用 `/api/readyz`，避免「进程在、库挂了」仍被接入流量。
- 两探针均为只读探测：不创建持座、不写业务表。
- 就绪探测超时时间由环境变量 `READYZ_TIMEOUT_SECONDS` 控制（默认 `1.0` 秒）。

手动验证（可重复步骤）：

```bash
# 数据库正常时
curl -i http://localhost:9100/api/readyz   # 200 {"status":"ready"}

# 停掉数据库模拟故障
docker compose stop db
curl -i http://localhost:9100/api/readyz   # 503 {"status":"not_ready","reason":"db_unreachable"}
curl -i http://localhost:9100/api/health   # 200 {"status":"ok"}，存活探针不受影响
docker compose start db
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
