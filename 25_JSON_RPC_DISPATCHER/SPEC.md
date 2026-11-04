# SPEC 25 — Dispatcher JSON-RPC 2.0

## 1. API lập trình

```python
dispatcher = Dispatcher()
dispatcher.register("math.add", handler, replace=False)   # handler phải async
await dispatcher.dispatch(payload) -> dict | None
```

- `register(method, handler, *, replace=False)`:
  - `method` khớp `^[A-Za-z][A-Za-z0-9_.-]{0,63}$` và không bắt đầu bằng `rpc.`.
  - handler phải là coroutine function; nếu không → `TypeError`.
  - trùng tên và `replace=False` → `DuplicateMethodError`.
- `dispatch(payload)` không ném lỗi giao thức; luôn trả response hoặc `None`.
- `RpcError(code, message, data=None)` là exception handler dùng để báo lỗi nghiệp vụ.
- `InvalidParams(message, data=None)` là subclass của `RpcError` với code `-32602`.

## 2. Thứ tự xử lý (bắt buộc)

1. Nếu `payload` không phải `dict` → `-32600`, `id: null`; dừng.
2. Xác định `has_id = "id" in payload`, `raw_id = payload.get("id")`, và `echo_id`:
   - `echo_id = raw_id` nếu `raw_id` là `str`, `int` (không phải `bool`), hoặc `None`;
   - ngược lại `echo_id = None` (không thể echo id không hợp lệ).
3. Nếu `jsonrpc` không phải chuỗi `"2.0"` → `-32600`, `id: echo_id`.
4. Nếu có khóa `id` nhưng giá trị không hợp lệ → `-32600`, `id: null`.
5. Nếu `method` không phải chuỗi, rỗng, hoặc bắt đầu bằng `rpc.` → `-32600`, `id: echo_id`.
6. Nếu có `params` và khác `null` nhưng không phải `dict` hoặc `list` → `-32602`, `id: echo_id`. Đây là lỗi **cấu trúc**, chưa phải notification.
7. Đến đây payload là một Request hợp lệ. Đặt `is_notification = not has_id`.
8. Tìm handler:
   - không có: notification → `None`; ngược lại `-32601` với `id: echo_id`.
9. Gọi `await handler(params)` với `params` đã chuẩn hóa (`None` nếu vắng/null). Xử lý kết quả:
   - handler ném `RpcError` → notification trả `None`, ngược lại dùng đúng `code`, `message`, `data` với `id: echo_id`;
   - handler ném `NotImplementedError` → notification trả `None`, ngược lại `-32601`;
   - handler ném exception khác → notification trả `None`, ngược lại `-32603`, message `"Internal error"`, không `data`;
   - kết quả không serialize được bằng `json.dumps` → notification trả `None`, ngược lại `-32603`.
10. Thành công: notification trả `None`; ngược lại trả `{"jsonrpc":"2.0","id":<echo_id>,"result":<result>}`.
11. `id: null` khác notification: có khóa `id` với giá trị `null` vẫn phải trả response `id: null`.

**Precedence tóm tắt:** lỗi cấu trúc (payload/version/id/method/kiểu params) **luôn** tạo response — dùng `echo_id` nếu id hợp lệ, ngược lại `null`. Chỉ sau khi toàn bộ cấu trúc hợp lệ và **không có khóa `id`** mới là notification; mọi lỗi lookup/handler của notification bị nuốt (không output). Payload thiếu `id` nhưng sai cấu trúc (ví dụ `{}`) **không phải** notification.

## 3. Định dạng lỗi

```json
{"jsonrpc":"2.0","id":7,"error":{"code":-32601,"message":"Method not found"}}
```

