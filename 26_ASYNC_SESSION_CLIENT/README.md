# 26 — Phiên bất đồng bộ có vòng đời rõ ràng

## Mục tiêu

Thiết kế client phiên bất đồng bộ kiểu WebSocket bằng `async with`: mở kết nối, gắn token xác thực, gửi/nhận thông điệp có schema, kết thúc generator sạch khi kết nối đóng, và bảo đảm giải phóng tài nguyên đúng một lần trong mọi nhánh lỗi.

## Giá trị

- `async context manager` là hợp đồng vòng đời; viết sai dễ rò rỉ kết nối hoặc nuốt exception.
- Học cách tách transport khỏi logic phiên để test không cần mạng.
- Học phân biệt “kết nối đóng bình thường” với “lỗi kết nối” với “hủy tác vụ”.
- Học không làm rò rỉ token vào log.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (`asyncio`, thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Thành thạo `async with`, async generator, xử lý hủy |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/aegis-ma`
- File nguồn: <https://github.com/triet4p/aegis-ma/blob/master/aegis_ma_core/protocol/client.py>
- Hành vi quan sát được:
  - `@asynccontextmanager async def session(self)` mở `websockets.connect(self.uri, additional_headers=headers)`.
  - `if self._token: headers["Authorization"] = f"Bearer {self._token}"`.
  - `yield session_instance` trong `async with`; khối `finally` luôn ghi log kết thúc.
  - `except WebSocketException as e: raise ConnectionError(f"Failed to connect to {self.uri}: {e}") from e`.
  - `A2ASession.listen()` là async generator: `async for message_str in self._websocket: yield TransportMessage.model_validate_json(message_str)`.
  - Chỉ bắt `json.JSONDecodeError` để bỏ qua frame hỏng; `ConnectionClosed` kết thúc generator bình thường.
  - `send()` dùng `message.model_dump_json()` và ghi log nội dung message.

**Phần là thiết kế của bài:** transport giả lập trong bộ nhớ, schema message cụ thể, chính sách bỏ qua cả frame sai schema, không log nội dung/token, đếm `close()` đúng một lần, lỗi dùng sau khi đóng. Nguồn log cả payload; bài không làm vậy vì dữ liệu có thể nhạy cảm.

## Hành vi bài tập yêu cầu

- `session()` mở đúng một kết nối; nếu mở lỗi, ném `ConnectionError` và không gọi `close()` trên kết nối không tồn tại.
- Token khác rỗng → header `Authorization: Bearer <token>`; token `None`/rỗng → không có header.
- Trong khối `async with`, `send()` gửi đúng JSON; `listen()` yield các message hợp lệ.
- Frame không phải JSON hoặc sai schema → bỏ qua, ghi cảnh báo không chứa nội dung frame.
- Transport đóng → `listen()` kết thúc bình thường, không ném.
- Thoát khối (bình thường hoặc exception) → `close()` đúng một lần; exception của người dùng được giữ nguyên.
- Hủy tác vụ → `close()` vẫn chạy trong `finally`, `CancelledError` lan truyền.
- `send()`/`listen()` sau khi đóng → `SessionClosed`.
- Không tự kết nối lại, không giữ token trong log.

## Phạm vi

Trong phạm vi: client, session, transport in-memory, schema message, test vòng đời.

Ngoài phạm vi: WebSocket thật, JWT thật, reconnect/backoff, heartbeat, nhiều listener đồng thời, xác thực phía server.

## Fixture offline

- `fixtures/scenarios/ok.json`: chuỗi frame nhận, gồm frame hợp lệ, JSON hỏng, schema sai, rồi đóng.
- `fixtures/scenarios/connect-fail.json`, `body-error.json`, `cancel.json`.
- `fixtures/expected/`.
- Không có token thật; dùng `"test-token"`. Không cổng, không mạng.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng vòng đời, schema, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế context manager/generator và kiểm chứng.
