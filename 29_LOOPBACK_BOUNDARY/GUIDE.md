# GUIDE 29 — Thiết kế ranh giới loopback

## 1. Kiến trúc

```
loopback/
├─ policy.py    # hostname_of, host_allowed, origin_allowed, evaluate
├─ asgi.py      # LoopbackBoundary
├─ cli.py       # kiểm tra một tổ hợp
└─ errors.py
fixtures/
```

Tách policy khỏi ASGI. Policy là hàm thuần, test bằng bảng; middleware chỉ lo đọc header và gửi response.

## 2. Vì sao cần cả Host và Origin

- **DNS rebinding**: trang `evil.example` khiến tên miền đó phân giải về `127.0.0.1`; trình duyệt gửi request same-origin tới `http://evil.example:8080` nhưng kết nối tới máy local. Header `Host` là `evil.example:8080`, không nằm trong tập loopback → chặn.
- **Cross-origin forgery**: trang bất kỳ gửi `fetch("http://127.0.0.1:8080/...")`. Request vẫn tới server; API không có CORS nên trình duyệt không cho đọc response, nhưng side effect vẫn xảy ra. `Origin` của trang là `http://evil.example`, không khớp → chặn.

Thiếu một trong hai sẽ hở một hướng.

## 3. Chuẩn hóa

Không dùng `strip()`/cắt tiền tố. Viết `parse_host` theo grammar:

1. Từ chối control (`ord < 0x20`, `0x7f`), whitespace, `@`, `/ \ ? #`.
2. Nếu bắt đầu `[`: tìm `]`; thiếu hoặc `[]` → malformed; parse `ipaddress.IPv6Address`; chỉ chấp nhận loopback `::1`; phần sau `]` phải rỗng hoặc `:port`; junk → malformed.
3. Không ngoặc: 0 colon → host; 1 colon → host + port; >1 colon → malformed (IPv6 phải có ngoặc).
4. `parse_port`: đúng `^[0-9]{1,5}$` và 1…65535; sai → `HOST_PORT`.
5. Hostname ngoài `localhost`/`127.0.0.1` (và `::1` trong ngoặc) → `HOST_NOT_LOOPBACK`.

Đừng dùng `urlsplit` cho Host: `urlsplit("localhost:8080")` hiểu `localhost` là scheme. Host header không phải URL. Với Origin, `urlsplit` là đúng; nhưng phải kiểm tra control, `username/password`, `port`, `path`, `query`, `fragment`, và chuẩn hóa IPv6 loopback qua `ipaddress`.

**Khác nguồn:** nguồn lấy phần trong `]` bất kể junk phía sau và bỏ qua port Host; bài từ chối `[::1]evil`, `localhost:bad`, `::1` không ngoặc.

## 4. ASGI middleware

Khung:

```python
class LoopbackBoundary:
    def __init__(self, app, port):
        self.app, self.port = app, port

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = decode_headers(scope["headers"])
        decision = evaluate(headers.get("host"), headers.get("origin"), self.port)
        if not decision.allowed:
            await send_json(send, 403, {...})
            return
        await self.app(scope, receive, send)
```

`decode_headers` phải phát hiện trùng:

```python
seen = {}
for raw_name, raw_value in scope["headers"]:
    name = raw_name.decode("latin-1").lower()
    value = raw_value.decode("latin-1")
    seen.setdefault(name, []).append(value)
```

Nếu `len(seen.get("host", [])) > 1` → `HOST_DUPLICATE`.

Header tên không phải ASCII?: decode latin-1 không lỗi; tên lạ bị bỏ qua.

## 5. Gửi 403

ASGI yêu cầu gửi `http.response.start` rồi `http.response.body`. Body JSON không khoảng trắng:

```python
body = b'{"code":"LOOPBACK_BOUNDARY_REJECTED","detail":"The request did not originate from the local loopback boundary."}'
```

`content-length` phải là `str(len(body))` encode latin-1/ascii.

## 6. Bẫy thường gặp

