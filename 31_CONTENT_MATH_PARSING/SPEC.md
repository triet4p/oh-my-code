# SPEC 31 — Tokenizer công thức và tiền tệ

## 1. API

```ts
type Token =
  | { type: "text"; value: string }
  | { type: "currency"; value: string }          // "$5.00"
  | { type: "math_inline"; value: string }       // đã trim
  | { type: "math_display"; value: string };     // đã trim

function tokenizeLatex(input: string): Token[];
function renderTokens(tokens: Token[], renderMath?: MathRenderer): string;
function renderLatex(input: string, renderMath?: MathRenderer): string;

type MathRenderer = (tex: string, display: boolean) => string;
```

Renderer mặc định:

```ts
function placeholderRenderer(tex: string, display: boolean): string {
  const escaped = escapeHtml(tex);
  const attr = escapeAttr(tex);
  return display
    ? `<div class="math-display" data-tex="${attr}">${escaped}</div>`
    : `<span class="math-inline" data-tex="${attr}">${escaped}</span>`;
}
```

## 2. Ưu tiên token

Tại mỗi vị trí `i` trong chuỗi, xét theo thứ tự:

1. **Display**: `input.startsWith("$$", i)`.
   - Tìm `$$` kế tiếp từ `i+2`.
   - Nếu không có → không phải display; sang bước 2.
   - Nếu có: `inner = input.slice(i+2, end)`; `trim()`.
   - Nếu `inner` rỗng → không phải display; sang bước 2 (hai ký tự `$` có thể là hai currency/inline).
   - Ngược lại token `math_display`, tiêu thụ đến `end+2`.
2. **Currency**: `input[i] === "$"` và ký tự sau là chữ số `[0-9]`.
   - Đọc `[0-9]+`, sau đó nếu có `[.,][0-9]+` thì đọc tiếp **một** lần.
   - Xét hậu tố ngay sau số: bỏ qua khoảng trắng (` `, `\t`); nếu bắt đầu bằng `\times`, `\pm`, `\ge`, `\le` → **không** phải currency.
   - Ngược lại token `currency`, giá trị gồm `$` + phần số.
3. **Inline**: `input[i] === "$"`.
   - Biên trước: `i === 0` hoặc ký tự `i-1` không khớp `[A-Za-z0-9_$]`.
   - Tìm `$` đóng trong đoạn không chứa `$` hoặc `\n`, bắt đầu từ `i+1`.
   - Nội dung thô phải khác rỗng; `trim()` khác rỗng.
   - Ký tự ngay sau `$` đóng (nếu có) không được là `[A-Za-z0-9_]`.
   - Nếu nội dung trim khớp regex dấu tiếng Việt → **không** tạo math; phần `$...$` là text (token text gộp).
   - Ngược lại token `math_inline`, giá trị là trim.
4. **Text**: gom ký tự hiện tại vào token text, gộp với token text trước nếu có.

Không dùng regex toàn chuỗi cho cả ba loại; ưu tiên tuần tự tránh chồng lấn.

## 3. Regex dấu tiếng Việt

Tập ký tự (không phân biệt hoa thường):

```text
à á ả ã ạ ă ằ ắ ẳ ẵ ặ â ầ ấ ẩ ẫ ậ
è é ẻ ẽ ẹ ê ề ế ể ễ ệ
ì í ỉ ĩ ị
ò ó ỏ õ ọ ô ồ ố ổ ỗ ộ ơ ờ ớ ở ỡ ợ
ù ú ủ ũ ụ ư ừ ứ ử ữ ự
ỳ ý ỷ ỹ ỵ đ
```

Nếu bất kỳ ký tự nào thuộc tập xuất hiện trong nội dung inline → coi là văn bản, không phải công thức.

## 4. Render

- Token `text`: `escapeHtml(value)` (`&`, `<`, `>`, `"`, `'`).
- Token `currency`: `"&dollar;" + escapeHtml(phần số)`.
- Token `math_inline`/`math_display`: gọi renderer.
  - Renderer ném lỗi → phát ra text gốc: inline `"$" + tex + "$"`, display `"$$" + tex + "$$"`, đã escape.
- Display bọc thêm `"\n\n"` trước và sau để tách block Markdown.
- Không escape lại output của renderer; hợp đồng của renderer là trả HTML an toàn.

## 5. Ví dụ cụ thể

### 5.1. Tiền

Input: `Price is $5.00 and $0.042, total $150.80.`

Tokens:

