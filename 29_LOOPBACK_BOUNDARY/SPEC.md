# SPEC 29 — Ranh giới Host/Origin loopback

## 1. Hàm thuần

```python
def parse_host(value: str | None) -> HostParse
def hostname_of(value: str | None) -> str | None
def host_header_allowed(value: str | None) -> bool
def origin_header_allowed(value: str | None, port: int) -> bool
def evaluate(host: str | None, origin: str | None, port: int) -> Decision
```

`HostParse` được định nghĩa ở mục 2; `hostname_of` là tiện ích trả `None` khi cú pháp sai.

`Decision`:

```python
@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str          # ALLOWED hoặc mã từ chối
    detail: str
```

## 2. Host grammar

```python
@dataclass(frozen=True)
class HostParse:
    grammar_ok: bool          # cú pháp Host hợp lệ, kể cả hostname ngoài loopback
    hostname: str | None
    port: int | None
    code: str                 # ALLOWED hoặc lý do từ chối

def parse_host(value: str | None) -> HostParse
def hostname_of(value: str | None) -> str | None
```

`hostname_of` trả hostname đã chuẩn hóa nếu cú pháp hợp lệ, ngược lại `None`. Hostname ngoài loopback vẫn có thể trả về (để `host_header_allowed` từ chối), nhưng hostname malformed thì `None`.

Thuật toán:

1. `None` → `HOST_MISSING`.
2. Chuỗi rỗng → `HOST_MALFORMED`.
3. Nếu có ký tự `ord(ch) < 0x20` hoặc `ord(ch) == 0x7f` → `HOST_CONTROL`.
4. Nếu có bất kỳ whitespace nào (space, tab, …) → `HOST_WHITESPACE`. Không trim; Host có khoảng trắng là không hợp lệ.
5. Nếu có `@` → `HOST_USERINFO`.
6. Nếu có `/`, `\`, `?`, hoặc `#` → `HOST_SCHEME_OR_PATH`.
7. Nếu bắt đầu `[`:
   1. Tìm `]`; không có, hoặc `]` ngay sau `[` → `HOST_MALFORMED`.
   2. `literal = value[1:end]`; parse `ipaddress.IPv6Address(literal)`; lỗi → `HOST_MALFORMED`.
   3. Nếu địa chỉ khác `IPv6Address("::1")` → `HOST_NOT_LOOPBACK` (nhưng hostname = dạng chuẩn của literal).
   4. `rest = value[end+1:]`:
      - rỗng → không port;
      - bắt đầu `:` → `parse_port(rest[1:])`;
      - còn lại (junk sau `]`) → `HOST_MALFORMED`.
8. Ngược lại (không ngoặc):
   1. `value.count(":") == 0` → `host = value.lower()`, không port.
   2. `count == 1` → tách `host, port_text`; `parse_port(port_text)`.
   3. `count > 1` → `HOST_MALFORMED` (bao gồm IPv6 không ngoặc như `::1`).
   4. `host` rỗng → `HOST_MALFORMED`.
   5. `host` không thuộc `{"localhost", "127.0.0.1"}` → `HOST_NOT_LOOPBACK` (hostname vẫn trả về).
9. `parse_port(text)`:
   - phải khớp `^[0-9]{1,5}$`;
   - `1 <= int(text) <= 65535`;
   - sai → `HOST_PORT`.

`HOST_NOT_LOOPBACK` là cú pháp hợp lệ nhưng hostname ngoài tập. `HOST_MALFORMED` là cú pháp sai (junk sau `]`, nhiều colon, thiếu `]`, host rỗng).

**Khác nguồn (có chủ đích):** nguồn cắt tại `]` nên `[::1]evil` thành `::1`; nguồn bỏ qua port Host nên `localhost:bad` thành `localhost`; nguồn chấp nhận `::1` không ngoặc. Bài từ chối cả ba để dạy Host grammar. Nguồn cũng không kiểm tra ký tự điều khiển/userinfo; bài từ chối.

