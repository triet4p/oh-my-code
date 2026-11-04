# SPEC — CSS contract checker

## Mục tiêu hành vi

Cho một file CSS, xác định theme có định nghĩa đủ các token bắt buộc và có các dấu hiệu phong cách bị cấm/đáng ngờ không. Kết quả gồm danh sách thiếu, danh sách cảnh báo, và mã thoát phân biệt đạt / không đạt / lỗi đầu vào.

## Giao diện dòng lệnh

```text
node check-ui-contract.mjs <path-to-theme.css>
```

- Không có đối số → in `Usage: node check-ui-contract.mjs <path-to-theme.css>` ra `stderr`, thoát `2`.
- Nhiều hơn một đối số → thoát `2` (không âm thầm bỏ qua).
- File không tồn tại hoặc không đọc được → in `ERROR: cannot read <path>` ra `stderr`, thoát `2`.

## Token bắt buộc

Danh sách cố định, giữ đúng thứ tự:

| # | Token | Cách kiểm tra |
|---:|---|---|
| 1 | `--dws-canvas` | khai báo |
| 2 | `--dws-surface-subtle` | khai báo |
| 3 | `--dws-border` | khai báo |
| 4 | `--dws-border-strong` | khai báo |
| 5 | `--dws-text` | khai báo |
| 6 | `--dws-text-muted` | khai báo |
| 7 | `--dws-primary` | khai báo |
| 8 | `--dws-control-height` | khai báo |
| 9 | `--dws-sidebar-width` | khai báo |
| 10 | `:focus-visible` | xuất hiện như selector trong CSS đã bỏ comment |
| 11 | `prefers-reduced-motion` | xuất hiện trong CSS đã bỏ comment |

“Khai báo” nghĩa là khớp `--ten` theo sau (cho phép khoảng trắng) bởi dấu `:`. Ví dụ `--dws-canvas: #fff;` đạt; `var(--dws-canvas)` hoặc `/* --dws-canvas: #fff */` không đạt.

So khớp tên token phải chính xác theo biên: `--dws-border` không được “đạt” nhờ `--dws-border-strong`. Dùng regex có lookahead hoặc so khớp chuỗi có dấu `:` ngay sau tên.

## Cảnh báo

Cảnh báo không ảnh hưởng mã thoát. Thứ tự output cố định:

| # | Điều kiện | Thông điệp |
|---:|---|---|
| 1 | Không có `font-size` giá trị `13px` (không phân biệt hoa thường) | `No explicit 13px base/control text found.` |
| 2 | Không có `height`/`min-height` là `var(--dws-control-height)` hoặc `32px` | `No 32px standard control height found.` |
| 3 | Có `backdrop-filter` hoặc `filter: blur` | `Glass/blur effect found; remove it for this workspace style.` |
| 4 | Có `border-radius` từ `16px` đến `99px` | `Large non-pill radius found; verify it is intentional.` |
| 5 | Có `box-shadow` chứa hai độ dài mà độ dài thứ nhất ≥12px và thứ hai ≥24px | `Heavy card shadow found; prefer border-first separation.` |

Quy ước: `border-radius: 100px` trở lên được coi là pill và **không** cảnh báo (ngưỡng dừng ở 99px), giống regex nguồn.

Ngưỡng bóng đổ là heuristic, không phải hình học tuyệt đối; mục tiêu là bắt `0 24px 48px`. Không cần hiểu `rgba()`.

## Chuẩn hóa trước khi kiểm tra

1. Đọc UTF-8.
2. Bỏ mọi comment dạng `/* ... */` (không lồng nhau trong CSS hợp lệ).
3. Giữ nguyên chuỗi, dấu nháy và xuống dòng.
4. Không resolve `@import`.

Không bỏ comment theo kiểu “xóa từ `/*` đến cuối file” — chỉ xóa đến `*/` gần nhất.

## Định dạng output

