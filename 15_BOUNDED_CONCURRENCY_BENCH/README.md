# 15 — Bounded concurrency benchmark: semaphore và in-flight

## Mục tiêu

Tự viết benchmark gửi `N` yêu cầu streaming với tối đa `C` yêu cầu đồng thời, đo thông lượng (requests/giây, tokens/giây) và phân bố độ trễ, đồng thời **chứng minh** rằng số yêu cầu đang bay không bao giờ vượt `C`. Bài tập rèn `asyncio.Semaphore`, chia sẻ client, xử lý lỗi cục bộ và kiểm thử tất định bằng transport giả.

## Giá trị học được

- Semaphore giới hạn **thời gian sống** của tác vụ, không chỉ lúc khởi tạo.
- Tạo một `AsyncClient` cho mỗi request (như nguồn) làm mất connection pooling; bài tập dùng client chia sẻ và đặt `Limits` phù hợp.
- `asyncio.gather` nuốt exception trừ khi xử lý; kết quả phải giữ thứ tự.
- Đo peak in-flight cần instrumentation, không suy từ wall time.
- Hủy đúng cách khi `Ctrl+C` để không để task treo.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Trung bình – Khó**.
- Thời lượng gợi ý: 5–6 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `httpx`, `pytest`, `pytest-asyncio` (hoặc `anyio`).
- Server giả cục bộ (tự viết); không cần GPU, API key, mạng.

## Nguồn gốc

- Nguồn: `triet4p/llm-serving-lab`, file `benchmarks/concurrency.py`.
- URL chính xác: <https://github.com/triet4p/llm-serving-lab/blob/main/benchmarks/concurrency.py>

Hành vi quan sát được trong nguồn:

- PEP 723 với `httpx>=0.27`, Python `>=3.12`.
- Đọc ba biến `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME`; thiếu thì `SystemExit`.
- `send_request` async đo `perf_counter`, duyệt `aiter_lines`, parse SSE giống bài 14, trả `total_time`, `time_to_first_token`, `generation_time`, `tokens`, `tokens_per_second`.
- `run_batch` tạo `asyncio.Semaphore(concurrency)`; trong `bounded`, mở một `httpx.AsyncClient` **mới cho mỗi request**, gọi `send_request`; `asyncio.gather(*(bounded(p) for p in payloads))`.
- `main` validate `requests >= 1`, `concurrency >= 1`; đo `wall`; in requests/sec, tokens/sec, latency min/mean/max; lưu JSON/CSV.
- Nguồn không kiểm tra in-flight thực tế; không xử lý lỗi từng request; không hủy task khi ngắt.

## Phạm vi bài tập

Xây package `concurrency_bench`:

- `run_batch(client, url, headers, payloads, concurrency)` với semaphore, client chia sẻ, kết quả giữ thứ tự.
- `InstrumentedSemaphore` hoặc counter để đo `peak_in_flight`.
- `summarize_latencies`, `throughput`.
- CLI với server giả; lỗi từng request được ghi; `KeyboardInterrupt` hủy sạch.
- Test với transport giả để khẳng định peak == `min(C, N)`.

Không nằm trong phạm vi: benchmark khoa học, autoscaling, rate limit theo token, so sánh backend, phân tích queueing.

## Liên kết

- [SPEC.md](SPEC.md) — API, bất biến in-flight, ví dụ, mã thoát.
- [GUIDE.md](GUIDE.md) — semaphore, client, test giả, hủy.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn mở client mới trong mỗi tác vụ; bài tập yêu cầu client chia sẻ và `Limits(max_connections >= concurrency)`. Nguồn không đo in-flight và không cô lập lỗi; bài tập thêm cả hai. Đây là thiết kế của bài tập.
