# SPEC — Streaming latency benchmark

## Mục tiêu hành vi

Gửi `N` yêu cầu chat streaming tới một endpoint tương thích OpenAI, đo tổng thời gian, thời điểm chunk văn bản đầu tiên (TTFT) và thời gian sinh cho từng yêu cầu; tổng hợp min/max/mean/p50/p90/p95; ghi kết quả JSON/CSV. Không yêu cầu GPU, API key thật hay mạng ngoài.

## CLI

```text
bench [--base-url URL] [--api-key KEY] [--model NAME]
      [--iterations N] [--prompt TEXT] [--max-tokens N]
      [--timeout SECONDS] [--output-dir DIR] [--no-save]
```

| Tùy chọn | Mặc định |
|---|---|
| `--base-url` | `http://127.0.0.1:8765/v1` |
| `--api-key` | `local` |
| `--model` | `local-model` |
| `--iterations` | `10` |
| `--prompt` | `Explain in one sentence what an LLM serving engine does.` |
| `--max-tokens` | `128` |
| `--timeout` | `0` (không giới hạn) |
| `--output-dir` | `results/` |
| `--no-save` | tắt |

Ưu tiên: CLI > env (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME`) > mặc định. Không bắt buộc env.

`--iterations < 1` → exit 2. `--max-tokens < 1` → exit 2.

## Endpoint

`POST {base_url}/chat/completions` với:

```json
{
  "model": "...",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "..."}
  ],
  "max_tokens": 128,
  "temperature": 0.7,
  "stream": true
}
```

Header `Content-Type: application/json`, `Authorization: Bearer {key}`. Không gửi `chat_template_kwargs` trừ khi có cờ mở rộng.

## Đo

Với mỗi yêu cầu:

- `start = time.perf_counter()` ngay trước khi mở stream.
- `first_token_time = None`; `tokens = 0`.
- Đọc từng dòng SSE.
- Khi chunk có text: `tokens += 1`; nếu `first_token_time is None`, gán `perf_counter() - start`.
- `total = perf_counter() - start`.
- `ttft = first_token_time if not None else total`.
- `generation = max(total - ttft, 0.0)`.
- `tokens_per_second = tokens / generation if generation > 0 else 0.0`.

`perf_counter` là đồng hồ đơn điệu; không dùng `time.time()`.

## Parse SSE

Mỗi dòng:

1. Bỏ `\r` cuối nếu có.
2. Bỏ qua dòng rỗng.
3. Chỉ xử lý dòng bắt đầu bằng `data:`; phần sau dấu `:` được `strip()`.
4. Nếu payload là `[DONE]` → dừng.
5. `json.loads`; nếu lỗi → bỏ qua dòng.
6. `choices = obj.get("choices") or []`; nếu rỗng → bỏ qua.
7. `delta = choices[0].get("delta") or {}`.
8. `text = delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content") or ""`.
9. Nếu `text` là string và khác rỗng → tính một “token” (thực chất là một chunk có text).
10. Không đọc `choices[0].message` (không streaming).

Chunk đầu thường chỉ có `{"delta":{"role":"assistant"}}` — không có text, nên không tính TTFT.

## Thống kê

`percentile(values, p)`:

- `values` rỗng → `0.0`.
- `p` phải `0 < p <= 100`; ngoài khoảng → `ValueError`.
- Sắp tăng dần.
- `rank = ceil(p / 100 * n)`; `index = clamp(rank - 1, 0, n - 1)`.
- Trả phần tử tại `index`.

Đây là **nearest-rank**. Ví dụ `[1,2,3,4]`:

| p | rank | index | value |
|---|---:|---:|---:|
| 50 | 2 | 1 | 2.0 |
| 90 | 4 | 3 | 4.0 |
| 95 | 4 | 3 | 4.0 |
| 100 | 4 | 3 | 4.0 |

`summarize(values)` trả:

```json
{"min": 0.0, "max": 0.0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}
```

- `mean` dùng `statistics.fmean`.
- Mảng rỗng → tất cả `0.0`.
- Không làm tròn trong dữ liệu; chỉ format khi in.

## Kết quả từng yêu cầu

```json
{
  "iteration": 1,
  "total_time": 0.123,
  "time_to_first_token": 0.045,
  "generation_time": 0.078,
  "tokens": 12,
  "tokens_per_second": 153.8,
  "error": null
}
```

Nếu lỗi (HTTP, timeout, kết nối):

- `error` là chuỗi mô tả ngắn (`HTTPStatusError: 500`, `ConnectError`, `ReadTimeout`).
- Các trường thời gian/tokens là `null` (không đưa vào thống kê).
- Không dừng cả mẻ.

