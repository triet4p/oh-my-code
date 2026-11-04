# 31 — Phân tích công thức trong nội dung

## Mục tiêu

Viết pipeline nhận diện công thức trong văn bản Markdown: ưu tiên block `$$...$$`, bảo vệ giá trị tiền `$5.00`, chỉ nhận inline `$...$` khi biên hợp lệ, bỏ qua cụm có dấu tiếng Việt, và xuất HTML an toàn với phần công thức do renderer tiêm vào.

## Giá trị

- `$` vừa là ký hiệu toán vừa là ký hiệu tiền tệ; thứ tự xử lý quyết định kết quả.
- Học tokenizer có ưu tiên rõ ràng thay vì chuỗi regex chồng chéo.
- Học tách “nhận diện” khỏi “render”, nhờ đó test không cần KaTeX và không gọi mạng.
- Học escape HTML đúng chỗ: văn bản là dữ liệu, công thức do renderer chịu trách nhiệm.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | TypeScript 5, Node.js 20+ |
| Độ khó | Trung bình |
| Điều kiện | TypeScript/ESM, `node --test`; không cần KaTeX |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/daily-research`
- File nguồn: <https://github.com/triet4p/daily-research/blob/main/src/lib/content.ts>
- Hành vi quan sát được:
  - `renderLatex` chạy **display math trước**: `text.replace(/\$\$([\s\S]+?)\$\$/g, … katex.renderToString(math.trim(), { displayMode: true, throwOnError: false, strict: "ignore" }) …)`; lỗi thì trả lại `$$${math}$$`.
  - Sau đó bảo vệ tiền tệ: `res.replace(/\$(\d+(?:[.,]\d+)?)(?!\s*\\times|\s*\\pm|\s*\\ge|\s*\\le)/g, "&dollar;$1")`.
  - Cuối cùng inline: `/(^|[^\w\$])\$([^\$\n]+?)\$(?!\w)/g`; nếu nội dung khớp regex dấu tiếng Việt thì giữ nguyên; ngược lại `katex.renderToString(trimmed, { displayMode: false, throwOnError: true, strict: "ignore" })`, lỗi thì giữ match.
  - Nội dung trong `$...$` được `trim()` trước khi render.
  - Regex tiếng Việt gồm `àáảãạ…đ` với cờ `i`.

**Phần là thiết kế của bài:** tokenizer + renderer tiêm, token JSON, quy tắc biên rõ hơn regex gốc, output an toàn, fixture. Không dùng KaTeX; renderer mặc định tạo placeholder có `data-tex`.

## Hành vi bài tập yêu cầu

- Tokenizer chạy một lượt trái sang phải với ưu tiên: display → currency → inline → text.
- `$$...$$` cho phép xuống dòng, nội dung trim khác rỗng.
- Currency chỉ khớp `$` + số có phần thập phân tùy chọn dùng `.` hoặc `,`; không bảo vệ nếu ngay sau (cho phép khoảng trắng) là `\times`, `\pm`, `\ge`, `\le`.
- Inline yêu cầu biên trước không phải word/`$`, nội dung không chứa `$`/xuống dòng, đóng `$` không theo sau bởi word.
- Inline chứa ký tự tiếng Việt có dấu → giữ nguyên chuỗi `$...$` như text.
- Renderer nhận `(tex, display)` và trả HTML; lỗi → token được hiển thị như text gốc.
- Text và currency được escape; `&dollar;` là entity duy nhất không bị escape lại.
- Cùng input + cùng renderer → cùng output.

## Phạm vi

Trong phạm vi: tokenizer, ưu tiên, render placeholder, escape, CLI, test.

Ngoài phạm vi: KaTeX thật, Markdown đầy đủ, công thức trong code fence, `\(...\)`/`\[...\]`, công thức nhiều dòng lồng nhau, syntax highlight.

## Fixture offline

- `fixtures/cases.json`: 30 chuỗi đầu vào và token/HTML mong đợi.
- `fixtures/strict-renderer.ts`: renderer ném lỗi với `\bad` để test fallback.
- Không tải KaTeX/CSS từ CDN; không render đồ họa.

## Liên kết

- [SPEC.md](SPEC.md) — thuật toán token, bảng ưu tiên, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế tokenizer và kiểm chứng.
