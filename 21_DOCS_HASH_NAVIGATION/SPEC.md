# SPEC 21 — Trình đọc tài liệu bằng hash

## 1. Đầu vào

### 1.1. File registry `fixtures/patterns.json`

```json
{
  "version": 1,
  "patterns": [
    { "id": "pattern-01", "file": "pattern-01-persistent-instruction-file", "title": "Persistent Instruction File", "group": "Memory & Context" },
    { "id": "pattern-02", "file": "pattern-02-scoped-context-assembly", "title": "Scoped Context Assembly", "group": "Memory & Context" }
  ]
}
```

Quy tắc:

- `id` duy nhất, khớp `^[a-z0-9][a-z0-9-]{2,63}$`.
- `file` duy nhất, không chứa `/`, `\`, `..`, không bắt đầu bằng `.`.
- `title` 1–80 ký tự; `group` 1–40 ký tự.
- Thứ tự mảng là thứ tự hiển thị và thứ tự prev/next.
- `version` phải bằng `1`; giá trị khác là lỗi cấu hình.

### 1.2. Tài liệu

Mỗi mục tương ứng `fixtures/docs/<file>.md`, UTF-8, tối đa 200 KiB.

### 1.3. Hash

- `#pattern-01` hoặc `#pattern-01-persistent-instruction-file`.
- Hash rỗng, `#`, hoặc không khớp mục nào → màn hình chào.
- So khớp `file` theo tiền tố chỉ khi tiền tố khớp **duy nhất một** mục; nếu mơ hồ → màn hình chào và ghi cảnh báo.

## 2. Đầu ra

### 2.1. Trạng thái DOM

| Vùng | Khi có tài liệu | Khi lỗi | Khi hash rỗng/không khớp |
|---|---|---|---|
| `#welcome` | ẩn | ẩn | hiện |
| `#doc-view` | hiện | hiện | ẩn |
| `#doc-header` | nhóm + `Pattern NN` | nhóm + `Pattern NN` | rỗng |
| `#doc-body` | HTML đã render | khối lỗi | rỗng |
| `#doc-nav` | prev/next nếu có | prev/next | rỗng |
| `#sidebar a[aria-current="page"]` | đúng một mục | đúng một mục | không mục nào |
| `document.title` | `<title> — Docs` | `Lỗi tải tài liệu — Docs` | `Docs` |

### 2.2. Khối lỗi

```html
<div class="load-error" role="alert">
  Không tải được tài liệu.
  <code>docs/pattern-03-tiered-memory.md</code>
  <span class="status">HTTP 404</span>
</div>
```

Không được giữ nội dung của tài liệu trước trong `#doc-body`.

## 3. Quy tắc xử lý

1. Khi khởi động: đọc registry; nếu registry sai, hiện lỗi cấu hình và dừng router.
2. Chuẩn hóa hash: bỏ `#`, `decodeURIComponent` một lần; nếu decode ném lỗi → coi như hash không hợp lệ.
3. Nếu hash rỗng hoặc không khớp: hiện welcome, xóa header/body/nav, đặt title mặc định, kết thúc.
4. Nếu khớp: đặt trạng thái tải, xóa nội dung cũ, cập nhật nav và title.
5. `fetch` với `cache: "no-store"`; kiểm tra `res.ok`.
6. Thành công: đọc text, render, gắn prev/next, cuộn vùng nội dung về đầu.
7. Lỗi: hiện khối lỗi; giữ prev/next theo vị trí tài liệu đích.
8. Chuyển trang bằng điều hướng hash **không** gọi `history.pushState`; để trình duyệt tự ghi lịch sử. Chỉ dùng `history.replaceState` khi chuẩn hóa hash lúc khởi động.
9. Click nav dùng `<a href="#pattern-02">`; không `preventDefault` để Back/Forward hoạt động.
10. `hashchange` gọi cùng một hàm xử lý; không tải lại registry.

## 4. Render Markdown tối giản

Chỉ hỗ trợ:

- Tiêu đề ATX `#`…`######`.
- Đoạn văn, xuống dòng đơn thành khoảng trắng.
- Danh sách `-`/`1.` một cấp.
- Fence ba dấu backtick; fence có nhãn `mermaid` thành `<pre class="diagram">` + text escape.
- Inline code `` `x` ``, bold `**x**`, italic `*x*`.
- Link `[text](url)`: chỉ chấp nhận `https:`, `http:`, `mailto:` và đường dẫn tương đối không chứa `..`; sai → hiện text, bỏ link.

Mọi ký tự `<`, `>`, `&`, `"`, `'` trong text phải escape **trước** khi chèn thẻ. HTML thô trong Markdown không được thực thi.

