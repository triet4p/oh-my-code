# GUIDE 25 — Thiết kế dispatcher

## 1. Kiến trúc

```
rpc/
├─ errors.py      # RpcError, InvalidParams, DuplicateMethodError
├─ dispatcher.py  # registry + dispatch
├─ handlers.py    # handler mẫu cho fixture
├─ runner.py      # NDJSON
└─ cli.py
fixtures/
```

`dispatch` chỉ phụ thuộc registry. `runner` chịu trách nhiệm parse dòng và ghi output; đừng trộn parse JSON vào dispatcher nếu muốn test sạch.

## 2. Cấu trúc dữ liệu

```python
@dataclass(frozen=True)
class RpcError(Exception):
    code: int
    message: str
    data: Any = None

handlers: dict[str, Callable[[Any], Awaitable[Any]]]
```

Có thể thêm `RequestView` để phân biệt “không có id” với “id = None”:

```python
has_id = "id" in payload
request_id = payload.get("id")
echo_id = request_id if is_valid_id(request_id) else None
is_notification = not has_id      # chỉ dùng SAU khi toàn bộ cấu trúc đã hợp lệ
```

Đây là điểm quan trọng nhất của bài. Nếu dùng `payload.get("id")` rồi so `is None`, bạn sẽ biến `id: null` thành notification sai. `has_id` một mình cũng chưa đủ: `{}` không có `id` nhưng **không phải** notification vì thiếu `jsonrpc`/`method`; nó phải nhận `-32600` với `id: null`.

## 3. Kiểm tra kiểu

Python coi `bool` là subclass của `int`. Phải viết:

```python
def is_valid_id(value):
    return value is None or isinstance(value, str) or (
        isinstance(value, int) and not isinstance(value, bool)
    )
```

`float` luôn sai, kể cả `1.0`, để tránh mơ hồ.

## 4. Luồng lỗi

Gợi ý dùng một hàm `error_response(request_id, code, message, data=_UNSET)` và một hàm `ok_response`. Tránh dựng dict rải rác.

Thứ tự ưu tiên:

1. Parse (ở runner).
2. Shape/version/id/method/params — **lỗi cấu trúc luôn tạo response** với `echo_id` nếu id hợp lệ, ngược lại `id: null`.
3. Chỉ khi bước 2 sạch: nếu không có khóa `id` thì đây là notification; lookup/invoke lỗi đều trả `None`.
4. Nếu có `id` (kể cả `id: null`), lookup/invoke lỗi tạo response bình thường.

Có thể viết `finish(echo_id, is_notification, response)`, nhưng `is_notification` chỉ được bật sau bước 2. `{}` phải trả `-32600` với `id: null`, không được im lặng.

## 5. Gọi handler

Source truyền nguyên `request.params`, không bind theo tên. Bài giữ cách này để tránh phải viết schema. Handler tự kiểm tra:

```python
async def math_add(params):
    if not isinstance(params, dict):
        raise InvalidParams("params must be an object")
    a, b = params.get("a"), params.get("b")
    if not isinstance(a, (int, float)) or isinstance(a, bool) ...
```

Dispatcher chỉ chịu trách nhiệm kiểu `params` mức giao thức (dict/list/null), không biết nghiệp vụ.

## 6. Bẫy thường gặp

