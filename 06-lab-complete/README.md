# Part 6 — Final Project: Production-ready AI Agent

Agent trong thư mục này kết hợp cấu hình qua biến môi trường, API key, rate limit và ngân sách trong Redis, structured logging, health/readiness và graceful shutdown. Theo dõi kết quả kiểm tra trong [MISSION_ANSWERS.md](../MISSION_ANSWERS.md).

Bài chỉ được tính hoàn thành khi script chấm báo **`PASS 12/12`**:

```bash
pip install -r requirements.txt
python check_production_ready.py
```

---

## Checklist Deliverable

- [ ] Dockerfile (multi-stage, < 500 MB)
- [ ] docker-compose.yml (agent + redis)
- [ ] .dockerignore
- [ ] Health check endpoint (`GET /health`)
- [ ] Readiness endpoint (`GET /ready`)
- [ ] API Key authentication
- [ ] Rate limiting
- [ ] Cost guard
- [ ] Config từ environment variables
- [ ] Structured logging
- [ ] Graceful shutdown
- [ ] Public URL ready (Railway / Render config)

---

## Script chấm dựa vào những tiêu chí dưới đây

Script tự khởi động agent của bạn, gọi API thật, build và chạy Docker image. Để chấm được, agent phải tuân theo các quy ước sau:

| Hạng mục | Yêu cầu |
|----------|---------|
| Điểm vào | `app/main.py` có biến `app` (FastAPI), chạy được bằng `uvicorn app.main:app --workers 2` từ thư mục này |
| `GET /health` | Luôn trả **200** khi process còn chạy, kể cả khi Redis chưa kết nối được |
| `GET /ready` | **200** khi sẵn sàng; **503** khi Redis (`REDIS_URL`) không kết nối được |
| `POST /ask` | Body JSON `{"question": "..."}` (được phép có thêm `user_id`) → **200** |
| API key | Header `X-API-Key` phải trùng biến `AGENT_API_KEY`; thiếu hoặc sai → **401** |
| Rate limit | Tối đa `RATE_LIMIT_PER_MINUTE` request / 60 giây cho mỗi API key; vượt → **429** (nên có header `Retry-After`). State lưu trong **Redis**, vẫn còn sau khi restart agent |
| Cost guard | Tổng chi phí vượt `DAILY_BUDGET_USD` (hoặc `MONTHLY_BUDGET_USD`) → **402** |
| Biến môi trường | Đọc từ env: `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`, `PORT`, `ENVIRONMENT`. Liệt kê đủ trong `.env.example`. Script chạy với `ENVIRONMENT=staging` |
| Log | Mỗi dòng log của app là **1 JSON object hợp lệ** (log của uvicorn không tính) |
| Graceful shutdown | Nhận SIGTERM khi đang có request → request đó vẫn trả 200, process tự thoát với exit code 0. Trong Docker, `docker stop` phải xong trong < 10 giây |
| Docker image | Multi-stage, base slim, user non-root, có `HEALTHCHECK`, < 500 MB. `CMD` lắng nghe theo biến `PORT` (mặc định 8000), uvicorn là PID 1. Container khởi động được khi **không có** Redis |
| Compose | Một service build từ `Dockerfile` + một service dùng image `redis:*`; agent có `REDIS_URL` trỏ tới service Redis và `depends_on` nó |
| `.dockerignore` | Loại trừ `.env`, `__pycache__`, `venv` |
| Deploy config | `railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`) **hoặc** `render.yaml` (`type: web`, `healthCheckPath: /health`, secret dùng `generateValue` / `sync: false`) |

---

## Cấu trúc code