## 5. Lỗi cấu hình và lỗi tải

| Mã | Điều kiện | Hành vi |
|---|---|---|
| `REGISTRY_FETCH` | không tải được `patterns.json` | màn hình lỗi cấu hình, không router |
| `REGISTRY_SCHEMA` | JSON sai/thiếu trường/trùng id hoặc file | màn hình lỗi cấu hình, nêu đường dẫn trường sai |
| `DOC_NOT_FOUND` | HTTP 404 | khối lỗi `HTTP 404` |
| `DOC_HTTP` | HTTP khác 2xx | khối lỗi `HTTP <status>` |
| `DOC_NETWORK` | fetch reject | khối lỗi `NETWORK` |
| `HASH_AMBIGUOUS` | tiền tố khớp nhiều mục | welcome + cảnh báo `console.warn` |
| `HASH_ENCODING` | `decodeURIComponent` ném lỗi | welcome |

Không hiển thị stack trace cho người dùng.

## 6. Tính xác định

- Cùng registry + hash + nội dung file → cùng DOM và title.
- Không dùng thời gian, `Math.random`, hay thứ tự thuộc tính object để quyết định hiển thị.
- Test phải stub `fetch` để không phụ thuộc mạng; fixture lỗi dùng đường dẫn tài liệu không tồn tại.

## 7. Trường hợp biên

| # | Tình huống | Kết quả bắt buộc |
|---|---|---|
| 1 | `#` | welcome |
| 2 | `#pattern-99` | welcome, không fetch |
| 3 | `#pattern-0` khớp nhiều file | welcome + cảnh báo |
| 4 | Hash có `%20` | decode một lần rồi so khớp |
| 5 | `#pattern-01#x` | không khớp → welcome |
| 6 | Tài liệu rỗng | render khung rỗng, vẫn COMPLETE, không lỗi |
| 7 | Tài liệu chỉ có fence mermaid | một `<pre class="diagram">`, không script |
| 8 | Markdown chứa `<img src=x onerror=…>` | text bị escape, không có phần tử `img` |
| 9 | Link `javascript:alert(1)` | chỉ còn text |
| 10 | Chuyển A → B → Back | hiển thị A, không tải lại registry |
| 11 | Fetch B lỗi, bấm Back về A | A tải lại và hiển thị đúng |
| 12 | Registry trùng `file` | lỗi cấu hình, không render mục nào |
| 13 | `file` chứa `../` | lỗi cấu hình |
| 14 | Tiêu đề có `<b>` | escape, hiện literal |

## 8. Ví dụ cụ thể

Registry có 3 mục; `#pattern-02`:

- Request: `GET docs/pattern-02-scoped-context-assembly.md` → 200.
- Header: `Memory & Context › Pattern 02`.
- Title: `Scoped Context Assembly — Docs`.
- Nav: prev `Pattern 01 — Persistent Instruction File`; next `Pattern 03 — Tiered Memory`.
- Sidebar: đúng `pattern-02` có `aria-current="page"`.

`#pattern-03` khi file trả 404:

- `#doc-body` chứa `HTTP 404` và đường dẫn `docs/pattern-03-tiered-memory.md`.
- `#doc-header` vẫn `Memory & Context › Pattern 03`.
- `document.title` = `Lỗi tải tài liệu — Docs`.

## 9. Tiêu chí chấp nhận quan sát được

- [ ] Mở `index.html` qua HTTP, deep link `#pattern-04` hiển thị đúng tài liệu ngay lần tải đầu.
- [ ] Back/Forward đổi tài liệu mà không reload trang (kiểm tra bằng counter trong `sessionStorage` hoặc log).
- [ ] Hash không tồn tại không tạo request nào (kiểm tra Network panel hoặc stub).
- [ ] Fetch lỗi hiển thị đúng một khối `role="alert"` và không còn nội dung cũ.
- [ ] Không có `<script>` hay handler `onerror` nào từ Markdown được thực thi.
- [ ] Registry sai tạo lỗi cấu hình rõ ràng, không màn hình trắng.
- [ ] Prev/next đúng thứ tự, mục đầu không có prev, mục cuối không có next.
- [ ] Cùng fixture cho cùng DOM (bỏ qua thuộc tính động không đáng kể).

## 10. Non-goals

- Không cần Mermaid, highlight cú pháp, hay Markdown đầy đủ theo CommonMark.
- Không cần routing phía server, SEO, hay prerender.
- Không cần tìm kiếm, mục lục cuộn, hay đồng bộ đa tab.
- Không được thêm analytics hoặc gọi mạng ngoài thư mục `fixtures/`.
