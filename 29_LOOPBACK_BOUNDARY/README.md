# 29 — Ranh giới API loopback

## Mục tiêu

Viết lớp kiểm tra `Host`/`Origin` cho API chỉ lắng nghe trên loopback, chặn hai lớp tấn công web: DNS rebinding (trang lạ khiến trình duyệt gửi request tới `127.0.0.1` với `Host` ngoài) và cross-origin forgery từ trang web bất kỳ. Kèm middleware ASGI tối giản và bộ test không phụ thuộc framework.

## Giá trị

- Hiểu vì sao “chỉ bind 127.0.0.1” chưa đủ khi trình duyệt là tác nhân.
- Học đọc/chuẩn hóa `Host` và `Origin` đúng cách, kể cả IPv6 trong ngoặc.
- Học rằng đây là **ranh giới web**, không phải xác thực; không thay thế token/authorization.
- Học viết middleware ASGI thuần, không cần Starlette.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (`urllib.parse`, `asyncio`) |
| Độ khó | Trung bình |
| Điều kiện | Hiểu HTTP header, same-origin policy, ASGI cơ bản |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/projecta`
- File nguồn: <https://github.com/triet4p/projecta/blob/main/apps/api/src/projecta_api/loopback_boundary.py>
- Hành vi quan sát được:
  - `LOOPBACK_HOST_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})`.
  - `_hostname` xử lý ngoặc IPv6: nếu bắt đầu `[`, lấy tới `]`; nếu có đúng một `:`, cắt trước `:`; ngược lại lower toàn bộ.
  - `host_header_allowed(None) == False`; Host thiếu bị từ chối.
  - `origin_header_allowed(None) == True`; Origin vắng được phép.
  - Origin phải `scheme == "http"`, không username/password, hostname loopback, `origin_port == port`.
  - Docstring nêu rõ hai tấn công: DNS rebinding và local cross-origin forgery.
  - Middleware trả 403 JSON `{"code": "LOOPBACK_BOUNDARY_REJECTED", "detail": "The request did not originate from the local loopback boundary."}`.

**Phần là thiết kế của bài:** API hàm thuần, mã lý do, middleware ASGI tự viết, kiểm tra path/query của Origin, từ chối header trùng, **Host grammar chặt** (port hợp lệ, không junk sau `]`, không control/whitespace/userinfo, IPv6 phải có ngoặc và đúng loopback), và bộ test. Nguồn dùng Starlette; bài không cần dependency. Nguồn cắt Host tại `]` và bỏ qua port Host; bài cố ý từ chối các Host malformed đó — đây là khác biệt bảo mật có chủ đích, không phải hành vi nguồn.

## Hành vi bài tập yêu cầu

- `parse_host` / `hostname_of` validate cú pháp Host trước khi so hostname: Host có control/whitespace, `@`, `/ \ ? #`, junk sau `]`, thiếu `]`, nhiều colon không ngoặc, port rỗng/không phải số/ngoài 1…65535 đều bị từ chối.
- `host_header_allowed(value)` đúng tập hostname loopback; thiếu → từ chối. Host port chỉ cần đúng cú pháp, không phải khớp port phục vụ.
- `origin_header_allowed(value, port)` theo đúng scheme/port/hostname; thiếu → cho phép; Origin có control/port sai bị từ chối.
- Origin có path khác `/`, query, fragment → từ chối (thiết kế chặt hơn nguồn).
- Middleware chặn trước khi gọi ứng dụng; ứng dụng không bao giờ thấy request bị chặn.
- Header trùng `Host` hoặc `Origin` → từ chối.
- Scope không phải `http` được chuyển tiếp nguyên vẹn.
- Không tin `X-Forwarded-Host`, `Forwarded`, hay tham số query.

## Phạm vi

Trong phạm vi: chuẩn hóa host/origin, quyết định, middleware ASGI, test.

Ngoài phạm vi: xác thực người dùng, TLS, CORS, reverse proxy, rate limit, lọc IP thật.

## Fixture offline

- `fixtures/header-cases.json`: 34 tổ hợp host/origin/port với kết quả mong đợi, gồm Host malformed/port xấu/control.
- `fixtures/asgi-cases.json`: request scope mẫu và response mong đợi.
- Không cần cổng thật; test gọi middleware bằng harness ASGI trong bộ nhớ.

## Liên kết

- [SPEC.md](SPEC.md) — thuật toán, bảng quyết định, ví dụ.
- [GUIDE.md](GUIDE.md) — middleware, bẫy và kiểm chứng.
