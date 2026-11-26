# Benchmark & Observability Report — Day 14

**Họ tên:** Đinh Lê Thịnh, 2A202603953  
**Ngày chạy:** 26/11/2026 (GMT+7)  
**Môi trường:** Windows, Docker Desktop với Linux engine trên WSL2, 16 CPU và 7.41 GiB RAM báo bởi Docker Engine, Python 3.11 trong container.

## 1. SLO của agent

| SLI | SLO | Lý do |
| --- | --- | --- |
| p95 latency `POST /ask` | ≤ 500 ms | Giới hạn thời gian chờ của phần lớn lượt gọi theo mặc định của load test local. |
| Error rate `POST /ask` | ≤ 2% | Giới hạn tỷ lệ lỗi, gồm mã HTTP khác 200 và lỗi kết nối. |
| Accuracy trên golden dataset | ≥ 85% ở CI, 100% cho lần kiểm cuối | Đặt ngưỡng tối thiểu khi review PR và dùng baseline để bắt case từng đúng nay sai. |

## 2. Benchmark hiệu năng

### 2.1 Concurrency vs latency

Agent v2 sau khi bổ sung KB, 300 request mỗi lượt. Giữ `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Latency trong JSON tính trên response 200.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO | File |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 4.47 | 191.1 | 217.9 | 1698.0 | 1.33% | PASS | [JSON](reports/load_v2_c1.json) |
| 10 | 39.65 | 189.9 | 223.0 | 1678.7 | 1.00% | PASS | [JSON](reports/load_v2_c10.json) |
| 50 | 106.19 | 238.3 | 890.7 | 1689.2 | 1.67% | FAIL p95 | [JSON](reports/load_v2_c50.json) |
| 100 | 41.36 | 1067.6 | 5117.1 | 5466.2 | 1.67% | FAIL p95 | [JSON](reports/load_v2_c100.json) |

RPS tăng từ 4.47 lên 106.19 đến concurrency 50 rồi giảm ở 100. Ở mức 100, p50 vượt 1 giây và p95 vượt 5 giây, phù hợp với việc client và agent tranh CPU hoặc chờ xử lý khi cùng chạy trong một container. Cần đo riêng CPU, event loop và chờ kết nối để xác định nguyên nhân của lần chạy này. Trong các mức đã thử, 10 là mức cao nhất vẫn đạt cả hai SLO.

### 2.2 Tail latency

300 request mỗi lượt, concurrency 20. Khởi động lại v2 sau mỗi lần đổi `MOCK_SLOW_RATE`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) | File |
| ---: | ---: | ---: | ---: | --- |
| 0 | 193.2 | 223.6 | 243.0 | [JSON](reports/load_v2_slow_0.json) |
| 0.03 | 247.9 | 250.4 | 1715.5 | [JSON](reports/load_v2_slow_0.03.json) |
| 0.1 | 358.0 | 1692.9 | 1713.1 | [JSON](reports/load_v2_slow_0.1.json) |

p99 bắt được nhóm chậm ngay ở 3%, khi p95 chỉ tăng từ 223.6 lên 250.4 ms. Ở mức 10%, nhóm chậm chiếm đủ tỷ trọng để kéo p95 lên 1692.9 ms. Average gộp các lượt nhanh/chậm nên mức tăng 193.2 → 358.0 ms có thể che trải nghiệm chờ trên 1.6 giây. Dùng p95 làm SLO và quan sát thêm p99 để phát hiện nhóm đuôi nhỏ hơn.

### 2.3 Exercise 7.1 — Đọc metrics

Sau eval và một request kiểm tra, scrape trực tiếp agent v2 cho các dòng sau. Số đếm tính từ khi process v2 được khởi động lại cho lượt eval cuối.

```text
http_requests_total{method="POST",route="/ask",status="200"} 24.0
agent_in_flight_requests 0.0
agent_question_length_chars_count 24.0
```

`http_requests_total` là Counter. `agent_in_flight_requests` là Gauge đo số request đang xử lý lúc scrape. `agent_question_length_chars` là Histogram đo độ dài câu hỏi bằng bucket cố định, kèm `_count` và `_sum`. Gán URL lạ vào label sẽ tạo một time series cho mỗi biến thể. Dùng route template và nhóm `unmatched` giữ cardinality thấp.

## 3. Benchmark chất lượng

Tắt lỗi upstream giả lập cho các lượt eval (`MOCK_ERROR_RATE=0`) để đo retrieval và chất lượng câu trả lời. Trước và sau dùng chung golden dataset.

| Chỉ số | [Agent v1](reports/eval_v1.json) | [Agent v2](reports/eval_v2.json) | [Agent v2 sau sửa KB](reports/eval_v2_fixed.json) |
| --- | ---: | ---: | ---: |
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.4 | 109.1 | 114.2 |
| Tổng cost (USD) | 0.000408 | 0.000762 | 0.000795 |
| Cost / câu đúng (USD) | 0.00040815 | 0.00003627 | 0.00003456 |
| p95 (ms) | 188.3 | 216.4 | 213.0 |
| Quality gate | FAIL (80%) | PASS (80%) | PASS (100%, 0 regression) |

| ID | Keyword thiếu trước khi sửa | Tài liệu bổ sung |
| --- | --- | --- |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Giải thích API key và cách JWT mang thông tin, được xác minh chữ ký và thời hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Giải thích Kubernetes HPA điều chỉnh số pod theo tài nguyên và custom metrics. |

Retrieval tăng token trung bình và chi phí tổng, đồng thời giảm chi phí trên mỗi câu đúng vì số câu đạt tăng từ 1 lên 23. p95 của lượt v2 trước/sau chênh 3.4 ms và jitter mô phỏng thay đổi giữa các lượt, nên chênh lệch này cần chạy lặp mới có thể gán cho thay đổi KB.

**Quality gate trên CI.** Job PR khởi động agent v2 với `MOCK_ERROR_RATE=0`, chờ `/health`, rồi chạy `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.85 --baseline <json-baseline>`. Dùng JSON từ lần đo của nhánh đích làm baseline. Exit code 1 làm job fail khi accuracy dưới ngưỡng hoặc một case baseline bị regression. Đặt job làm required status check để chặn merge.

## 4. Observability stack

### 4.1 Grafana, Jaeger và Prometheus

| Bằng chứng | Nội dung |
| --- | --- |
| [Grafana tải 100 user](screenshots/grafana-dashboard.png) | 3 instance up, 61.9 req/s, error rate 1.12%, p95 292.45 ms, 14 request đang xử lý tại lần chụp. |
| [Jaeger trace chậm](screenshots/jaeger-slow-trace.png) | `POST /ask` khoảng 1.71 giây, span gọi mock LLM chiếm phần lớn thời gian. |
| [Jaeger trace lỗi](screenshots/jaeger-error-trace.png) | `POST /ask` trả 503 và span gọi mock LLM ghi event `exception`. |
| [Prometheus Alerts](screenshots/prometheus-alert-firing.png) | `AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing. |

