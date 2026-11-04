# GUIDE — CSS contract checker

## Bước 0 — Môi trường

```bash
mkdir 05_CSS_CONTRACT_CHECKER/work && cd 05_CSS_CONTRACT_CHECKER/work
printf '{"type":"module","scripts":{"test":"node --test"}}' > package.json
mkdir -p fixtures test
```

Không cần `npm install`.

## Bước 1 — Viết khung CLI trước

Thứ tự xử lý:

1. `process.argv.slice(2)`.
2. Nếu `length !== 1` → usage, `process.exitCode = 2`, `return`.
3. `const target = argv[0]`.
4. Đọc file trong `try/catch`; lỗi → `ERROR`, exit 2.
5. Gọi hàm thuần `checkContract(css)` trả `{ missing, warnings }`.
6. In và đặt exit code.

Tách `checkContract` khỏi I/O ngay từ đầu để test không cần tiến trình con.

Gợi ý chữ ký:

```text
export function checkContract(css) {
  return { missing: string[], warnings: string[] };
}
```

## Bước 2 — Bỏ comment đúng cách

Comment CSS không lồng nhau. Cách an toàn:

- Duyệt chuỗi, tìm `/*`.
- Tìm `*/` kế tiếp.
- Thay cả đoạn bằng một khoảng trắng (không xóa hẳn, để tránh dính hai token hai bên thành một).
- Nếu không có `*/`, bỏ đến cuối file.

Tại sao không dùng `css.replace(/\/\*[\s\S]*?\*\//g, "")`? Nó đúng với comment thông thường, nhưng nếu chuỗi CSS chứa `url("/*")`, regex sẽ hiểu nhầm. Với phạm vi bài này, có thể dùng regex **kèm ghi chú giới hạn**, hoặc viết scanner nhỏ bỏ qua nội dung trong nháy đơn/nháy kép. Bài học nằm ở việc biết giới hạn.

Gợi ý scanner: trạng thái `normal`, `in-single-quote`, `in-double-quote`, `in-comment`; xử lý escape `\\` trong chuỗi.

## Bước 3 — Kiểm tra khai báo token

Với mỗi tên custom property:

- Escape ký tự `-` không cần thiết trong regex nhưng nên dùng `RegExp` với `escape` chuẩn.
- Pattern: tên token, cho phép khoảng trắng, rồi `:`; phía trước không được là ký tự tên token (để tránh `x--dws-canvas:`), phía sau tên phải là biên (để tránh `--dws-canvas-extra`).

Một cách rõ ràng: kiểm tra `declared.has(token)` sau khi thu thập mọi tên khai báo bằng regex:

```text
/(^|[;{]\s*)(--[a-z0-9-]+)\s*:/g
```

Nhưng token có thể sau `{` cùng dòng, sau `;`, hoặc đầu file. Cách này bắt được phần lớn; hãy viết test cho các vị trí đó.

Cách khác đơn giản hơn và ít bẫy: với từng token, kiểm tra `css` có khớp `token` + `\s*:` và ký tự ngay trước token không phải `[\w-]`. Cả hai đều chấp nhận được; chọn một và ghi rõ.

Với `:focus-visible` và `prefers-reduced-motion`, chỉ cần `includes` trên CSS đã bỏ comment. `:focus-visible` nên kiểm tra không nằm trong comment; không cần kiểm tra nó là selector.

## Bước 4 — Cảnh báo

Viết từng kiểm tra độc lập, theo đúng thứ tự bảng SPEC:

1. `/font-size\s*:\s*13px/i`.
2. `/(height|min-height)\s*:\s*(var\(--dws-control-height\)|32px)/i`.
3. `/backdrop-filter|filter\s*:\s*blur/i`.
4. `/border-radius\s*:\s*(1[6-9]|[2-9]\d)px/i`.
5. Bóng đổ: đừng cố viết một regex hoàn hảo. Tách giá trị trong `box-shadow` (đến `;` hoặc `}`), tìm các độ dài `px`, lấy hai độ dài đầu; cảnh báo nếu `first >= 12 && second >= 24`.

