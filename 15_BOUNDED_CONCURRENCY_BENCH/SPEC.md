# SPEC — Bounded concurrency benchmark

## Mục tiêu hành vi

Gửi `N` yêu cầu streaming với tối đa `C` yêu cầu đồng thời. Trả về kết quả theo đúng thứ tự đầu vào, đo thời gian tường, thông lượng và độ trễ; ghi nhận số yêu cầu đang bay lớn nhất và bảo đảm nó không vượt `C`.

## Kiểu

```python
@dataclass(frozen=True, slots=True)
class RequestResult:
    index: int
    total_time: float | None
    time_to_first_token: float | None
    generation_time: float | None
    tokens: int | None
    error: str | None

@dataclass(frozen=True, slots=True)
class BatchResult:
    rows: tuple[RequestResult, ...]
    wall_seconds: float
    peak_in_flight: int
    requested_concurrency: int
    requests_per_second: float
    tokens_per_second: float
```

## API

```python
async def send_request(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict,
) -> RequestResult: ...

async def run_batch(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payloads: Sequence[dict],
    concurrency: int,
    *,
    counter: InFlightCounter | None = None,
) -> BatchResult: ...
```

`InFlightCounter` là protocol nhỏ:

```python
class InFlightCounter(Protocol):
    def enter(self) -> None: ...
    def exit(self) -> None: ...
    @property
    def peak(self) -> int: ...
```

Có thể truyền `None`; `run_batch` vẫn trả `peak_in_flight` từ counter nội bộ.

## Bất biến

1. `1 <= concurrency`; nếu không → `ValueError`.
2. `len(payloads) >= 1`; nếu không → `ValueError`.
3. Peak in-flight `<= concurrency`.
4. Với `N >= C`, peak **bằng** `C` ngay từ đầu, vì C tác vụ đầu tiên lấy semaphore và tăng bộ đếm trước khi await I/O.
5. `len(rows) == N` và `rows[i].index == i`.
6. Không có task nào bị mất khi một request lỗi.
7. Semaphore được nhả trong `finally`, kể cả khi `send_request` ném.

## `send_request`

- Giống bài 14: POST `{url}`, stream, `perf_counter`, parse SSE, đếm chunk text.
- Trả `RequestResult` với `index` do caller gán? Để tránh nhầm, `send_request` trả các trường thời gian và `error=None`; `run_batch` gán `index`.
- Khi lỗi, **không** ném ra ngoài `run_batch`; `run_batch` bắt và tạo row lỗi.

## `run_batch`

```text
validate
sem = asyncio.Semaphore(concurrency)
counter = counter or InFlightCounter()
start = perf_counter()

async def one(index, payload):
    async with sem:
        counter.enter()
        try:
            result = await send_request(client, url, headers, payload)
            return replace(result, index=index)
        except Exception as exc:
            return RequestResult(index=index, None, None, None, None, type(exc).__name__)
        finally:
            counter.exit()

rows = await asyncio.gather(*(one(i, p) for i, p in enumerate(payloads)))
wall = perf_counter() - start
```

- `asyncio.gather` trả kết quả theo thứ tự task, nên `rows` đúng thứ tự.
- Bắt `Exception`, **không** bắt `BaseException`; `CancelledError` phải lan ra để hủy sạch.
- `counter.enter()` phải nằm sau khi lấy semaphore và trước `await` đầu tiên.

Thống kê:

- `ok = [r for r in rows if r.error is None]`.
- `token_sum = sum(r.tokens or 0 for r in ok)`.
- `rps = N / wall` (kể cả lỗi; đây là thông lượng attempted).
- `tokens_per_second = token_sum / wall`.
- `wall_seconds = max(wall, 1e-12)` để tránh chia 0.
- Độ trễ chỉ tính trên `ok`.

## Latency

`latency_summary(ok)` trả:

```json
{"min": ..., "mean": ..., "max": ..., "p50": ...}
```