Truy vấn tức thời qua Prometheus trên cửa sổ 30 giây gần thời điểm chụp cho p95 **291.98 ms** và avg **220.04 ms**. Chênh lệch cho thấy một phần request kéo dài hơn mức trung bình, phù hợp với p99 cao trong đồ thị. Ba instance xử lý lần lượt **21.36**, **20.08** và **20.64 req/s**, tương đối đều qua Nginx. API Prometheus trả **4768.08 input tokens/s** và **2499.08 output tokens/s**. Input chứa system prompt, câu hỏi và tài liệu retrieval. Panel Tokens/s vẽ các chuỗi chồng lên nhau nên đường trên cùng biểu diễn tổng.

`GET /metrics` qua Nginx trả 404 vì proxy chỉ công bố các endpoint phục vụ client. Prometheus scrape từng agent qua mạng Compose. `promtool test rules` đã trả `SUCCESS`.

### 4.2 Thí nghiệm

Mỗi thí nghiệm dùng 3 replica, 30 user với ramp-up 5 user/giây. Đo từ lúc áp dụng Compose với biến mới đến lần đầu API Prometheus báo `firing`, truy vấn khoảng mỗi 2 giây.

| Thí nghiệm | Thay đổi | Cảnh báo quan sát được | Thời gian | Panel phản ánh rõ |
| --- | --- | --- | ---: | --- |
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 100 giây | Error rate. Locust ghi 358/1930 request `/ask` lỗi (18.55%). |
| B | Thêm `MOCK_SLOW_RATE=0.3`, giữ lỗi 0.2 | `AgentHighLatencyP95`. Cảnh báo lỗi vẫn firing khi chụp ảnh. | 152 giây cho cảnh báo p95 | Latency p95. Locust ghi p95 `/ask` 1700 ms. |

