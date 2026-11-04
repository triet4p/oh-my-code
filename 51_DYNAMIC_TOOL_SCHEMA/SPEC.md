# SPEC 51 — Sinh lược đồ công cụ động từ registry

## 1. Registry

### 1.1 File

`fixtures/registry_<provider>.json`:

```json
{
  "provider": "finance",
  "tools": [
    {
      "name": "get_quote",
      "description": "Lấy giá hiện tại",
      "method": "GET",
      "endpoint": "/v1/quotes/{symbol}",
      "params": [
        {"name": "symbol", "in": "path", "type": "string", "required": true},
        {"name": "currency", "in": "query", "type": "string", "required": false,
         "enum": ["USD", "EUR"], "default": "USD"}
      ]
    },
    {
      "name": "place_order",
      "description": "Đặt lệnh",
      "method": "POST",
      "endpoint": "/v1/orders",
      "params": [
        {"name": "payload", "in": "body", "type": "object", "required": true,
         "properties": {
           "symbol": {"type": "string", "required": true},
           "qty": {"type": "integer", "required": true},
           "side": {"type": "string", "required": true, "enum": ["buy", "sell"]}
         }}
      ]
    }
  ]
}
```

### 1.2 Trường của tham số

| Trường | Bắt buộc | Giá trị |
|---|---|---|
| `name` | có | `^[a-z][a-z0-9_]*$`, duy nhất trong một công cụ |
| `in` | có | `path`, `query`, `body` |
| `type` | có | `string`, `integer`, `number`, `boolean`, `object` |
| `required` | không (mặc định `false`) | bool |
| `enum` | không | list không rỗng, cùng kiểu với `type` |
| `default` | không | phải thoả `type`/`enum` |
| `properties` | chỉ khi `type == "object"` | bản đồ tên → mô tả con (`type`, `required`, `enum`, `default`) |

Ràng buộc cấu trúc:

- Đúng **một** tham số `in: "body"` mỗi công cụ (hoặc không có).
- Mọi `{placeholder}` trong `endpoint` phải có tham số `in: "path"` cùng tên.
- Mọi tham số `in: "path"` phải xuất hiện trong `endpoint`.
- `endpoint` bắt đầu bằng `/`, không chứa `..`.

### 1.3 Nạp provider

```text
load_provider(name) -> ProviderSpec
```

- `name` phải khớp `^[a-z][a-z0-9_]*$`; sai ⇒ `InvalidProviderName`.
- Chỉ đọc `fixtures/registry_<name>.json`; không dùng `importlib`, không dựng đường dẫn từ chuỗi chưa kiểm tra.
- Tên không tồn tại ⇒ `UnknownProvider(name, available=[...])`, danh sách đã sắp.

## 2. JSON Schema sinh ra

### 2.1 Quy tắc

- Gốc: `{"type": "object", "properties": {...}, "required": [...], "additionalProperties": false, "title": "<Title>Input"}`.
- `title` = `tool.name.title().replace('_', '') + "Input"`; Python `"get_quote".title()` là `"Get_Quote"` ⇒ `"GetQuoteInput"`.
- Chỉ tham số `in: "path"` hoặc `"query"` xuất hiện trực tiếp trong `properties`. Tham số `body` xuất hiện như **một** property kiểu object với `properties` lồng.
- `type` ánh xạ 1-1: `string → "string"`, `integer → "integer"`, `number → "number"`, `boolean → "boolean"`, `object → "object"`.
- `enum` chép nguyên thứ tự khai báo. `default` chép nguyên giá trị.
- `required` là danh sách tên **theo thứ tự khai báo** (không sắp).
- Object lồng cũng có `additionalProperties: false` và `required` riêng.

### 2.2 Ví dụ

Với `get_quote`:

```json
{
  "type": "object",
  "properties": {
    "symbol": {"type": "string"},
    "currency": {"type": "string", "enum": ["USD", "EUR"], "default": "USD"}
  },
  "required": ["symbol"],
  "additionalProperties": false,
  "title": "GetQuoteInput"
}
```

Với `place_order`:

```json
{
  "type": "object",
  "properties": {
    "payload": {
      "type": "object",
      "properties": {
        "symbol": {"type": "string"},
        "qty": {"type": "integer"},
        "side": {"type": "string", "enum": ["buy", "sell"]}
      },
      "required": ["symbol", "qty", "side"],
      "additionalProperties": false
    }
  },
  "required": ["payload"],
  "additionalProperties": false,
  "title": "PlaceOrderInput"
}
```

## 3. Xác thực tham số

```text
validate_args(tool, args: dict) -> dict            # trả args đã áp default, đã ép kiểu
```

Thứ tự kiểm tra:

1. Khóa lạ (không có trong `params` và không phải tên property của body) ⇒ `UnknownParam(key)`.
2. Thiếu tham số `required` ⇒ `MissingParam(name)`.
3. Sai kiểu ⇒ `TypeMismatch(name, expected, got)`.
4. Giá trị ngoài `enum` ⇒ `EnumViolation(name, value)`.
5. Tham số `path` chứa ký tự không an toàn `[^A-Za-z0-9._~-]` ⇒ `UnsafePathValue(name)`.
6. Với `body`: xác thực `properties` theo cùng luật 1–4 (đệ quy một cấp).

Ép kiểu (`[DESIGN]`, để CLI dùng được):