Nếu tất cả yêu cầu lỗi → exit 1. Nếu ít nhất một thành công → exit 0, in cảnh báo số lỗi.

## Tổng hợp và lưu

JSON:

```json
{
  "model": "local-model",
  "endpoint": "http://127.0.0.1:8765/v1/chat/completions",
  "iterations": 3,
  "ok": 3,
  "failed": 0,
  "total_latency_s": { "min": ..., "max": ..., "mean": ..., "p50": ..., "p90": ..., "p95": ... },
  "time_to_first_token_s": { ... },
  "generation_s": { ... },
  "tokens_mean": 12.0
}
```

CSV: header cố định `iteration,total_time,time_to_first_token,generation_time,tokens,tokens_per_second,error`; một dòng mỗi yêu cầu, kể cả lỗi.

Tên file: `latency_<YYYYmmdd-HHMMSS>.json` và `.csv` trong `--output-dir`. Tạo thư mục nếu chưa có. `--no-save` không ghi gì.

## Stdout

```text
model:            local-model
endpoint:         http://127.0.0.1:8765/v1/chat/completions
iterations:       3
ok:               3
failed:           0

latency summary (s)
     total latency: min=0.100 max=0.130 mean=0.115 p50=0.115 p90=0.130 p95=0.130
 time-to-first-token: min=0.040 max=0.050 mean=0.045 p50=0.045 p90=0.050 p95=0.050
         generation: min=0.060 max=0.080 mean=0.070 p50=0.070 p90=0.080 p95=0.080
              tokens: mean=12.0
```

Số chữ số thập phân khi in là `.3f`.

## Server giả

`fixture_server.py`:

- `POST /v1/chat/completions`.
- Trả `Content-Type: text/event-stream`.
- Gửi một chunk role-only, rồi `chunks` chunk content, mỗi chunk cách nhau `delay_ms`, cuối cùng `data: [DONE]`.
- Bỏ qua body.
- Có thể trả 500 nếu header `X-Fail: 1` để test lỗi.
- Chạy `python fixture_server.py --port 8765 --chunks 5 --delay-ms 20`.

Không cần đúng tokenizer; mục tiêu là hình dạng SSE.

## Ví dụ

Với server giả 5 chunk, delay 20ms, 3 iteration:

- `tokens` mỗi yêu cầu = 5 (role-only không tính).
- `ttft >= 20ms`, `total >= 100ms`, `generation = total - ttft`.
- `tokens_per_second > 0`.

Kiểm tra parse bằng chuỗi cố định:

```text
data: {"choices":[{"delta":{"role":"assistant"}}]}
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: not-json
data: {"choices":[]}
data: [DONE]
```

Kết quả: `tokens == 1`, TTFT được ghi ở dòng thứ hai.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `iterations = 0` | exit 2 |
| `percentile([], 50)` | `0.0` |
| `percentile([1], 90)` | `1.0` |
| `percentile([1,2,3,4], 100)` | `4.0` |
| `p = 0` hoặc `>100` | `ValueError` |
| SSE không có `[DONE]` | đọc đến hết stream; vẫn tính |
| Không có chunk text | `ttft == total`, `tokens == 0`, `tps == 0` |
| Chunk content rỗng `""` | không tính token, không đặt TTFT |
| Chunk reasoning | tính token |
| JSON hỏng giữa stream | bỏ qua dòng, tiếp tục |
| HTTP 500 | row lỗi, tiếp tục mẻ |
| Tất cả lỗi | exit 1 |
| Timeout | row lỗi `ReadTimeout` |
| `--no-save` | không tạo file |
| Thư mục output không ghi được | exit 1, in lỗi |

## Tiêu chí nghiệm thu

1. `percentile` khớp bảng ví dụ và là nearest-rank.
2. `summarize([])` trả toàn 0.
3. Parser SSE với chuỗi cố định cho `tokens == 1` và bỏ qua dòng hỏng.
4. Chunk role-only không đặt TTFT.
5. Integration với server giả: `tokens == chunks`, `ttft <= total`, `generation == total - ttft` (sai số `1e-9`).
6. Một request lỗi không làm mất các request thành công; `failed` đúng.
7. JSON/CSV có đúng khóa; CSV có header.
8. `--no-save` không tạo file.
9. `pytest -q` xanh; không test phụ thuộc thời gian tuyệt đối.

## Non-goals

- Đo token thật bằng tokenizer.
- So sánh vLLM/Ollama/FastAPI.
- Đo GPU, bộ nhớ, năng lượng.
- Tải đồng thời (bài 15).
- Phân tích thống kê nâng cao (confidence interval, warmup, outlier removal).
- Gửi `thinking`/`chat_template_kwargs`.
