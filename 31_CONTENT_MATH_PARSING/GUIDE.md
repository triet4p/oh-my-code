# GUIDE 31 — Thiết kế tokenizer

## 1. Kiến trúc

```
src/
├─ tokenize.ts     # tokenizeLatex
├─ render.ts       # escapeHtml, placeholderRenderer, renderTokens
├─ index.ts        # renderLatex
└─ cli.ts
fixtures/
tests/
```

Tokenizer không biết HTML; renderer không biết cú pháp `$`. Tách hai lớp giúp test độc lập và thay renderer thật sau này.

## 2. Tokenizer một lượt

Khung:

```ts
let i = 0;
const tokens: Token[] = [];
while (i < input.length) {
  if (input.startsWith("$$", i)) { /* thử display */ }
  if (input[i] === "$" && isDigit(input[i+1])) { /* thử currency */ }
  if (input[i] === "$") { /* thử inline */ }
  pushText(tokens, input[i]); i++;
}
```

Đây là **khung**, không phải lời giải. Chú ý: sau khi thử display thất bại, không được tiêu thụ ký tự; tiếp tục currency/inline.

Gộp text: nếu token cuối là `text`, nối thêm thay vì tạo token mới. Điều này làm output gọn và test dễ.

## 3. Display

```
if startsWith("$$", i):
    end = input.indexOf("$$", i + 2)
    if end >= 0:
        inner = input.slice(i+2, end).trim()
        if inner !== "":
            push({type:"math_display", value: inner})
            i = end + 2
            continue
```

`indexOf` trả `-1` nếu không có. `$$$$`: `end = 2`, `inner=""` → không display; sau đó currency? `$` + next `$` no; inline content empty / `$` → không; text từng ký tự.

## 4. Currency

```
j = i + 1
while digit: j++
if input[j] in ".," and digit(input[j+1]):
    j++
    while digit: j++
suffix = input.slice(j).trimStart()
if startsWithAny(suffix, ["\\times","\\pm","\\ge","\\le"]):
    // không phải currency
else:
    push currency(input.slice(i, j)); i = j; continue
```

Chỉ một dấu thập phân; `$5.00.3` dừng sau `00`.

`trimStart` bỏ mọi whitespace, kể cả newline; source regex `\s*` cũng vậy. Nếu muốn chặt hơn, chỉ bỏ space/tab; bài chọn `\s` để khớp nguồn.

## 5. Inline

```
prev = i === 0 ? "" : input[i-1]
if (i === 0 || !/[A-Za-z0-9_$]/.test(prev)):
    for j = i+1; j < len; j++:
        c = input[j]
        if c === "$": break
        if c === "\n": fail
    if j < len && input[j] === "$" && j > i+1:
        raw = input.slice(i+1, j)
        tex = raw.trim()
        after = input[j+1] ?? ""
        if tex !== "" && !/[A-Za-z0-9_]/.test(after):
            if !vietnamese.test(tex):
                push math_inline(tex)
                i = j+1
                continue
```

Nếu thất bại bất kỳ điều kiện nào, coi `$` là text và tăng `i` 1. Không nhảy qua toàn chuỗi.

Biên trước dùng `[A-Za-z0-9_$]`; source dùng `[^\w\$]` với `\w` gồm `[A-Za-z0-9_]`. Với Unicode, `\w` JavaScript không gồm chữ có dấu; bài định nghĩa ASCII cho rõ. Ghi chú khác biệt.

## 6. Render

`escapeHtml` phải escape `&` trước `<`/`>` để không tạo entity lồng:

```ts
s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
 .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
```

`escapeAttr` dùng cùng hàm là đủ cho `data-tex`.

Currency: `&dollar;` + số (số đã an toàn, nhưng vẫn escape cho nhất quán).

Display: thêm `\n\n` trước/sau. Nếu hai display liền nhau, sẽ có bốn newline; chấp nhận hoặc gộp; bài yêu cầu đúng một cặp `\n\n` mỗi bên.

Renderer lỗi: bắt `unknown`, không bắt `Error` cụ thể; trả text gốc. Với display, text gốc `$$` + tex + `$$`.

## 7. Bẫy thường gặp

- **Chạy inline trước display**: `$$x$$` bị tách thành hai inline/text sai. Display phải trước.
- **Bảo vệ tiền trước display**: `$$5$$` có thể bị currency. Display trước.
- **Regex currency không có negative lookahead**: `$5 \times 3$` bị tách tiền, sai.
- **Negative lookahead không cho khoảng trắng**: `$5  \times` vẫn phải math; dùng `\s*`.
- **Inline cho phép xuống dòng**: công thức tràn đoạn; cấm `\n`.
- **Không kiểm tra ký tự sau `$` đóng**: `$x$y` thành math sai.
- **Không kiểm tra biên trước**: `a$x$` thành math sai.
- **Trim trước khi kiểm tra rỗng**: `$   $` trim rỗng → phải là text.
- **Escape output renderer**: renderer đã trả HTML; escape lại làm hỏng thẻ. Chỉ escape text/currency/fallback.
- **Escape `&dollar;`**: nếu escape toàn output, entity thành `&amp;dollar;`. Render từng token.
- **Tiếng Việt không dấu**: `$gia$` là math; chỉ dấu mới bị loại. Đúng thiết kế.

## 8. Gỡ lỗi

- In token JSON cho từng case; so với fixture.
- Với mỗi case sai, kiểm tra `i` và token trước đó.
- Viết test riêng cho `isCurrencySuffix`.
- Thử renderer ném lỗi; kiểm tra fallback không làm mất prefix.
- Kiểm tra output chứa `<script>` khi input có `<script>` ngoài math: phải là `&lt;script&gt;`.

## 9. Kiểm chứng

```bash
cd 31_CONTENT_MATH_PARSING
npm install        # chỉ lần đầu, cần mạng
npx tsc -p .
node --test dist/tests
node dist/cli.js --input 'Price $5.00 and $x^2$'
```

Nếu không muốn build, dùng `npx tsx src/cli.ts`. Test không được gọi mạng.

Kiểm tra nhanh bằng Node:

```bash
node -e "const {tokenizeLatex}=require('./dist/tokenize'); console.log(JSON.stringify(tokenizeLatex('$5 \\times 3$')))"
```

## 10. Gợi ý

- Viết test bảng trước, đặc biệt các cặp `$5 \times 3$` và `$5 \cdot 3$`.
- Tách hàm `tryDisplay`, `tryCurrency`, `tryInline` trả `{token,next}` hoặc `null`.
- Dùng `String.prototype.startsWith` thay vì so chuỗi con.
- Đừng dùng regex `\w` của JS cho biên nếu muốn hành vi Unicode rõ; dùng lớp ASCII tường minh.
- Renderer mặc định nên là hàm thuần, không phụ thuộc DOM.

## 11. Mở rộng

1. Thay placeholder bằng KaTeX renderer, giữ nguyên tokenizer.
2. Hỗ trợ `\(...\)`/`\[...\]` với ưu tiên riêng.
3. Bỏ qua code fence và inline code.
4. Thêm cảnh báo công thức không cân bằng.
5. Cache render theo `(tex, display)`.