- `code`: số nguyên.
- `message`: chuỗi 1–200 ký tự; với lỗi nội bộ luôn `"Internal error"`.
- `data`: tùy chọn, phải serialize được; lỗi chuẩn không đặt `data`, trừ `-32602` có thể kèm `{"field": "..."}`.
- Mã nghiệp vụ hợp lệ: `-32099 <= code <= -32000`, hoặc các mã chuẩn.
- Không bao giờ trả `traceback`, `repr(exception)`, hay đường dẫn file.

## 4. Parse và NDJSON runner

CLI:

```bash
python -m rpc_runner --requests fixtures/requests.ndjson --out responses.ndjson
```

- Mỗi dòng không rỗng là một đơn vị JSON.
- Dòng không parse được → response `-32700`, `id: null`.
- Dòng trắng ở giữa file → `-32700` (không bỏ qua âm thầm).
- Dòng cuối có/không newline đều được.
- Dispatcher trả `dict` → ghi đúng một response; trả `None` → không ghi. Chỉ **Request hợp lệ không có `id`** mới là notification; payload thiếu `id` nhưng sai cấu trúc vẫn tạo response lỗi với `id: null`.
- Exit 0 nếu đọc/ghi thành công, kể cả khi có lỗi JSON-RPC; exit 2 nếu file không đọc được; exit 3 nếu không ghi được.

## 5. Ví dụ cụ thể

### 5.1. Thành công

Request:

```json
{"jsonrpc":"2.0","id":1,"method":"math.add","params":{"a":2,"b":3}}
```

Response:

```json
{"jsonrpc":"2.0","id":1,"result":5}
```

### 5.2. Notification

Request:

```json
{"jsonrpc":"2.0","method":"log.write","params":{"text":"hello"}}
```

Không ghi dòng nào. Nếu handler ném lỗi, vẫn không ghi.

### 5.3. `id: null`

Request:

```json
{"jsonrpc":"2.0","id":null,"method":"math.add","params":{"a":1,"b":2}}
```

Response:

```json
{"jsonrpc":"2.0","id":null,"result":3}
```

### 5.4. Method không tồn tại

```json
{"jsonrpc":"2.0","id":2,"method":"missing","params":{}}
```

```json
{"jsonrpc":"2.0","id":2,"error":{"code":-32601,"message":"Method not found"}}
```

### 5.5. Params sai kiểu

```json
{"jsonrpc":"2.0","id":3,"method":"math.add","params":"a=1"}
```

```json
{"jsonrpc":"2.0","id":3,"error":{"code":-32602,"message":"Invalid params"}}
```

### 5.6. Lỗi nghiệp vụ

Handler ném `RpcError(-32001, "Quota exceeded", {"limit": 10})`:

```json
{"jsonrpc":"2.0","id":4,"error":{"code":-32001,"message":"Quota exceeded","data":{"limit":10}}}
```

### 5.7. Lỗi nội bộ

Handler ném `ValueError("/secret/path")`:

```json
{"jsonrpc":"2.0","id":5,"error":{"code":-32603,"message":"Internal error"}}
```

### 5.8. Parse error

Dòng `{bad json`:

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}
```

### 5.9. `jsonrpc` sai

```json
{"jsonrpc":"1.0","id":6,"method":"math.add","params":{}}
```

```json
{"jsonrpc":"2.0","id":6,"error":{"code":-32600,"message":"Invalid Request"}}
```

### 5.10. Payload rỗng — invalid request, không phải notification

```json
{}
```

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Invalid Request"}}
```

### 5.11. Notification hợp lệ, method không tồn tại

```json
{"jsonrpc":"2.0","method":"missing"}
```

Không có output: payload đã qua kiểm tra cấu trúc, không có `id`, nên là notification; lỗi `-32601` bị nuốt.

### 5.12. Params sai kiểu container, không có id