- **Notification hợp lệ lỗi vẫn trả response**: sai. Request đã qua kiểm tra cấu trúc, không có khóa `id` thì im lặng.
- **Payload thiếu `id` nhưng sai cấu trúc bị coi là notification**: sai. `{}` phải nhận `-32600 id:null`; `params` sai container nhận `-32602 id:null`.
- **`id: null` bị coi là notification**: sai. `null` là id hợp lệ.
- **Echo id kiểu bool**: JSON `true` không phải id hợp lệ.
- **Trả `str(e)` cho internal**: rò rỉ. Luôn message cố định.
- **Đăng ký handler sync**: phải kiểm tra `inspect.iscoroutinefunction` hoặc `asyncio.iscoroutinefunction`; gọi thử không đủ.
- **Bắt `BaseException`**: nuốt cả `KeyboardInterrupt`/`CancelledError`. Chỉ bắt `Exception`; để hủy lan truyền.
- **Serialize kết quả sau khi đã gửi**: kiểm tra bằng `json.dumps(result)` trước khi trả.
- **Đăng ký trùng im lặng**: mặc định phải lỗi; `replace=True` mới ghi đè.
- **Dòng trắng bị bỏ qua**: trong fixture, dòng trắng phải là parse error để phát hiện lỗi định dạng.
- **Thứ tự validate**: kiểm tra `jsonrpc` trước `id` có thể làm id hợp lệ bị mất; bài yêu cầu echo id nếu xác định được.

## 7. Gỡ lỗi

- Viết test bảng cho `is_valid_id` và `dispatch` với payload tối thiểu.
- Kiểm tra `"id" in payload` bằng test riêng.
- Chạy fixture, so từng dòng bằng `json.loads` (không so chuỗi thô nếu key order khác).
- Thêm log nội bộ có `request_id` nhưng không đưa vào response.
- Thử handler trả `set()` để chắc `-32603`.
- Thử handler raise `asyncio.CancelledError`; phải lan truyền, không thành `-32603`.

## 8. Kiểm chứng độc lập

```bash
cd 25_JSON_RPC_DISPATCHER
python -m rpc_runner --requests fixtures/requests.ndjson --out /tmp/responses.ndjson
python - <<'PY'
import json
req=[]; parse_errors=0
for line in open('fixtures/requests.ndjson', encoding='utf-8'):
    if not line.strip():
        parse_errors += 1
        continue
    try: req.append(json.loads(line))
    except json.JSONDecodeError: parse_errors += 1
res=[json.loads(l) for l in open('/tmp/responses.ndjson', encoding='utf-8')]
def structurally_valid(r):
    return (
        isinstance(r, dict)
        and r.get('jsonrpc') == '2.0'
        and isinstance(r.get('method'), str) and r['method']
        and not r['method'].startswith('rpc.')
        and ('params' not in r or r['params'] is None or isinstance(r['params'], (dict, list)))
        and ('id' not in r or r['id'] is None or isinstance(r['id'], str)
             or (isinstance(r['id'], int) and not isinstance(r['id'], bool)))
    )
expected = parse_errors + sum(1 for r in req if ('id' in r) or not structurally_valid(r))
assert len(res) == expected, (len(res), expected)
assert all(r['jsonrpc']=='2.0' for r in res)
print(len(req), 'parsed requests,', parse_errors, 'parse errors ->', len(res), 'responses')
PY
```

Chú ý: request thiếu `id` nhưng **không** structurally valid vẫn phải có response (`id: null`); đừng đếm đơn giản theo `'id' in r`.

Test:

```bash
python -m unittest discover -s tests -v
```

Nếu so khớp file expected, dùng parse JSON và so object, không so byte, trừ khi bạn đã cố định `separators` và thứ tự khóa.

## 9. Gợi ý

- Bắt đầu bằng `dispatch` với registry rỗng; test lỗi trước, thành công sau.
- Tách `_validate_request(payload) -> (echo_id, method, params, is_notification) | error`; `is_notification` chỉ được `True` khi toàn bộ kiểm tra cấu trúc đã qua và payload không có khóa `id`.
- Dùng sentinel `_MISSING` cho `data` để phân biệt “không có data” và `data: null`.
- Đừng cố hỗ trợ batch trong lõi; nếu muốn, thêm lớp ngoài.

## 10. Mở rộng

1. Thêm batch request đúng chuẩn, gồm mảng rỗng → `-32600`.
2. Thêm decorator `@method("name")` để đăng ký.
3. Thêm schema params bằng `inspect.signature`.
4. Thêm timeout mỗi handler; map timeout thành mã nghiệp vụ.
5. Thêm middleware logging có correlation id, không lộ ra client.