- Dùng `total_time`.
- `p50` nearest-rank như bài 14.
- Rỗng → tất cả `0.0`.

## CLI

```text
bench [--base-url URL] [--api-key KEY] [--model NAME]
      [--requests N] [--concurrency C] [--max-tokens N]
      [--timeout SECONDS] [--output-dir DIR] [--no-save]
```

Mặc định giống bài 14, thêm `--requests 8`, `--concurrency 4`.

Validation:

- `requests >= 1`; `concurrency >= 1`.
- `concurrency` được phép lớn hơn `requests`; peak khi đó là `requests`.
- `timeout = 0` → `None`.

## Output

```text
model:            local-model
endpoint:         http://127.0.0.1:8765/v1/chat/completions
requests:         8
concurrency:      4
peak in-flight:   4
wall time (s):    0.412
requests/sec:     19.42
tokens/sec:       97.09
latency min/mean/max (s): 0.201 / 0.309 / 0.410
p50 latency (s):  0.305
failed:           0
```

JSON:

```json
{
  "model": "...",
  "endpoint": "...",
  "requests": 8,
  "concurrency": 4,
  "peak_in_flight": 4,
  "wall_time_s": 0.412,
  "requests_per_second": 19.42,
  "tokens_per_second": 97.09,
  "latency_min_s": 0.201,
  "latency_mean_s": 0.309,
  "latency_max_s": 0.410,
  "latency_p50_s": 0.305,
  "ok": 8,
  "failed": 0
}
```

CSV: một dòng mỗi request với `index,total_time,time_to_first_token,generation_time,tokens,tokens_per_second,error`.

## Mã thoát

| Tình huống | Mã |
|---|---:|
| Có ít nhất một request thành công | 0 |
| Tất cả lỗi | 1 |
| CLI/validate sai | 2 |
| Không ghi được output | 1 |

## Ví dụ

N=6, C=2, mỗi request mất 100ms:

- Peak = 2.
- Wall xấp xỉ 300ms (3 đợt).
- `rps ≈ 20`.
- `rows` có index 0..5 đúng thứ tự, dù thứ tự hoàn thành khác.

N=3, C=5:

- Peak = 3.
- Wall xấp xỉ thời gian một request.

C=1:

- Tuần tự; peak 1; wall xấp xỉ N × latency.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `N=0` | `ValueError` |
| `C=0` | `ValueError` |
| `C > N` | peak = N |
| Một request 500 | row lỗi; các row khác bình thường |
| Tất cả 500 | exit 1 |
| Timeout | row `ReadTimeout`/`TimeoutException` |
| Request hoàn thành ngay | peak vẫn đạt C (do enter trước await) |
| Client bị đóng giữa chừng | lỗi từng row, không treo |
| `Ctrl+C` | `KeyboardInterrupt`; task bị hủy; client đóng qua `async with` |
| `wall` cực nhỏ | rps lớn nhưng hữu hạn nhờ `max(wall, 1e-12)` |

## Tiêu chí nghiệm thu

1. Test fake transport: `N=6, C=2` → `peak == 2`, `rows` index 0..5, `len == 6`.
2. `N=2, C=5` → `peak == 2`.
3. Counter trong handler fake chứng minh active không bao giờ > C.
4. Một handler ném lỗi → các row khác vẫn `ok`, `failed == 1`.
5. `C=0`/`N=0` ném `ValueError`.
6. Thống kê với mảng cố định cho đúng `min/mean/max/p50`.
7. Integration server giả: `tokens == chunks * ok`.
8. Không tạo client mới trong mỗi task (kiểm tra bằng code review hoặc đếm constructor qua monkeypatch).
9. `pytest -q` xanh.

## Non-goals

- Benchmark khoa học, warmup, confidence interval.
- Rate limit theo token, queueing theory.
- Tự động chọn concurrency tối ưu.
- So sánh nhiều backend.
- Streaming UI.
