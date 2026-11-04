# 05 — CSS contract checker: kiểm tra token giao diện bằng CLI

## Mục tiêu

Tự viết một công cụ dòng lệnh đọc file CSS và trả lời: theme có đủ các token thiết kế bắt buộc không, và có dấu hiệu đi ngược quy ước (blur, bo góc lớn, bóng đổ nặng, thiếu cỡ chữ/chiều cao điều khiển chuẩn) không. Công cụ trả mã thoát để dùng được trong CI.

## Giá trị học được

- Một checker tốt phải phân biệt **khai báo** với **nhắc đến**: token nằm trong comment hoặc trong `var(...)` không chứng minh theme định nghĩa nó.
- Thiết kế mã thoát: `0` đạt, `1` không đạt hợp đồng, `2` lỗi cách dùng/đọc file. CI phân biệt được “code sai” và “gọi sai”.
- Cảnh báo không được làm đỏ build; chỉ lỗi hợp đồng mới đỏ.
- Regex cho CSS luôn có bẫy: comment, chuỗi, xuống dòng, khoảng trắng tùy ý.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Node.js 22, ESM, chỉ thư viện chuẩn.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 3–4 giờ.

## Điều kiện tiên quyết và runtime

- Node.js 22+ (có `node:test`, `node:assert`).
- Không cần npm install, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/coding-agent-stacks`, file `.agents/skills/build-databricks-ui/scripts/check-ui-contract.mjs`.
- URL chính xác: <https://github.com/triet4p/coding-agent-stacks/blob/main/.agents/skills/build-databricks-ui/scripts/check-ui-contract.mjs>

Hành vi quan sát được trong nguồn:

- Nhận đường dẫn CSS từ `process.argv[2]`; thiếu thì in usage và `process.exit(2)`.
- Đọc file bằng `readFile` và kiểm tra `css.includes(token)` với danh sách 11 mục: `--dws-canvas`, `--dws-surface-subtle`, `--dws-border`, `--dws-border-strong`, `--dws-text`, `--dws-text-muted`, `--dws-primary`, `--dws-control-height`, `--dws-sidebar-width`, `:focus-visible`, `prefers-reduced-motion`.
- Thu thập cảnh báo nếu thiếu `font-size: 13px`, thiếu chiều cao `32px`/`var(--dws-control-height)`, có `backdrop-filter`/`filter: blur`, có `border-radius` từ 16px trở lên, hoặc có `box-shadow` nặng.
- In `WARN:` cho cảnh báo; nếu thiếu token in `FAIL: ... is missing: ...` và đặt `process.exitCode = 1`; ngược lại in `PASS`.
- Cảnh báo **không** làm thay đổi mã thoát.

## Phạm vi bài tập

Xây `check-ui-contract.mjs`:

- Giữ danh sách token và các ngưỡng cảnh báo.
- Loại comment trước khi kiểm tra.
- Yêu cầu token là **khai báo** (`--ten:`), không chỉ xuất hiện.
- Kiểm tra sự hiện diện của selector `:focus-visible` và media/feature `prefers-reduced-motion`.
- Xuất kết quả ổn định, có test với fixture.

Không nằm trong phạm vi: parse CSS đầy đủ, resolve `@import`, kiểm tra tương phản màu, chạy trình duyệt.

## Liên kết

- [SPEC.md](SPEC.md) — danh sách token, thuật toán, định dạng output, mã thoát.
- [GUIDE.md](GUIDE.md) — thiết kế parser nhỏ, bẫy regex, cách test.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn dùng `includes` trên toàn văn, nên một token trong comment vẫn “đạt”, và `var(--dws-canvas)` cũng làm token “đạt” dù theme không định nghĩa. Bài tập **thắt chặt** bằng cách bỏ comment và yêu cầu khai báo. Đây là khác biệt có chủ đích, không phải hành vi của nguồn.