## 3. `host_header_allowed`

- `None` → `False`.
- `parse_host(value)` phải `grammar_ok` và hostname thuộc `{"127.0.0.1", "localhost", "::1"}`.
- Port Host (nếu có) chỉ được **validate cú pháp** 1…65535, không bắt buộc bằng port phục vụ. `127.0.0.1:9999` vẫn được chấp nhận nếu kết nối thực tế tới đúng cổng phục vụ; đây là giới hạn đã biết.
- Từ chối `localhost.`, `127.0.0.1.nip.io`, `evil-localhost`, `::1` không ngoặc, `[::1]evil`, `localhost:bad`, `localhost:8080:90`.
- Chấp nhận IPv6 loopback viết đầy đủ trong ngoặc, ví dụ `[0:0:0:0:0:0:0:1]:8080`, và chuẩn hóa về `::1`.

## 4. `origin_header_allowed`

- `None` → `True`.
- Chuỗi rỗng hoặc có ký tự điều khiển (`ord < 0x20` hoặc `0x7f`) → `False` (`ORIGIN_MALFORMED`).
- Parse bằng `urlsplit`; lỗi → `False`.
- `scheme` phải đúng `http` (không phải `https`, `file`, `null`).
- `username`/`password` phải rỗng.
- `hostname`:
  - `localhost` hoặc `127.0.0.1` → hợp lệ;
  - nếu là IPv6 (chứa `:`), parse `ipaddress.IPv6Address`; chỉ chấp nhận `::1` (chuẩn hóa từ dạng đầy đủ); lỗi/khác → `False`.
- `port` parse được; `ValueError` → `False`; phải bằng `port` phục vụ; `port` phục vụ phải trong 1…65535.
- `path` phải `""` hoặc `"/"`; `query` và `fragment` phải rỗng.
- Không có Origin (same-origin GET/HEAD và client không phải trình duyệt) được phép.

## 5. Mã quyết định

| Code | Điều kiện | HTTP |
|---|---|---|
| `ALLOWED` | cả hai qua | — |
| `HOST_MISSING` | Host `None` | 403 |
| `HOST_CONTROL` | Host có ký tự điều khiển | 403 |
| `HOST_WHITESPACE` | Host có khoảng trắng | 403 |
| `HOST_USERINFO` | Host có `@` | 403 |
| `HOST_SCHEME_OR_PATH` | Host có `/`, `\`, `?`, `#` | 403 |
| `HOST_MALFORMED` | cú pháp Host sai (junk sau `]`, nhiều colon, thiếu `]`, host rỗng) | 403 |
| `HOST_PORT` | port Host sai cú pháp/ngoài 1…65535 | 403 |
| `HOST_NOT_LOOPBACK` | hostname cú pháp hợp lệ nhưng ngoài tập | 403 |
| `HOST_DUPLICATE` | nhiều header Host (middleware) | 403 |
| `ORIGIN_DUPLICATE` | nhiều header Origin (middleware) | 403 |
| `ORIGIN_MALFORMED` | Origin rỗng/control/urlsplit lỗi/port lỗi | 403 |
| `ORIGIN_SCHEME` | scheme != `http` | 403 |
| `ORIGIN_USERINFO` | có username/password | 403 |
| `ORIGIN_NOT_LOOPBACK` | hostname ngoài tập | 403 |
| `ORIGIN_PORT` | port thiếu/khác | 403 |
| `ORIGIN_PATH` | path/query/fragment không hợp lệ | 403 |

Ưu tiên: Host trước, rồi Origin. Chỉ trả một mã.

## 6. Middleware ASGI

```python
class LoopbackBoundary:
    def __init__(self, app, port: int): ...
    async def __call__(self, scope, receive, send): ...
```

