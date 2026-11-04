# GUIDE — Streaming latency benchmark

## Bước 0 — Script độc lập

Theo nguồn, dùng PEP 723 để chạy không cần tạo project:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
```

Đặt `bench.py` và `fixture_server.py`. Chạy:

```bash
uv run bench.py --base-url http://127.0.0.1:8765/v1 --iterations 3
```

Nếu muốn pytest, tách phần thuần (`stats.py`, `sse.py`) khỏi script, hoặc dùng `uv run --with pytest pytest`.

## Bước 1 — Viết server giả trước

Server giả giúp bạn phát triển mà không cần backend. Dùng `http.server.ThreadingHTTPServer`.

Handler:

- Chỉ chấp nhận `POST /v1/chat/completions`.
- Đặt `Content-Type: text/event-stream`, `Cache-Control: no-cache`.
- Ghi chunk role-only:

```text
data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}\n\n
```

- Lặp `chunks` lần:

```text
data: {"choices":[{"delta":{"content":"token "},"index":0}]}\n\n
```

- `time.sleep(delay_ms / 1000)` giữa các chunk.
- Kết thúc `data: [DONE]\n\n`.
- `self.wfile.flush()` sau mỗi lần ghi; nếu không, client sẽ nhận tất cả cùng lúc và TTFT sai.
- Đọc/ignore body dựa trên `Content-Length`, nếu không client có thể bị reset.

Tùy chọn `X-Fail: 1` → trả 500 ngay.

Kiểm tra bằng `curl -N`:

```bash
curl -N -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H 'Content-Type: application/json' -d '{}'
```

Bạn phải thấy từng dòng đến rải rác, không phải một cục.

## Bước 2 — Parse SSE

Viết `iter_text_chunks(lines: Iterable[str]) -> Iterator[str]` thuần, không I/O:

```text
for raw in lines:
    line = raw.rstrip("\r")
    if not line or not line.startswith("data:"):
        continue
    payload = line[5:].strip()
    if payload == "[DONE]":
        return
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        continue
    ...
    if isinstance(text, str) and text:
        yield text
```

Kiểm tra `isinstance(text, str)`: một số backend trả `null` hoặc object.

Tại sao `.strip()`? SSE cho phép `data: {...}` và `data:  {...}`. `.strip()` xử lý cả hai.

## Bước 3 — Đo

```text
start = time.perf_counter()
first = None
count = 0
with client.stream(...) as response:
    response.raise_for_status()
    for text in iter_text_chunks(response.iter_lines()):
        count += 1
        if first is None:
            first = time.perf_counter() - start
total = time.perf_counter() - start
```

`response.raise_for_status()` đặt **trong** `with` và trước khi đọc; lỗi sẽ được bắt ở lớp ngoài.

Không gọi `time.perf_counter()` trong generator rồi trừ sai mốc; mốc phải là `start` của toàn request.

## Bước 4 — Percentile

Cài đặt nearest-rank:

```text
def percentile(values, p):
    if not values: return 0.0
    if not (0 < p <= 100): raise ValueError("p must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    index = min(max(rank - 1, 0), len(ordered) - 1)
    return float(ordered[index])
```

Kiểm tra với `[1,2,3,4]`. Nếu p50 của bạn ra 2.5, bạn đang dùng nội suy, không phải nearest-rank.

## Bước 5 — Tổng hợp

`summarize`:

```text
if not values: return {k: 0.0 for k in (...)}
return {"min": float(min(values)), "max": float(max(values)),
        "mean": statistics.fmean(values),
        "p50": percentile(values, 50), "p90": percentile(values, 90),
        "p95": percentile(values, 95)}
```

Dùng `fmean` trả `float`; `statistics.mean` có thể trả `Fraction`/`Decimal` với đầu vào đặc biệt.

## Bước 6 — Vòng lặp và lỗi

```text
rows = []
with httpx.Client(timeout=timeout or None) as client:
    for i in range(iterations):
        try:
            row = send_request(...)
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            row = {"iteration": i + 1, "error": type(exc).__name__, ...nulls}
        rows.append(row)
```

Không bắt `BaseException`; `KeyboardInterrupt` phải thoát.

Tính `ok = [r for r in rows if r["error"] is None]`.

Nếu `not ok`: in lỗi, exit 1. Nếu có lỗi lẻ: in cảnh báo, tiếp tục.

## Bước 7 — Lưu

Tên file timestamp: `time.strftime("%Y%m%d-%H%M%S")`. Nếu chạy nhanh hai lần trong cùng giây, file ghi đè; thêm hậu tố milliseconds nếu muốn. Bài tập chấp nhận ghi đè, ghi rõ.

CSV: dùng `csv.DictWriter`, `fieldnames` cố định; giá trị `None` thành ô rỗng.

JSON: `json.dumps(..., indent=2, ensure_ascii=False)`.

## Bước 8 — Test

1. `percentile` với bảng.
2. `summarize([])`.
3. `iter_text_chunks` với chuỗi cố định (dùng `io.StringIO` hoặc list).
4. Role-only không tạo text.
5. Integration với server giả: chạy subprocess server trên cổng ngẫu nhiên, đợi port mở, chạy 2 iteration, tắt.
6. Lỗi 500: server giả với `X-Fail`, kiểm tra row `error`.
7. `--no-save`.

Với integration, đừng khẳng định `ttft > 0.02` chính xác; chỉ `ttft >= 0` và `tokens == 5`.

## Bước 9 — Kiểm chứng độc lập

```bash
uv run fixture_server.py --port 8765 --chunks 5 --delay-ms 20 &
uv run bench.py --base-url http://127.0.0.1:8765/v1 --iterations 3 --no-save
```

Kỳ vọng: `tokens mean=5.0`, TTFT khoảng 20ms, total khoảng 100ms.

Sau đó bỏ `--no-save`:

```bash
uv run bench.py --iterations 2 --output-dir out
ls out
python -c "import json,glob; d=json.load(open(glob.glob('out/*.json')[0])); print(d['ok'], d['total_latency_s']['p50'])"
```

## Bước 10 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| TTFT xấp xỉ total dù có chunk sớm | Server không flush; hoặc client buffer. |
| `tokens == 0` | Chỉ có chunk role; hoặc parse sai `data:`. |
| Percentile lệch | Dùng nội suy hoặc index `int(p/100*n)` không clamp. |
| `tokens_per_second` âm | Không `max(total-ttft, 0)`. |
| Một lỗi làm mất cả mẻ | Không bọc từng request. |
| CSV thiếu cột khi lỗi | `fieldnames` lấy từ row đầu; cố định header. |
| `httpx` treo | `timeout=0` nghĩa là không giới hạn; test nên đặt timeout. |
| Server giả không nhận request | Thiếu đọc body hoặc sai `Content-Length`. |

## Bước 11 — Mở rộng

- Thêm warmup requests và loại bỏ.
- Thêm `--thinking on/off`.
- Thêm dataset request.
- Thêm histogram.
- Thêm so sánh hai endpoint trong một lần chạy.
- Chuyển sang bài 15 để đo tải đồng thời.

## Tự đánh giá

1. Vì sao TTFT không thể lấy từ chunk role-only?
2. Vì sao dùng `perf_counter`?
3. Nearest-rank khác nội suy ở đâu, và điều đó ảnh hưởng báo cáo thế nào?
4. Vì sao lỗi từng request nên được ghi nhận thay vì ném?