- **Dùng `request.client.host`**: không đủ; DNS rebinding vẫn tới từ 127.0.0.1.
- **Chỉ kiểm tra Origin**: request không phải trình duyệt có thể bỏ Origin; Host vẫn cần.
- **Chỉ kiểm tra Host**: cross-origin forgery vẫn xảy ra nếu Host là loopback.
- **Cho phép `https` loopback**: source chỉ cho `http`; HTTPS local có thể là proxy khác, không thuộc ranh giới này.
- **Bỏ qua port Host**: `localhost:bad`/`localhost:99999` phải bị `HOST_PORT`; chỉ port 1…65535 là hợp lệ.
- **Cắt tại `]` mà không kiểm tra phần sau**: `[::1]evil` sẽ bị nhận nhầm là `::1`; phải `HOST_MALFORMED`.
- **Nhận IPv6 không ngoặc**: `::1` là Host grammar sai; chỉ chấp nhận `[::1]`.
- **Trim Host**: ` localhost ` phải bị `HOST_WHITESPACE`, không được `.strip()`.
- **Bỏ qua userinfo/path**: `user@localhost`, `http://localhost` phải bị từ chối.
- **`urlsplit` rồi tin `hostname`**: username/password có thể đánh lừa hiển thị; phải từ chối.
- **Origin `null`**: `urlsplit("null")` không có scheme; phải từ chối.
- **Header trùng**: proxy có thể gửi hai Host; lấy cái đầu có thể bị lợi dụng. Từ chối.
- **Nuốt exception của app**: middleware không được bọc `try/except Exception` quanh `await self.app`.
- **Trả 403 kèm CORS**: không cần; không thêm.

## 7. Gỡ lỗi

- Test bảng policy trước; in `parse_host` (hostname, port, code) cho từng input.
- Test middleware với app giả đếm `called`.
- Kiểm tra scope `websocket` đi qua.
- Kiểm tra body/headers bằng cách thu message ASGI.
- Thử `Origin: http://localhost:8080/foo` — phải bị chặn bởi thiết kế chặt.
- Thử host `::1` không ngoặc — phải bị `HOST_MALFORMED` (khác nguồn, chủ đích).
- Thử `[::1]evil`, `localhost:bad`, `127.0.0.1:99999` — phải bị từ chối, không được lọt thành `::1`/`localhost`.

## 8. Kiểm chứng

```bash
cd 29_LOOPBACK_BOUNDARY
python -m loopback --host localhost:8080 --origin http://localhost:8080 --port 8080
python -m loopback --host evil.example:8080 --origin http://evil.example:8080 --port 8080
python -m loopback --host "[::1]evil" --origin http://localhost:8080 --port 8080
python -m loopback --host "localhost:bad" --origin http://localhost:8080 --port 8080
python -m loopback --host "::1" --origin http://localhost:8080 --port 8080
python -m loopback --host "127.0.0.1:9999" --origin http://127.0.0.1:8080 --port 8080
```

Test:

```bash
python -m unittest discover -s tests -v
```

Harness ASGI tối thiểu:

```python
async def call(mw, headers):
    sent = []
    async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
    async def send(msg): sent.append(msg)
    await mw({"type": "http", "headers": headers, "method": "GET", "path": "/"}, receive, send)
    return sent
```

## 9. Gợi ý

- Viết `evaluate` trả `Decision` thay vì bool để test mã lý do.
- Dùng hằng `LOOPBACK = frozenset({...})`.
- Với `urlsplit`, bắt `ValueError` cả khi parse và khi đọc `.port`.
- Không dùng regex để parse IPv6; đi theo thuật toán nguồn.
- Ghi rõ trong README rằng đây không phải xác thực.

## 10. Mở rộng

1. Thêm kiểm tra cổng trong Host header (khác nguồn, cần cân nhắc proxy).
2. Thêm allowlist hostname cấu hình được.
3. Thêm test tự động cho `Forwarded`.
4. Thêm logging an toàn (không log giá trị header).
5. Chuyển policy sang ngôn ngữ khác, giữ nguyên bảng test.