- `scope["type"] != "http"` → gọi app trực tiếp.
- `port` phải trong 1…65535; sai → `ValueError` ngay khi tạo middleware/CLI.
- Đọc header từ `scope["headers"]` (danh sách `(bytes, bytes)`), decode `latin-1`, lower tên.
- Nếu có nhiều `host` hoặc nhiều `origin` → từ chối tương ứng (`HOST_DUPLICATE`/`ORIGIN_DUPLICATE`) trước khi parse.
- Gọi `evaluate(host, origin, port)`; `parse_host` chịu trách nhiệm grammar Host.
- Từ chối: gửi response 403, body JSON UTF-8:

```json
{"code":"LOOPBACK_BOUNDARY_REJECTED","detail":"The request did not originate from the local loopback boundary."}
```

  headers: `content-type: application/json; charset=utf-8`, `content-length`.
- Cho phép: gọi app với scope/receive/send nguyên vẹn.
- Không thêm CORS header.

## 7. Ví dụ cụ thể

Port phục vụ `8080`.

| Host | Origin | Kết quả | Code |
|---|---|---|---|
| `localhost:8080` | `http://localhost:8080` | cho phép | `ALLOWED` |
| `127.0.0.1:8080` | `http://127.0.0.1:8080` | cho phép | `ALLOWED` |
| `[::1]:8080` | `http://[::1]:8080` | cho phép | `ALLOWED` |
| `localhost:8080` | `null` | từ chối | `ORIGIN_MALFORMED` |
| `localhost:8080` | `https://localhost:8080` | từ chối | `ORIGIN_SCHEME` |
| `localhost:8080` | `http://localhost:8081` | từ chối | `ORIGIN_PORT` |
| `localhost:8080` | `http://localhost` | từ chối | `ORIGIN_PORT` |
| `localhost:8080` | `http://user@localhost:8080` | từ chối | `ORIGIN_USERINFO` |
| `localhost:8080` | `http://localhost:8080/app` | từ chối | `ORIGIN_PATH` |
| `localhost:8080` | `http://localhost:8080/?x=1` | từ chối | `ORIGIN_PATH` |
| `[::1]evil` | `http://localhost:8080` | từ chối | `HOST_MALFORMED` |
| `localhost:bad` | `http://localhost:8080` | từ chối | `HOST_PORT` |
| `localhost:8080:90` | `http://localhost:8080` | từ chối | `HOST_MALFORMED` |
| `user@localhost:8080` | `http://localhost:8080` | từ chối | `HOST_USERINFO` |
| `localhost:0` | `http://localhost:8080` | từ chối | `HOST_PORT` |
| `localhost:65536` | `http://localhost:8080` | từ chối | `HOST_PORT` |
| `::1` | `http://localhost:8080` | từ chối | `HOST_MALFORMED` |
| `[::2]:8080` | `http://localhost:8080` | từ chối | `HOST_NOT_LOOPBACK` |
| ` localhost ` | `http://localhost:8080` | từ chối | `HOST_WHITESPACE` |
| `[0:0:0:0:0:0:0:1]:8080` | `http://[0:0:0:0:0:0:0:1]:8080` | cho phép | `ALLOWED` |
| `evil.example:8080` | `http://evil.example:8080` | từ chối | `HOST_NOT_LOOPBACK` |
| `127.0.0.1.evil.example` | — | từ chối | `HOST_NOT_LOOPBACK` |
| — (thiếu) | — | từ chối | `HOST_MISSING` |
| `localhost:8080` | — (thiếu) | cho phép | `ALLOWED` |

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Host `" localhost "` | `HOST_WHITESPACE` (không trim) |
| 2 | Host `"LOCALHOST:8080"` | cho phép |
| 3 | Host `"localhost."` | `HOST_NOT_LOOPBACK` |
| 4 | Host `"[::1]"` | cho phép |
| 5 | Host `"::1"` | `HOST_MALFORMED` (IPv6 phải có ngoặc; khác nguồn) |
| 6 | Host `"[0:0:0:0:0:0:0:1]:8080"` | cho phép, chuẩn hóa `::1` |
| 7 | Host `"127.0.0.1:abc"` | `HOST_PORT` (khác nguồn) |
| 8 | Host `"[::1]evil"` | `HOST_MALFORMED` |
| 9 | Host `"[::1]evil:8080"` | `HOST_MALFORMED` |
| 10 | Host `"localhost:8080:90"` | `HOST_MALFORMED` |
| 11 | Host `"[::1]:"` | `HOST_PORT` |
| 12 | Host `"localhost:0"` | `HOST_PORT` |
| 13 | Host `"localhost:65536"` | `HOST_PORT` |
| 14 | Host `"user@localhost"` | `HOST_USERINFO` |
| 15 | Host `"localhost/path"` | `HOST_SCHEME_OR_PATH` |
| 16 | Host `"localhost\t"` | `HOST_CONTROL` |
| 17 | Host rỗng | `HOST_MALFORMED` |
| 18 | Host `"127.0.0.1:9999"` | cho phép nếu cú pháp hợp lệ; port Host không phải port phục vụ |
| 19 | Origin `"http://LOCALHOST:8080"` | cho phép (urlsplit lower) |
| 20 | Origin `"http://localhost:8080/"` | cho phép |
| 21 | Origin `"http://localhost:8080/#x"` | `ORIGIN_PATH` |
| 22 | Origin `"http://localhost:8080?x=1"` | `ORIGIN_PATH` |
| 23 | Origin `"http://localhost:99999"` | `ORIGIN_MALFORMED` |
| 24 | Origin `"file:///tmp/x"` | `ORIGIN_SCHEME` |
| 25 | Origin `""` | `ORIGIN_MALFORMED` |
| 26 | Origin `"http://[0:0:0:0:0:0:0:1]:8080"` | cho phép, chuẩn hóa `::1` |
| 27 | Hai header Host | `HOST_DUPLICATE` |
| 28 | Hai header Origin, cả hai hợp lệ | `ORIGIN_DUPLICATE` |
| 29 | Scope `websocket` | chuyển tiếp, không kiểm tra |
| 30 | App ném exception | middleware không nuốt |
| 31 | `port=0` | `ValueError` khi tạo middleware/CLI |
| 32 | Origin `"http://[::1]"` thiếu port | `ORIGIN_PORT` |
| 33 | Host `"[::1]:65535"` | cho phép |
| 34 | Host `"localhost: 80"` | `HOST_WHITESPACE` |