```json
{"jsonrpc":"2.0","method":"math.add","params":"a=1"}
```

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32602,"message":"Invalid params"}}
```

Đây là lỗi cấu trúc trước khi xác định notification, nên vẫn có response `id: null`.

### 5.13. Notification hợp lệ, handler báo invalid params

```json
{"jsonrpc":"2.0","method":"math.add","params":{"a":1}}
```

Nếu handler ném `InvalidParams` vì thiếu `b`, **không có output** vì đây là notification hợp lệ.

### 5.14. Precedence với id hợp lệ

```json
{"jsonrpc":"2.0","id":7,"method":"math.add","params":"a=1"}
```

```json
{"jsonrpc":"2.0","id":7,"error":{"code":-32602,"message":"Invalid params"}}
```

```json
{"jsonrpc":"1.0","id":8,"method":"math.add"}
```

```json
{"jsonrpc":"2.0","id":8,"error":{"code":-32600,"message":"Invalid Request"}}
```

## 6. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Payload là mảng | `-32600`, id null |
| 2 | `id` là `true` | `-32600`, id null |
| 3 | `id` là `1.5` | `-32600`, id null |
| 4 | `id` là số nguyên âm | hợp lệ, echo nguyên |
| 5 | `method` rỗng | `-32600`, id echo/null |
| 6 | `method` bắt đầu `rpc.` | `-32600`, id echo/null |
| 7 | `params` là chuỗi/số/bool | `-32602`, id echo/null |
| 8 | `params` vắng | handler nhận `None` |
| 9 | `params: null` | handler nhận `None` |
| 10 | Handler đồng bộ | `TypeError` lúc đăng ký |
| 11 | Đăng ký trùng, `replace=False` | `DuplicateMethodError` |
| 12 | Đăng ký trùng, `replace=True` | ghi đè, có cảnh báo |
| 13 | Handler trả object chứa `set`/`bytes` | `-32603` (không serialize) |
| 14 | Handler trả `None` | `result: null` |
| 15 | Notification hợp lệ gây exception | không output |
| 16 | `id: null` gây exception | response id null |
| 17 | Handler ném `RpcError` mã `-32000` | hợp lệ |
| 18 | Handler ném `RpcError` mã `-1` | đổi thành `-32603` |
| 19 | Hai request cùng id | độc lập, hai response |
| 20 | Dòng trắng giữa file | `-32700` |
| 21 | Payload `{}` | `-32600`, id null (không phải notification) |
| 22 | `{"jsonrpc":"2.0","method":5}` | `-32600`, id null |
| 23 | Notification hợp lệ + method lạ | không output |
| 24 | Notification hợp lệ + handler `InvalidParams` | không output |
| 25 | Invalid request có id hợp lệ | echo id trong response lỗi |
| 26 | `params` sai container, không id | `-32602`, id null |
| 27 | `id: null` + method lạ | `-32601`, id null |
| 28 | `params` vắng và `params: null` | cùng handler nhận `None` |

## 7. Tiêu chí chấp nhận

- [ ] 14 ví dụ ở mục 5 khớp chính xác sau khi parse JSON (khóa thừa không được có).
- [ ] Notification **hợp lệ** không tạo output, kể cả method lạ hoặc handler lỗi.
- [ ] Payload thiếu `id` nhưng sai cấu trúc (`{}`, version/method/params sai) vẫn tạo lỗi `id: null`.
- [ ] Invalid request có id hợp lệ echo đúng id.
- [ ] `id: null` tạo response.
- [ ] Không response nào chứa traceback, `ValueError`, hay chuỗi `/secret/path`.
- [ ] Handler đồng bộ bị từ chối ngay, không đợi đến lúc gọi.
- [ ] Đăng ký trùng mặc định là lỗi.
- [ ] Response giữ đúng thứ tự dòng của request, chỉ bỏ **notification hợp lệ**; invalid request thiếu id vẫn có response.
- [ ] Cùng fixture cho cùng file response.

## 8. Non-goals

- Không cần batch request.
- Không cần transport thật, TLS, xác thực, phiên.
- Không cần Pydantic hay JSON Schema.
- Không cần streaming kết quả.