- Mỗi cảnh báo một dòng `WARN: <message>` ra `stderr`.
- Nếu thiếu token, một dòng `FAIL: <path> is missing: <token1>, <token2>` ra `stderr`; các token theo thứ tự bảng.
- Nếu không thiếu, một dòng `PASS: <path> contains the required data-workspace theme contract.` ra `stdout`.
- Không in thêm dòng nào khác.

`<path>` là đường dẫn người dùng truyền vào (không resolve tuyệt đối) để output ổn định giữa máy.

## Mã thoát

| Tình huống | Mã |
|---|---:|
| Đạt hợp đồng (có thể có cảnh báo) | 0 |
| Thiếu ít nhất một token bắt buộc | 1 |
| Sai cách dùng, không đọc được file | 2 |

## Ví dụ

`valid.css`:

```css
:root {
  --dws-canvas: #ffffff;
  --dws-surface-subtle: #f7f8fa;
  --dws-border: #d9dde3;
  --dws-border-strong: #b7bec8;
  --dws-text: #111827;
  --dws-text-muted: #5b6472;
  --dws-primary: #2272b9;
  --dws-control-height: 32px;
  --dws-sidebar-width: 240px;
}
button { height: var(--dws-control-height); font-size: 13px; }
button:focus-visible { outline: 2px solid var(--dws-primary); }
@media (prefers-reduced-motion: reduce) { * { transition: none; } }
```

Kết quả:

```text
PASS: valid.css contains the required data-workspace theme contract.
```

exit 0.

`missing.css` chỉ có `--dws-canvas` và `--dws-border-strong`:

```text
FAIL: missing.css is missing: --dws-surface-subtle, --dws-border, --dws-text, --dws-text-muted, --dws-primary, --dws-control-height, --dws-sidebar-width, :focus-visible, prefers-reduced-motion
```

exit 1. Lưu ý `--dws-border` vẫn thiếu dù `--dws-border-strong` có mặt.

`commented.css` có đủ token nhưng tất cả nằm trong `/* ... */` → vẫn FAIL.

`glass.css` đủ token, có `backdrop-filter: blur(8px);` và `border-radius: 24px;` → `PASS` + hai dòng `WARN`, exit 0.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| File rỗng | FAIL với cả 11 mục, exit 1 |
| Chỉ có comment | FAIL với cả 11 mục |
| Token viết hoa (`--DWS-CANVAS`) | không đạt (CSS custom property phân biệt hoa thường) |
| `--dws-canvas : #fff` (khoảng trắng trước `:`) | đạt |
| `--dws-canvasx: 1` | không làm đạt `--dws-canvas` |
| `var(--dws-canvas)` không có khai báo | không đạt |
| `:focus-visible` trong comment | không đạt |
| `prefers-reduced-motion` không có `@media` | vẫn đạt (chỉ cần xuất hiện) |
| Nhiều comment trên nhiều dòng | xóa đúng, không nuốt phần sau |
| Đường dẫn có dấu cách | đọc được nếu truyền đúng một đối số có quote ở shell |
| File không tồn tại | exit 2, không in PASS/FAIL |

## Tiêu chí nghiệm thu

1. Bốn fixture `valid.css`, `missing.css`, `commented.css`, `glass.css` cho đúng output/mã thoát như trên.
2. Có test khẳng định `--dws-border-strong` không thỏa `--dws-border`.
3. Có test khẳng định token trong comment không được tính.
4. Có test khẳng định `var(--dws-canvas)` không được tính là khai báo.
5. Có test cho không đối số → exit 2.
6. Thứ tự token thiếu và thứ tự cảnh báo ổn định.
7. `node --test` xanh.

## Non-goals

- Parse AST CSS hoặc resolve biến.
- Kiểm tra giá trị màu, tương phản WCAG.
- Kiểm tra file HTML/TSX dùng token.
- Đo kích thước thật của sidebar hay control.
- Sửa file CSS.