## 9. Tiêu chí chấp nhận

- [ ] Bảng mục 7 khớp 100%.
- [ ] 34 trường hợp biên khớp.
- [ ] `hostname_of("[::1]evil")` và `hostname_of("localhost:bad")` trả `None`.
- [ ] `hostname_of("::1")` trả `None`; IPv6 không ngoặc bị từ chối.
- [ ] Host có port sai cú pháp/ngoài 1…65535 bị `HOST_PORT`.
- [ ] Host có control/whitespace/userinfo/path bị từ chối với đúng mã.
- [ ] Middleware không gọi app khi từ chối (đếm bằng cờ trong app giả).
- [ ] Middleware gọi app đúng một lần khi cho phép.
- [ ] Body 403 khớp byte JSON (không khoảng trắng thừa) và `content-type` đúng.
- [ ] Header trùng bị từ chối.
- [ ] Scope `lifespan`/`websocket` đi qua.
- [ ] Không đọc `x-forwarded-host`.

## 10. Non-goals

- Không phải cơ chế xác thực/ủy quyền.
- Không chống tấn công từ tiến trình local độc hại.
- Không cấu hình CORS, TLS, reverse proxy.
- Không so khớp port trong Host với port phục vụ; chỉ validate cú pháp port 1…65535. Origin port vẫn phải khớp.