```json
[
  {"type":"text","value":"Price is "},
  {"type":"currency","value":"$5.00"},
  {"type":"text","value":" and "},
  {"type":"currency","value":"$0.042"},
  {"type":"text","value":", total "},
  {"type":"currency","value":"$150.80"},
  {"type":"text","value":"."}
]
```

Output:

```html
Price is &dollar;5.00 and &dollar;0.042, total &dollar;150.80.
```

### 5.2. Công thức đơn

Input: `Formula $x^2$ and $$\\sum_i x_i$$ done.`

- `math_inline` `x^2`
- `math_display` `\sum_i x_i`

Output (placeholder):

```html
Formula <span class="math-inline" data-tex="x^2">x^2</span> and 

<div class="math-display" data-tex="\sum_i x_i">\sum_i x_i</div>

 done.
```

### 5.3. Tiền đứng trước toán tử

| Input | Kết quả |
|---|---|
| `$5 \\times 3$` | math inline `5 \times 3` |
| `$5 \\pm 3$` | math inline `5 \pm 3` |
| `$5 \\ge 3$` | math inline `5 \ge 3` |
| `$5 \\le 3$` | math inline `5 \le 3` |
| `$5 \\cdot 3$` | currency `$5`, text ` \cdot 3$` |
| `$5$` | currency `$5`, text `$` |

### 5.4. Biên

| Input | Tokens |
|---|---|
| `$x$` | math inline `x` |
| `a$x$` | text `a$x$` (biên trước là word) |
| `($x$)` | text `(`, math `x`, text `)` |
| `$x$y` | text `$x$y` (đóng theo sau word) |
| `$x$ y` | math `x`, text ` y` |
| `$ x $` | math `x` |
| `$x\ny$` | text (xuống dòng) |
| `$x$ $y$` | math `x`, text ` `, math `y` |
| `$$x$$` | math display `x` |
| `$$$$` | text `$$$$` |
| `$$ x $$` | math display `x` |
| `$$x` | text `$$x` |

### 5.5. Tiếng Việt

| Input | Kết quả |
|---|---|
| `$giá$` | text `$giá$` |
| `$đường$` | text `$đường$` |
| `$Đường$` | text `$Đường$` |
| `$x + giá$` | text |
| `$x + y$` | math |

### 5.6. Renderer lỗi

Với renderer ném lỗi khi gặp `\bad`:

- Input `$\\bad$` → text `$\bad$` đã escape.
- Input `$$\\bad$$` → text `$$\bad$$`.

## 6. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Input rỗng | `[]`; output `""` |
| 2 | Chỉ `$` | text `$` |
| 3 | `$$` | text `$$` |
| 4 | `$5.` | currency `$5`, text `.` |
| 5 | `$5,000` | currency `$5,000` |
| 6 | `$5.00.3` | currency `$5.00`, text `.3` |
| 7 | `$5x` | currency `$5`, text `x` |
| 8 | `$$5$$` | display `5` (display thắng) |
| 9 | `$$$x$$$` | display? bắt đầu `$$`, tìm `$$` tại vị trí 5? Nội dung `$x`, token display `$x`; còn `$`. Test cụ thể |
| 10 | `$\\alpha$` | math |
| 11 | `$a<b$` | math; renderer escape |
| 12 | Text `<script>` ngoài math | escaped |
| 13 | Data-tex chứa `"` | escape thành `&quot;` |
| 14 | Renderer trả chuỗi rỗng | giữ chuỗi rỗng (hợp đồng renderer) |
| 15 | Hai display liền nhau | hai token display |
| 16 | Display chứa `$$` bên trong | dừng ở cặp gần nhất |
| 17 | Inline chứa `$` | không khớp; text |
| 18 | Inline chứa tab | được phép (chỉ cấm `\n` và `$`) |
| 19 | Prefix là `_` | không math (word) |
| 20 | Prefix là `-` | math |

## 7. Tiêu chí chấp nhận

- [ ] 5 bảng ví dụ khớp token chính xác.
- [ ] `$5 \times 3$` là math, `$5 \cdot 3$` là currency + text.
- [ ] Tiếng Việt có dấu không bao giờ thành math.
- [ ] Không có `<script>` nào từ input đi vào output.
- [ ] `data-tex` escape đúng `"` và `&`.
- [ ] Renderer lỗi rơi về text gốc.
- [ ] Cùng input cho cùng token và HTML.
- [ ] Không import KaTeX, không gọi mạng.

## 8. Non-goals

- Không render công thức thật; placeholder là đủ.
- Không hỗ trợ `\(...\)`, `\[...\]`, `\begin{...}`.
- Không xử lý code fence; chạy pipeline trên text thuần.
- Không cần Markdown parser đầy đủ.
