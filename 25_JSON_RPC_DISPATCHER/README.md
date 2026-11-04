# 25 — Bộ điều phối JSON-RPC 2.0

## Mục tiêu

Viết dispatcher JSON-RPC 2.0 bất đồng bộ: đăng ký handler theo tên phương thức, xác thực request, gọi handler, ánh xạ lỗi chuẩn, phân biệt notification với request, và không rò rỉ exception nội bộ ra client.

## Giá trị

- JSON-RPC tưởng đơn giản nhưng đầy bẫy: `id: null`, notification, mã lỗi, `params` sai kiểu, handler đồng bộ lẫn vào.
- Học cách thiết kế **biên lỗi** rõ ràng: lỗi giao thức khác lỗi nghiệp vụ khác lỗi nội bộ.
- Học cách giữ bí mật thông tin: client không thấy traceback, đường dẫn, hay thông điệp nội bộ.
- Bài tập chạy hoàn toàn offline trên NDJSON, dễ kiểm thử và so khớp.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (`asyncio`, thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Hiểu `async`/`await`, JSON, đọc đặc tả JSON-RPC 2.0 |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/aegis-ma`
- File nguồn: <https://github.com/triet4p/aegis-ma/blob/master/aegis_ma_core/protocol/dispatcher.py>
- Hành vi quan sát được:
  - `if not asyncio.iscoroutinefunction(handler): raise TypeError(f"Handler for '{skill_id}' must be a coroutine function (async def).")`
  - Đăng ký trùng chỉ ghi cảnh báo rồi ghi đè: `if skill_id in self._handlers: logger.warning(...)`.
  - `request = JSONRPCRequest.model_validate(payload)`; handler lấy `await handler(request.params)`.
  - Không tìm thấy handler: `raise NotImplementedError(...)` → `JSONRPCErrorCode.METHOD_NOT_FOUND`.
  - Lỗi validate: trả `INVALID_REQUEST` với `id = payload.get("id")`.
  - Lỗi khác: `INTERNAL_ERROR`, message cố định `"An internal error occurred on the agent."`.
  - `if request.id is None: return None` — sau khi `JSONRPCRequest.model_validate(payload)` thành công; notification không có phản hồi.
  - Lỗi ở nhánh notification cũng trả `None` (payload validate thất bại **không** phải notification).

**Phần là thiết kế của bài:** đặc tả đầy đủ mã lỗi, từ chối đăng ký trùng mặc định, kiểm tra `params`, NDJSON offline, quy tắc `id` và output xác định. Nguồn dựa vào Pydantic; bài dùng kiểm tra tay để không cần dependency.

**Khác nguồn có chủ đích:** nguồn coi `id: null` như notification vì `request.id is None`; bài phân biệt “vắng khóa `id`” với “`id: null`” và trả response cho trường hợp sau. Nguồn gộp lỗi Pydantic thành `INVALID_REQUEST`; bài phân loại `params` sai kiểu container thành `-32602` (lỗi cấu trúc vẫn có response, kể cả khi không có `id`).

## Hành vi bài tập yêu cầu

- Chỉ chấp nhận handler `async def`; handler đồng bộ bị từ chối ngay lúc đăng ký.
- Đăng ký trùng là lỗi, trừ khi gọi `register(..., replace=True)`.
- Request hợp lệ: object, `jsonrpc == "2.0"`, `method` chuỗi không rỗng, `params` vắng/null/object/array, `id` chuỗi/số nguyên/null.
- **Notification hợp lệ** (Request đã qua toàn bộ kiểm tra cấu trúc, không có khóa `id`) không sinh output, kể cả method không tồn tại hoặc handler lỗi.
- Payload thiếu `id` nhưng **sai cấu trúc** (`{}`, `jsonrpc` sai, `method` sai, `params` sai kiểu) không phải notification: vẫn nhận lỗi với `id` hợp lệ nếu có, ngược lại `id: null`.
- `id: null` là request, phải trả response với `id: null`.
- Lỗi chuẩn: `-32700` parse, `-32600` invalid request, `-32601` method not found, `-32602` invalid params, `-32603` internal.
- Lỗi nghiệp vụ dùng `RpcError(code, message, data)`; mã ngoài dải chuẩn phải nằm trong `-32099…-32000`.
- Không trả traceback hay thông điệp exception gốc cho lỗi nội bộ.

## Phạm vi

Trong phạm vi: registry, validate, dispatch, lỗi, notification, NDJSON runner, test.

Ngoài phạm vi: batch request, transport WebSocket/HTTP thật, xác thực, rate limit, schema Pydantic, JSON-RPC qua nhiều kết nối.

## Fixture offline

- `fixtures/requests.ndjson`: 20 request phủ lỗi và thành công.
- `fixtures/expected.ndjson`: response tương ứng, theo đúng thứ tự.
- `fixtures/handlers.py`: handler mẫu **chỉ phục vụ test**, không phải lời giải dispatcher.
- Không mạng, không cổng, không credential; dữ liệu tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng request/response, thứ tự validate, ví dụ.
- [GUIDE.md](GUIDE.md) — kiến trúc, bẫy và kiểm chứng.
