# SPEC 26 — Phiên bất đồng bộ

## 1. API

```python
client = A2AClient(agent_id="agent-a", uri="ws://fixture/ws", token="test-token")

async with client.session() as session:
    await session.send(message)
    async for incoming in session.listen():
        ...
```

- `A2AClient(agent_id, uri, token=None)`; `agent_id` 1–64 ký tự; `uri` không rỗng.
- `session()` là async context manager, không trả về session trước khi kết nối thành công.
- `A2ASession.send(message) -> None`.
- `A2ASession.listen() -> AsyncIterator[TransportMessage]`.
- `A2ASession.closed` là thuộc tính bool.
- Exception: `SessionClosed`, `SessionAlreadyListening`, `SessionError` (lỗi transport sau khi mở).

## 2. Transport interface (dependency injection)

```python
class Transport(Protocol):
    async def connect(self, uri: str, headers: dict[str, str]) -> Connection: ...
class Connection(Protocol):
    async def send(self, text: str) -> None: ...
    def __aiter__(self) -> AsyncIterator[str]: ...
    async def close(self) -> None: ...
```

- `Connection.__aiter__` yield chuỗi; khi đóng bình thường, kết thúc vòng lặp **hoặc** ném `ConnectionClosed`.
- Lỗi mở kết nối ném `TransportError`.

Bài cung cấp `FakeTransport` đọc kịch bản; học viên tự viết client, không sửa fake.

## 3. Schema `TransportMessage`

```json
{
  "message_id": "m-001",
  "kind": "request",
  "sender": "agent-a",
  "recipient": "agent-b",
  "created_at": "2026-01-01T00:00:00Z",
  "payload": { "text": "hello" }
}
```

Ràng buộc:

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `message_id` | string | 1–64, khớp `^[A-Za-z0-9._:-]+$` |
| `kind` | string | một trong `request`, `response`, `event`, `error` |
| `sender` | string | 1–64 |
| `recipient` | string | 1–64 |
| `created_at` | string | ISO-8601 có `Z` hoặc offset |
| `payload` | object | bất kỳ JSON object, tối đa 64 KiB sau serialize |

Không chấp nhận trường thừa (`extra=forbid`). Thiếu trường, sai kiểu, sai `kind`, hay payload không phải object → message không hợp lệ.

## 4. Vòng đời

### 4.1. Mở

1. Chuẩn bị `headers = {}`.
2. Nếu `token` là chuỗi khác rỗng: `headers["Authorization"] = f"Bearer {token}"`.
3. Gọi `await transport.connect(uri, headers)`.
4. Nếu `TransportError` → ném `ConnectionError(f"Failed to connect to {uri}")` với `__cause__` là lỗi gốc. Không gọi `close()`.
5. Tạo `A2ASession`; `yield` nó.
6. Trong `finally`: nếu chưa đóng, `await connection.close()` đúng một lần; đặt `closed=True`.

### 4.2. Gửi

1. Nếu `closed` → `SessionClosed`.
2. Validate `message`; sai → `ValueError`, không chạm transport.
3. Serialize JSON compact, `ensure_ascii=False`, khóa theo thứ tự cố định.
4. `await connection.send(text)`; lỗi transport → `SessionError` (giữ `__cause__`), không tự đóng.

### 4.3. Nhận

1. Nếu `closed` → `SessionClosed`.
2. `async for text in connection`:
   - parse JSON; lỗi cú pháp → cảnh báo `RECV_JSON`, bỏ qua;
   - validate schema; lỗi → cảnh báo `RECV_SCHEMA`, bỏ qua;
   - hợp lệ → `yield`.
3. `ConnectionClosed` → `return` (kết thúc sạch).
4. `CancelledError` → lan truyền.
5. Lỗi transport khác → `SessionError`.

Chỉ một iterator `listen()` hoạt động tại một thời điểm; gọi lần hai khi iterator trước chưa kết thúc → `SessionAlreadyListening`.

## 5. Đóng

- `close()` idempotent; gọi nhiều lần chỉ đóng transport một lần.
- Đóng khi đang `listen()` làm generator kết thúc ở lần chờ kế tiếp.
- Sau khi đóng, `send()`/`listen()` mới → `SessionClosed`.
- Context manager không nuốt exception của thân: nếu thân ném `ValueError`, `close()` chạy rồi `ValueError` tiếp tục lan truyền.

