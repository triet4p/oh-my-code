# GUIDE 21 — Thiết kế và tự kiểm chứng

## 1. Kiến trúc gợi ý

```
21_DOCS_HASH_NAVIGATION/
├─ index.html          # khung DOM cố định
├─ app.js              # registry loader, router, renderer
├─ patterns.json       # (hoặc fixtures/patterns.json)
├─ docs/               # fixture Markdown
└─ fixtures/
   ├─ patterns.json
   └─ docs/
```

Tách ba module logic (có thể cùng file nhưng hàm riêng):

1. `loadRegistry()` — tải và validate.
2. `resolveHash(hash, patterns)` — thuần, trả `Match | None | Ambiguous`.
3. `showDocument(pattern, patterns, deps)` — tải và render.
4. `renderMarkdown(text)` — thuần, trả chuỗi HTML an toàn.

Router chỉ điều phối; không chứa logic render.

## 2. Cấu trúc dữ liệu

```js
// Kết quả phân giải hash
{ kind: "match", pattern, index }
{ kind: "welcome" }
{ kind: "ambiguous", candidates: [id…] }

// Trạng thái một lần tải
{ requestId, patternId, phase: "loading" | "ready" | "error", errorCode? }
```

Dùng `requestId` tăng dần để bỏ kết quả fetch cũ khi người dùng chuyển trang nhanh (race condition). Khi `hashchange` xảy ra, tăng `requestId`; chỉ áp dụng kết quả nếu `requestId` còn khớp.

## 3. Thuật toán từng bước

### 3.1. Khởi động

1. `fetch("fixtures/patterns.json")`.
2. Parse JSON trong `try/catch`.
3. Validate từng mục: kiểu, regex, unique, thứ tự.
4. Nếu lỗi: render khối cấu hình vào `#app-error`, gắn `aria-live="assertive"`, dừng.
5. Gắn listener `hashchange` **trước** lần xử lý đầu.
6. Gọi `handleRoute()`.

### 3.2. Phân giải hash

```
raw = location.hash.slice(1)
decoded = safeDecode(raw)            // lỗi -> welcome
if decoded == "": welcome
byId = registry.find(id == decoded)
if byId: match
byFile = registry.find(file == decoded)
if byFile: match
prefixes = registry.filter(file.startsWith(decoded))
if prefixes.length == 1: match
if prefixes.length > 1: ambiguous
welcome
```

Không dùng `startsWith` trước khi thử khớp chính xác: tránh `#pattern-0` trúng nhầm mục đầu.

### 3.3. Tải và render

1. Tăng `requestId`.
2. Ẩn welcome, hiện view, đặt header từ registry.
3. Đặt body thành trạng thái loading.
4. `fetch` với `AbortController` (tùy chọn) hoặc bỏ qua kết quả cũ bằng `requestId`.
5. Nếu `!res.ok`: ném lỗi có `status`.
6. Text → `renderMarkdown` → `innerHTML` **chỉ** với HTML do renderer sinh.
7. Cập nhật nav, title, `aria-current`.

### 3.4. Renderer an toàn

Thứ tự bắt buộc:

1. Chuẩn hóa CRLF → LF.
2. Tách theo dòng; xử lý fence trước (đếm ba backtick).
3. Với mỗi dòng ngoài fence: escape toàn bộ text trước.
4. Áp dụng inline bằng cách tách token, không chạy regex HTML sau khi đã chèn thẻ.
5. Link: parse URL bằng `new URL(raw, location.href)`; chỉ cho protocol trong danh sách trắng; thêm `rel="noopener noreferrer"`.

Gợi ý triển khai inline: một lần quét chuỗi, ưu tiên `` ` ``, rồi `**`, rồi `*`; tránh regex lồng nhau gây backtracking.

## 4. Bẫy thường gặp

- **Gọi `preventDefault` trên link nav**: Back/Forward vẫn đổi hash nhưng nếu bạn tự `pushState` sai, lịch sử bị nhân đôi.
- **`replaceState` mỗi lần tải**: làm mất khả năng Back.
- **So khớp tiền tố quá sớm**: `#pattern-0` có thể khớp nhiều mục; phải phát hiện mơ hồ.
- **Race khi chuyển nhanh**: response cũ về sau ghi đè tài liệu mới. Dùng `requestId`/`AbortController`.
- **`innerHTML` với Markdown thô**: XSS. Luôn escape trước.
- **Đọc `location.hash` chưa decode**: `%2F` và khoảng trắng gây lệch.
- **Fetch lỗi nhưng vẫn giữ header cũ**: phải cập nhật header theo tài liệu đích trước khi fetch.
- **`file.startsWith(hash)` với hash rỗng**: mọi file khớp; xử lý rỗng trước.

## 5. Kiểm tra gỡ lỗi

- Mở DevTools → Network, lọc `docs/`; đếm request khi đổi hash.
- Thêm log tạm `[route] hash=… requestId=…`; xóa trước khi nộp.
- Kiểm tra `document.querySelectorAll('[aria-current="page"]').length`.
- Thử hash lạ, hash mơ hồ, file 404, file rỗng.
- Dán Markdown chứa `<img src=x onerror="alert(1)">`; xác nhận không có `img` trong DOM.
- Dùng Back/Forward liên tục 5 lần; không có request registry lặp lại.

## 6. Kiểm chứng độc lập

Từ thư mục bài:

```bash
# Cách 1: Python
python -m http.server 8080

# Cách 2: Node
npx --yes http-server . -p 8080 -c-1
```

Mở `http://127.0.0.1:8080/#pattern-02`.

Kiểm tra tự động tối thiểu (không bắt buộc framework):

```bash
node --test
```

Gợi ý test thuần cho `renderMarkdown` và `resolveHash` (không cần DOM), cùng một test DOM bằng `jsdom` nếu muốn. Test fetch nên stub:

- 200 + nội dung;
- 404;
- reject;
- hai request cũ/mới về sai thứ tự.

Lệnh kiểm tra không được gọi mạng ngoài; fixture nằm trong repo.

## 7. Gợi ý (không phải lời giải)

- Viết `resolveHash` là hàm thuần trước; nó dễ test nhất và là nguồn của nhiều bug.
- Tách `renderInline` và `renderBlocks`; đừng cố viết một regex Markdown duy nhất.
- Với fence, xử lý theo máy trạng thái: `outside` / `inside(lang)`.
- Nếu phân vân về bảo mật, chọn escape nhiều hơn: mất vài thẻ hợp lệ còn hơn thực thi script.
- Dùng `textContent` cho tiêu đề/nhãn; chỉ dùng `innerHTML` cho chuỗi đã qua renderer.

## 8. Mở rộng tiếp theo

1. Thêm mục lục từ heading và cuộn đến anchor, vẫn giữ hash tài liệu.
2. Thêm tìm kiếm client trên registry (không cần index).
3. Thêm chế độ in và `prefers-reduced-motion`.
4. Thay hash router bằng History API, so sánh đánh đổi khi mở file trực tiếp.
5. Thêm kiểm tra link chết trong CI bằng script đọc registry và kiểm tra file tồn tại.