- `string`: nhận `str`; **không** tự ép số thành chuỗi.
- `integer`: nhận `int` (không nhận `bool`); chuỗi số nguyên được ép.
- `number`: nhận `int`/`float` (không nhận `bool`); chuỗi số được ép.
- `boolean`: nhận `bool`; chuỗi `"true"`/`"false"` được ép.
- `object`: nhận `dict`.

Tham số có `default` và không được truyền ⇒ dùng `default` (sau khi xác thực default đó hợp lệ).

## 4. Dựng request

```text
build_request(tool, args) -> {"method": ..., "url": ..., "query": {...}, "json": ... or null}
```

- `validate_args` chạy trước.
- `url` = `endpoint` với mọi `{placeholder}` thay bằng giá trị path (đã escape? **không** — SPEC cấm ký tự nguy hiểm ở 3.5 nên không cần escape).
- `query` = các tham số `in: "query"` đã có giá trị (kể cả từ `default`), khóa sắp theo thứ tự từ điển.
- `json` = giá trị của tham số body (object), hoặc `null` nếu không có body.
- `method` viết hoa như khai báo.

Ví dụ:

```text
build_request(get_quote, {"symbol": "AAPL"})
=> {"method": "GET", "url": "/v1/quotes/AAPL", "query": {"currency": "USD"}, "json": null}

build_request(get_quote, {"symbol": "AAPL", "currency": "EUR"})
=> {"method": "GET", "url": "/v1/quotes/AAPL", "query": {"currency": "EUR"}, "json": null}

build_request(place_order, {"payload": {"symbol": "AAPL", "qty": 10, "side": "buy"}})
=> {"method": "POST", "url": "/v1/orders", "query": {}, "json": {"symbol": "AAPL", "qty": 10, "side": "buy"}}
```

## 5. Phân tích argv

```text
parse_argv(tool, argv: list[str]) -> dict
```

- `--name value` cho tham số có giá trị.
- Với `boolean`: `--flag` ⇒ `true`; `--flag false` hoặc `--flag=false` ⇒ `false`.
- Giá trị chứa dấu cách phải được shell truyền thành một token; parser không xử lý quote.
- Thiếu giá trị ⇒ `MissingValue(flag)`.
- Cờ lạ ⇒ `UnknownFlag(flag)`.
- Cờ trùng ⇒ `DuplicateFlag(flag)`.
- Với body, dùng `--payload '{"symbol":"AAPL","qty":10,"side":"buy"}'` (JSON string) — parser `json.loads` giá trị đó.

## 6. Đầu ra CLI

| Lệnh | In ra |
|---|---|
| `python -m src schema --provider finance --tool get_quote` | JSON Schema (compact, sort_keys) |
| `python -m src validate --provider finance --tool get_quote --args fixtures/args_ok.json` | `{"ok": true, "args": {...}}` |
| `python -m src request --provider finance --tool get_quote --args fixtures/args_ok.json` | object request |
| `python -m src argv --provider finance --tool get_quote -- --symbol AAPL` | `{"symbol": "AAPL"}` |

Lỗi in `{"error": {"code": "...", "message": "..."}}` và mã thoát `2`.

## 7. Kiểm tra hợp lệ (lỗi cấu hình registry)

| Điều kiện | Lỗi |
|---|---|
| provider không khớp regex | `InvalidProviderName` |
| file không tồn tại | `UnknownProvider` |
| endpoint không bắt đầu `/` hoặc chứa `..` | `InvalidEndpoint(tool)` |
| placeholder thiếu tham số path | `UnresolvedPlaceholder(tool, name)` |
| tham số path không có trong endpoint | `UnusedPathParam(tool, name)` |
| nhiều hơn một tham số body | `MultipleBodyParams(tool)` |
| `properties` xuất hiện khi `type != object` | `InvalidParamSpec(name)` |
| `default` không thoả `type`/`enum` | `InvalidDefault(name)` |
| tên tham số trùng | `DuplicateParam(tool, name)` |

Các lỗi này phát hiện **khi nạp** provider, không phải khi gọi.

## 8. Tiêu chí chấp nhận

1. Schema của `get_quote` và `place_order` khớp **từng khóa** với mục 2.2 (so `dict`, không so chuỗi).
2. Ba ví dụ `build_request` ở mục 4 cho đúng object, kể cả `{}` cho query và `null` cho json.
3. `validate_args` phát hiện đủ sáu loại lỗi ở mục 3; mỗi lỗi nêu đúng tên tham số.
4. `parse_argv` xử lý boolean ba dạng (`--flag`, `--flag false`, `--flag=false`) và nêu `UnknownFlag` cho cờ lạ.
5. Nạp `../finance` ⇒ `InvalidProviderName`; `load_provider("khong_ton_tai")` ⇒ `UnknownProvider` kèm danh sách đã sắp.
6. Registry có placeholder chưa khai báo ⇒ `UnresolvedPlaceholder` **lúc nạp**.
7. `symbol = "A/B"` ⇒ `UnsafePathValue`.
8. Không có import `importlib`/`requests` trong mã nguồn.
9. Hai lần chạy cho cùng output JSON.
10. `body` sai kiểu (ví dụ `qty` là chuỗi `"mười"`) ⇒ `TypeMismatch("payload.qty", ...)` với đường dẫn có dấu chấm.

## 9. Non-goals

- Không gọi HTTP; không sinh client code; không hỗ trợ `$ref`/`oneOf`/`allOf`.
- Không auth, header tùy biến, upload file.
- Không dùng `pydantic`/`langchain`; xác thực viết tay.