## 6. Logging

- Được log: `agent_id`, `uri` (không query string), sự kiện mở/đóng, mã lỗi, số message.
- Không được log: token, header, nội dung payload, chuỗi frame nhận.
- Cảnh báo frame hỏng chỉ ghi độ dài và lý do, không ghi nội dung.

## 7. Ví dụ cụ thể

### 7.1. Phiên thành công

Kịch bản nhận: `msg-ok-1`, `{bad json`, `msg-schema-sai`, `msg-ok-2`, rồi đóng.

```python
async with client.session() as s:
    await s.send(msg_out)
    got = [m async for m in s.listen()]
```

Kết quả:

- `headers == {"Authorization": "Bearer test-token"}` tại `connect`.
- `got` có 2 phần tử: `msg-ok-1`, `msg-ok-2`.
- `warnings == ["RECV_JSON", "RECV_SCHEMA"]`.
- `connection.send` nhận đúng một chuỗi JSON.
- `close_count == 1`.

### 7.2. Token rỗng

`token=None` hoặc `""` → `headers == {}`.

### 7.3. Mở lỗi

`connect` ném `TransportError("refused")`:

- ném `ConnectionError("Failed to connect to ws://fixture/ws")`;
- `__cause__` là `TransportError`;
- `close_count == 0`.

### 7.4. Exception trong thân

```python
with pytest.raises(RuntimeError):
    async with client.session() as s:
        raise RuntimeError("boom")
```

- `RuntimeError` lan truyền;
- `close_count == 1`.

### 7.5. Hủy

Tác vụ bị `task.cancel()` khi đang `listen()`:

- `CancelledError` lan truyền;
- `close_count == 1`;
- không có cảnh báo giả.

### 7.6. Dùng sau đóng

```python
s = ...  # đã thoát context
await s.send(msg)   # SessionClosed
s.listen()          # SessionClosed khi bắt đầu iterate
```

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Token có khoảng trắng | vẫn gắn nguyên `Bearer <token>` |
| 2 | Token chỉ khoảng trắng | coi như khác rỗng, vẫn gắn |
| 3 | URI rỗng | `ValueError` trước khi connect |
| 4 | `listen()` gọi hai lần song song | lần hai `SessionAlreadyListening` |
| 5 | Người dùng `break` khỏi listen | session vẫn mở đến hết context |
| 6 | Transport đóng giữa frame | generator kết thúc sạch |
| 7 | Frame là `null`/mảng | schema sai, bỏ qua |
| 8 | Frame thiếu `payload` | schema sai, bỏ qua |
| 9 | Payload > 64 KiB | `ValueError` khi gửi |
| 10 | Gửi object không serialize | `ValueError` trước transport |
| 11 | `send` khi transport lỗi | `SessionError`, session vẫn mở |
| 12 | `close()` hai lần | transport chỉ đóng một lần |
| 13 | Exception trong `finally` của close | lan truyền, không che exception gốc nếu có |
| 14 | Hủy trong `send` | `CancelledError`, close vẫn chạy |
| 15 | Hai phiên tuần tự | mỗi phiên một kết nối, header độc lập |

## 9. Tiêu chí chấp nhận

- [ ] Kịch bản 7.1 cho đúng 2 message và 2 cảnh báo theo thứ tự.
- [ ] Không log nào chứa `test-token` hay nội dung payload.
- [ ] `close_count == 1` trong mọi nhánh thoát, trừ mở lỗi (`0`).
- [ ] `ConnectionClosed` không bị biến thành lỗi.
- [ ] Frame hỏng không làm mất các frame hợp lệ sau nó.
- [ ] `id`/schema message được kiểm tra chặt, trường thừa bị từ chối.
- [ ] Cùng kịch bản cho cùng chuỗi message và cùng số lần gọi transport.

## 10. Non-goals

- Không cần WebSocket thật hay JWT thật.
- Không cần reconnect, heartbeat, ping/pong.
- Không cần nhiều listener đồng thời.
- Không cần mã hóa đầu cuối.