```
06-lab-complete/
├── app/
│   ├── main.py           # Route, middleware log JSON và lifespan
│   ├── config.py         # Đọc cấu hình từ biến môi trường
│   ├── auth.py           # Kiểm tra X-API-Key
│   ├── rate_limiter.py   # Sliding window dùng Redis
│   ├── cost_guard.py     # Kiểm tra và ghi chi phí theo ngày UTC
│   └── redis_client.py   # Client Redis và health check cho /ready
├── utils/mock_llm.py     # Mock LLM — có sẵn, không cần sửa
├── Dockerfile            # Multi-stage, non-root, PORT động
├── docker-compose.yml    # Agent + Redis có volume
├── .dockerignore         # Bỏ secret, cache và code Part 7
├── .env.example          # Danh sách biến môi trường
├── railway.toml          # Cấu hình theo yêu cầu lab
├── render.yaml           # Blueprint gói Free gồm web và Key Value
├── requirements.txt      # Có sẵn
├── check_production_ready.py   # Script chấm — không sửa
└── benchmark-observability/    # Part 7 — làm sau khi xong Part 6
```

Các worker dùng chung sliding window 60 giây theo API key và budget theo môi trường trong Redis. Cost guard kiểm tra tổng chi phí đã ghi trước khi gọi mock LLM và ghi chi phí ước tính sau khi có câu trả lời. Các request đồng thời đã được chấp nhận có thể hoàn tất sau thời điểm chạm ngưỡng.

---

## Chạy local

```bash
cp .env.example .env
# Điền AGENT_API_KEY do bạn tự đặt vào .env.

# Chạy cả agent + Redis
docker compose -p k5-day14-final up -d --build

curl http://localhost:8000/health
curl http://localhost:8000/ready
read -r -s -p 'AGENT_API_KEY đã đặt trong .env: ' AGENT_API_KEY
printf '\n'
curl -X POST http://localhost:8000/ask \
     -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
     -d '{"question": "What is deployment?"}'
unset AGENT_API_KEY
```

Nếu Redis đã chạy riêng, cài `pip install -r requirements.txt` rồi dùng `uvicorn app.main:app --env-file .env --port 8000 --workers 2`. Với Compose, `PORT` mặc định là 8000 và `REDIS_URL` được đặt theo tên service `redis`.

---

## Chấm bài

```bash
python check_production_ready.py                 # chấm đầy đủ — cần Docker đang chạy
python check_production_ready.py --skip-docker   # chế độ nhanh khi đang làm (bỏ build image)
python check_production_ready.py --static-only   # chỉ đọc file, không chạy agent
python check_production_ready.py --public-url https://day14-agent-ubeq.onrender.com
```

- Kết quả in theo từng tiêu chí: ✅ đạt · ❌ chưa đạt · ⚠️ chưa kiểm tra được.
- **Chỉ PASS khi cả 12 tiêu chí ✅.** Mục ⚠️ (vd máy chưa bật Docker) cũng tính là chưa đạt, nên khi nộp bài phải chạy chế độ đầy đủ.
- Lần đầu chạy, script build Docker image nên mất vài phút. Bài test stateless cần Redis: script dùng `REDIS_URL` nếu có, không thì tự bật container `redis:7-alpine` tạm thời.

---

## Deploy

Cấu hình Render, URL public và kết quả xác minh nằm trong [DEPLOYMENT.md](../DEPLOYMENT.md).

---

## Part 7 — Benchmark & Observability

Agent đã chạy được, bước tiếp theo là đo xem nó **nhanh** và **đúng** tới đâu, rồi **giám sát** khi chạy thật:

```bash
cd benchmark-observability
```

| Thư mục | Nội dung |
|---------|----------|
| `develop/` | Agent có `/metrics`, load test (p50/p95/p99, SLO), eval trên golden dataset + quality gate |
| `production/` | Docker Compose: agent x2 + Nginx + Prometheus + Grafana + Jaeger + Locust, 4 alert rules |

Hướng dẫn đầy đủ: [benchmark-observability/README.md](benchmark-observability/README.md). Nộp kèm `BENCHMARK_REPORT.md` theo [mẫu](benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md).
