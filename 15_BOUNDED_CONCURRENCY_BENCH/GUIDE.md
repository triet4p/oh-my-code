# GUIDE — Bounded concurrency benchmark

## Bước 0 — Môi trường

```bash
mkdir 15_BOUNDED_CONCURRENCY_BENCH/work && cd 15_BOUNDED_CONCURRENCY_BENCH/work
uv init . -p 3.12
uv add httpx
uv add --dev pytest pytest-asyncio
mkdir -p src/concurrency_bench tests
```

Cấu hình `pytest` với `asyncio_mode = "auto"` trong `pyproject.toml` để test async gọn.

## Bước 1 — Semaphore đặt đúng chỗ

Mẫu sai:

```text
async def one(payload):
    await sem.acquire()
    result = await send_request(...)
    sem.release()
```

Nếu `send_request` ném, `release` không chạy → deadlock. Dùng `async with sem:`.

Mẫu đúng:

```text
async def one(i, payload):
    async with sem:
        counter.enter()
        try:
            return await send_request(...)
        finally:
            counter.exit()
```

`counter.enter()` **sau** `async with` và **trước** `await` đầu tiên. Nhờ vậy, khi event loop chạy C task đầu, cả C đều tăng trước khi bất kỳ I/O nào hoàn tất; peak = min(C,N) ổn định.

## Bước 2 — Client chia sẻ

Tạo một `httpx.AsyncClient` trong `async with` ngoài cùng:

```text
limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
async with httpx.AsyncClient(timeout=timeout or None, limits=limits) as client:
    batch = await run_batch(client, url, headers, payloads, concurrency)
```

Nếu `max_connections < concurrency`, httpx sẽ xếp hàng bên trong, peak quan sát vẫn ≤ C nhưng throughput thấp hơn và bài học “semaphore là giới hạn duy nhất” sai. Đặt `max_connections >= concurrency`, hoặc ghi rõ có hai tầng giới hạn.

Nguồn mở client trong mỗi task; điều đó vẫn đúng nhưng bỏ pooling. Bài tập yêu cầu chia sẻ.

## Bước 3 — Counter

```python
class InFlightCounter:
    def __init__(self):
        self.current = 0
        self._peak = 0
    def enter(self):
        self.current += 1
        self._peak = max(self._peak, self.current)
    def exit(self):
        self.current -= 1
    @property
    def peak(self):
        return self._peak
```

Không dùng `asyncio.Lock` quanh counter: các thao tác đồng bộ trong một event loop là nguyên tử giữa các `await`. Nếu chạy đa luồng, cần lock; bài tập không.

Muốn kiểm tra chắc hơn, dùng thêm counter trong handler fake; so hai peak.

## Bước 4 — `send_request`

Tái sử dụng ý tưởng bài 14 nhưng async:

```text
async with client.stream("POST", url, headers=headers, json=payload) as response:
    response.raise_for_status()
    async for line in response.aiter_lines():
        ...
```

`raise_for_status` trong `async with` để đóng stream đúng.

Trả `RequestResult` không có `index`; `run_batch` dùng `dataclasses.replace` gán index.

## Bước 5 — `run_batch`

```text
if concurrency < 1: raise ValueError
if not payloads: raise ValueError
sem = asyncio.Semaphore(concurrency)
counter = counter or InFlightCounter()
start = perf_counter()
tasks = [one(i, p) for i, p in enumerate(payloads)]
rows = await asyncio.gather(*tasks)
wall = max(perf_counter() - start, 1e-12)
```

Không dùng `asyncio.as_completed`: nó trả theo thứ tự hoàn thành, làm mất index trừ khi bạn tự map. `gather` giữ thứ tự.

Bắt `Exception` trong `one`:

```text
except Exception as exc:
    return RequestResult(index=i, ..., error=f"{type(exc).__name__}: {exc}")
```

Không bắt `asyncio.CancelledError` (nó kế thừa `BaseException` ở Python 3.8+), để hủy lan truyền.

## Bước 6 — Thống kê

```text
ok = [r for r in rows if r.error is None]
tokens = sum(r.tokens or 0 for r in ok)
rps = len(rows) / wall
tps = tokens / wall
latencies = [r.total_time for r in ok]
```

`r.total_time` có thể `None`; lọc trước khi tính.

`p50`: nearest-rank. Với 8 giá trị, p50 lấy phần tử thứ 4 (1-based).

## Bước 7 — Hủy

`asyncio.run(main())` sẽ biến `KeyboardInterrupt` thành hủy main task và in traceback nếu không bắt. Bọc:

```text
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("interrupted", file=sys.stderr)
    sys.exit(130)
```

Bên trong `main`, `async with client` đảm bảo đóng. Nếu bạn giữ task riêng, phải `cancel()` và `await` chúng; `gather` đã làm khi main bị hủy.

## Bước 8 — Test tất định

Dùng `httpx.MockTransport`:

```text
class Handler:
    def __init__(self, delay, fail_indexes): ...
    async def __call__(self, request):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.delay)
            if index in fail: return httpx.Response(500)
            body = "data: {...}\n\ndata: [DONE]\n\n"
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        finally:
            self.active -= 1
```

Vấn đề: handler không biết index từ request. Có thể đọc `request.content` (JSON) và lấy `messages` hoặc thêm header `X-Index` khi build payload. Đơn giản: payload có `metadata: {"index": i}`; handler parse.

Test:

- `run_batch` với 6 payload, C=2, delay 10ms: peak 2; order.
- C=5, N=2: peak 2.
- Handler lỗi index 1: failed 1, ok 5.
- Tất cả lỗi: `ok == 0`.
- Counter trong handler `peak <= C`.

Với MockTransport, `client.stream` hoạt động; response content đã có sẵn nên `aiter_lines` trả ngay. Đo TTFT gần 0, không sao.

## Bước 9 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run fixture_server.py --port 8765 --chunks 5 --delay-ms 20 &
uv run bench.py --requests 8 --concurrency 4 --no-save
```

Kỳ vọng: `peak in-flight: 4`; `requests/sec` xấp xỉ `4 / (5*20ms)` ≈ 40 (tùy overhead); `failed: 0`.

Thử `--concurrency 16 --requests 4`: peak 4.

## Bước 10 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Peak > C | Tăng counter trước khi lấy semaphore. |
| Peak < C dù N>=C | Tăng sau `await` đầu tiên, hoặc client giới hạn connection. |
| Deadlock | Thiếu `finally`/`async with` khi lỗi. |
| Thứ tự sai | Dùng `as_completed`. |
| Một lỗi hủy mẻ | Không bắt trong task; `gather` ném. |
| `CancelledError` bị nuốt | Bắt `BaseException`. |
| Tokens/s sai | Chia cho thời gian sinh thay vì wall. |
| Client mới mỗi task | Tạo trong `one` thay vì truyền vào. |
| Test chập chờn | Dùng sleep thật; thay bằng delay nhỏ + invariant. |

## Bước 11 — Mở rộng

- Đo p90/p95 latency.
- Thêm rate limit (token bucket) song song semaphore.
- Thêm warmup và repetitions.
- So sánh C=1,2,4,8 và vẽ biểu đồ.
- Thêm adaptive concurrency (AIMD) như một bài nâng cao.

## Tự đánh giá

1. Vì sao `peak == C` ngay từ đầu với C tác vụ đầu?
2. Vì sao không bắt `BaseException`?
3. Semaphore và `max_connections` khác vai trò thế nào?
4. Vì sao `gather` giữ thứ tự còn `as_completed` thì không?
