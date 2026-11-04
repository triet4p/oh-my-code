# GUIDE 26 — Thiết kế vòng đời phiên

## 1. Kiến trúc

```
session/
├─ models.py      # TransportMessage, validate
├─ client.py      # A2AClient, A2ASession
├─ transport.py   # Protocol + FakeTransport
├─ errors.py
└─ demo.py
fixtures/scenarios/
```

`client.py` không import `websockets`; nó chỉ biết `Transport`. Nhờ vậy test chạy offline và có thể thay bằng WebSocket thật sau này.

## 2. Context manager

Khung:

```python
@asynccontextmanager
async def session(self):
    headers = ...
    conn = await self._transport.connect(self.uri, headers)  # bọc lỗi
    session = A2ASession(conn, ...)
    try:
        yield session
    finally:
        await session.close()
```

Đây là **khung**, không phải lời giải đầy đủ. Cần xử lý:

- `close()` có thể ném; nếu thân đã ném, ưu tiên giữ exception gốc (dùng `try/finally` cẩn thận).
- Không gọi `close()` nếu `connect` ném.
- Đặt `closed=True` **trước** hoặc ngay sau khi gọi close để chống tái nhập.

## 3. Phân biệt notification/khóa

Trong bài này không có JSON-RPC; nhưng nguyên tắc tương tự: kiểm tra sự hiện diện của trường, không chỉ giá trị. Với schema message, dùng kiểm tra tường minh:

```
required = {"message_id", "kind", "sender", "recipient", "created_at", "payload"}
if set(obj) != required: invalid
```

Nếu muốn cho phép mở rộng sau này, dùng `required <= set(obj)` và bỏ qua trường lạ; bài chọn chặt để test dễ.

## 4. Async generator

```python
async def listen(self):
    if self.closed: raise SessionClosed
    if self._listening: raise SessionAlreadyListening
    self._listening = True
    try:
        async for text in self._conn:
            msg = decode(text)
            if msg is None: continue
            yield msg
    except ConnectionClosed:
        return
    finally:
        self._listening = False
```

**Bẫy:** nếu người dùng `break`, `finally` chạy và `_listening=False`, nhưng generator bị đóng; lần `listen()` sau có thể tạo generator mới. Điều này chấp nhận được. Nếu muốn cấm, đặt cờ `_listen_consumed`.

`CancelledError` là `BaseException` trong Python 3.8+; đừng bắt `Exception` rồi biến nó thành `SessionError`.

## 5. Serialize

- Dùng `json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)` để ổn định.
- Kiểm tra kích thước payload sau serialize; 64 KiB là giới hạn bài.
- Không dùng `default=str`; nếu object không serialize được, đó là lỗi lập trình, phải báo.

## 6. FakeTransport

Kịch bản JSON:

```json
{
  "connect": "ok",
  "headers_expected": {"Authorization": "Bearer test-token"},
  "frames": [
    {"type": "text", "text": "{\"message_id\":\"m-1\",...}"},
    {"type": "malformed", "text": "{bad"},
    {"type": "sleep", "seconds": 0.01},
    {"type": "close"}
  ]
}
```

`FakeTransport` ghi lại `connect_calls`, `send_calls`, `close_calls`, `headers`. Không dùng sleep thật nếu muốn test nhanh; thay bằng `await asyncio.sleep(0)` để nhường scheduler.

## 7. Bẫy thường gặp

- **Gọi `close()` trong `except` thay vì `finally`**: bỏ qua nhánh hủy.
- **Bắt `Exception` quanh `yield`**: có thể nuốt lỗi của người dùng. Chỉ bọc phần transport.
- **Đặt `closed=True` sau `await close()`**: nếu close ném, trạng thái sai.
- **Log `headers`**: rò token. Log danh sách khóa, không giá trị.
- **Parse JSON rồi validate bằng `assert`**: `assert` bị tắt với `-O`; dùng exception.
- **Bỏ qua frame sai schema im lặng**: cần cảnh báo đếm được, nhưng không log nội dung.
- **Để `ConnectionClosed` rơi vào nhánh lỗi chung**: biến đóng bình thường thành sự cố.
- **Tạo session trước khi connect**: context manager yield sai thời điểm.

## 8. Kiểm chứng

```bash
cd 26_ASYNC_SESSION_CLIENT
python -m unittest discover -s tests -v
```

Test thủ công:

```bash
python -m demo --scenario fixtures/scenarios/ok.json
```

Demo in ra: số message nhận, số cảnh báo, `close_count`, và việc header có token hay không (chỉ boolean, không in token).

Kiểm tra hủy:

```python
task = asyncio.create_task(run_session())
await asyncio.sleep(0)
task.cancel()
try: await task
except asyncio.CancelledError: pass
assert transport.close_calls == 1
```

Kiểm tra log:

```python
assert "test-token" not in caplog.text
assert "hello" not in caplog.text
```

## 9. Gợi ý

- Viết `FakeConnection` với `asyncio.Queue`; `close()` đặt sentinel và đánh thức iterator.
- `__aiter__` trả chính connection; `__anext__` chờ queue, nếu sentinel → `StopAsyncIteration`.
- Tách `decode_frame(text) -> TransportMessage | None` để test độc lập.
- Dùng `contextlib.asynccontextmanager` thay vì tự viết `__aenter__`.
- Kiểm tra `close_count` bằng bộ đếm trong fake, không dựa vào log.

## 10. Mở rộng

1. Thêm heartbeat và phát hiện kết nối chết.
2. Thêm reconnect có backoff, nhưng chỉ khi được yêu cầu rõ.
3. Thêm hai listener độc lập với `asyncio.Queue` broadcast.
4. Thêm mã hóa token trong bộ nhớ (không log).
5. Thay transport bằng WebSocket thật, giữ nguyên test.