Rule lỗi yêu cầu tỷ lệ 5xx vượt 5% trong 1 phút, rule latency yêu cầu p95 vượt 1 giây trong 2 phút. Từ lúc đổi biến, kết quả đo còn bao gồm thời gian thay container, khôi phục traffic và đủ mẫu để vượt ngưỡng. Giữ cấu hình lỗi ở bước B giúp chụp cả hai cảnh báo cùng trạng thái firing.

Hạ `AGENT_VERSION` xuống v1 có thể giảm accuracy trong khi error rate và latency vẫn đạt ngưỡng. Dùng quality gate trước deploy, chạy golden dataset định kỳ hoặc canary và theo dõi accuracy theo phiên bản cùng tín hiệu phản hồi người dùng.

### 4.3 Đối chiếu log và trace

Trace chậm `4444ecc40dfbbf54d3fa22e21d0a001b` có thời gian toàn request **1714.323 ms**. Span xử lý LLM `chat mock-llm-small` mất **1695.978 ms**, tức **98.93%** tổng thời gian. Dòng log dưới đây được đối chiếu với ID từ Jaeger.

```json
{"ts":"2026-11-26T07:43:07.424214+00:00","level":"INFO","service":"observable-agent","instance":"62f3bb04b578","event":"llm_call","trace_id":"4444ecc40dfbbf54d3fa22e21d0a001b","span_id":"8dd2a27fd3a4e19f","request_id":"6eb114fe3200","model":"mock-llm-small","agent_version":"v2","input_tokens":81,"output_tokens":46,"cost_usd":0.00004,"llm_ms":1695.6}
```

Trace lỗi `355cc7cc6e5280d7cf44d87094fc7ea2` có HTTP 503 và thời gian toàn request **112.626 ms**. Span `chat mock-llm-small` mất **87.067 ms** và ghi event `exception` loại `utils.mock_llm.LLMError`.

```json
{"ts":"2026-11-26T07:43:10.270015+00:00","level":"INFO","service":"observable-agent","instance":"72f78768c027","event":"llm_error","trace_id":"355cc7cc6e5280d7cf44d87094fc7ea2","span_id":"f5d767cc02916c25","request_id":"09bc2ca3b968","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

Locust headless chạy cùng kịch bản 100 user, spawn rate 10 user/giây, 2 phút cho mỗi mức 1 và 3 replica. Dùng `--no-deps` để Locust giữ đúng số replica và lấy dòng `POST /ask` của hai CSV.

| Replica | Requests | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | CSV |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 7043 | 59.27 | 200 | 500 | 1700 | 74 (1.05%) | [scale_1](benchmark-results/scale_1_stats.csv) |
| 3 | 7119 | 59.88 | 200 | 240 | 1700 | 77 (1.08%) | [scale_3](benchmark-results/scale_3_stats.csv) |

p95 giảm **52%** trong lượt đo, p50 giữ 200 ms và p99 giữ 1700 ms. Throughput chỉ tăng khoảng **1%** vì kịch bản giữ số user và thời gian nghỉ giữa lượt cố định. Các lượt mock cố ý cộng độ trễ vẫn chi phối p99 dù có thêm replica. Kết quả cho thấy lợi ích ở p95 của lần đo, chưa xác định được thông lượng tối đa của hệ thống.

## 6. Kết luận

1. p99 cho thấy nhóm request chậm khi p95 và average còn gần mức bình thường.
2. Accuracy và cost trên mỗi câu đúng cho thấy tác động của retrieval lên chất lượng, kể cả khi tổng chi phí tăng.
3. Đặt alert theo triệu chứng người dùng thấy và dùng trace cùng `trace_id` để định vị bước chậm hoặc lỗi.

Trong production có thể bổ sung cảnh báo tỷ lệ retrieval miss theo phiên bản và tốc độ tiêu thụ error budget theo hai cửa sổ thời gian.