Regex nguồn cho bóng đổ phức tạp và dễ âm tính/ dương tính giả. Bài tập cho phép heuristic đơn giản hơn, miễn test mô tả đúng.

Không đưa cảnh báo vào `missing`.

## Bước 5 — In và mã thoát

- Dùng `console.warn` cho `WARN`/`FAIL` (đi stderr), `console.log` cho `PASS`.
- In warning trước, rồi FAIL/PASS, theo thứ tự SPEC.
- `process.exitCode = 1` khi `missing.length > 0`; không gọi `process.exit(1)` ngay, để stdout/stderr flush.
- Lỗi đọc file dùng `process.exitCode = 2` và `return`.

Một cái bẫy: nếu bạn `process.exit(1)` sau `console.warn`, trên một số nền tảng output có thể bị cắt. Dùng `exitCode`.

## Bước 6 — Test

Dùng `node:test`:

- Test hàm thuần với chuỗi CSS inline (nhanh, không I/O).
- Test CLI bằng `spawnSync(process.execPath, [script, fixture])`, kiểm tra `status`, `stdout`, `stderr`.

Các ca bắt buộc:

| Ca | Kỳ vọng |
|---|---|
| valid | status 0, stdout PASS, stderr rỗng |
| missing | status 1, stderr chứa danh sách đúng thứ tự |
| comment-only | status 1, đủ 11 mục |
| `--dws-border-strong` only | thiếu `--dws-border` |
| `var(--dws-canvas)` | thiếu `--dws-canvas` |
| glass | status 0, hai WARN |
| no args | status 2, usage |
| nonexistent | status 2, ERROR |

Gợi ý: so khớp `stderr` bằng `assert.match` với chuỗi escaped, hoặc tách dòng và so mảng.

## Bước 7 — Kiểm chứng độc lập

```bash
node check-ui-contract.mjs fixtures/valid.css; echo "exit=$?"
node check-ui-contract.mjs fixtures/missing.css; echo "exit=$?"
node check-ui-contract.mjs; echo "exit=$?"
node --test
```

Kỳ vọng lần lượt: PASS/exit=0; FAIL/exit=1; usage/exit=2; test xanh.

Kiểm tra token biên bằng tay:

```bash
printf ':root{--dws-border-strong:#000}' > /tmp/x.css
node check-ui-contract.mjs /tmp/x.css; echo "exit=$?"
```

Phải báo thiếu `--dws-border` (và các token khác), không được coi `-strong` là `--dws-border`.

## Bước 8 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Token trong comment vẫn đạt | Chưa bỏ comment hoặc bỏ sai. |
| `--dws-border-strong` làm đạt `--dws-border` | Thiếu biên cuối tên. |
| `var(--x)` làm đạt | Chỉ dùng `includes`, chưa yêu cầu `:`. |
| Cảnh báo làm exit 1 | Gộp warning vào missing. |
| Không có đối số vẫn chạy | Thiếu kiểm tra `argv.length`. |
| PASS in ra stderr | Dùng nhầm `console.error`. |
| Exit code sai dù output đúng | Dùng `process.exit` sớm hoặc quên `exitCode`. |
| Comment nhiều dòng nuốt code | Regex `.*` thay vì `[\s\S]*?`. |

## Bước 9 — Mở rộng

- Thêm `--json` xuất `{missing, warnings, path}` cho CI.
- Thêm `--require-token` để CI chỉ kiểm tra một tập con.
- Thêm kiểm tra token dùng trong `var()` mà không khai báo (phân tích hai chiều).
- Thêm chế độ kiểm tra nhiều file và tổng hợp.
- Nếu đi xa: dùng `postcss` để parse thật, nhưng khi đó phải nêu rõ thay đổi dependency.

## Tự đánh giá

1. Vì sao phải bỏ comment trước khi kiểm tra?
2. Vì sao `includes("--dws-border")` sai với `--dws-border-strong`?
3. Ba mã thoát bảo vệ CI khỏi những lỗi nào?
4. Cảnh báo nên là lỗi cứng trong trường hợp nào? Ai quyết định?
