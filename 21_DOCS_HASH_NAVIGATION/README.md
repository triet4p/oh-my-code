# 21 — Điều hướng tài liệu tĩnh bằng hash

## Mục tiêu

Tự viết một trình đọc tài liệu tĩnh một trang (SPA) không framework: registry tài liệu, tải Markdown theo yêu cầu, điều hướng bằng `location.hash`, nút trước/sau, trạng thái lỗi và deep link có thể chia sẻ. Không cần server API, không cần bundler.

## Giá trị

Bài này luyện bốn kỹ năng thường bị xem nhẹ trong ứng dụng tài liệu:

1. **Router dựa trên hash** không làm tải lại trang, vẫn giữ được lịch sử Back/Forward.
2. **Registry là nguồn sự thật duy nhất**: thứ tự, tiêu đề, nhóm và đường dẫn file đến từ một mảng khai báo, không rải rác trong HTML.
3. **Tải bất đồng bộ có trạng thái**: đang tải, thành công, lỗi HTTP, hash không tồn tại.
4. **An toàn nội dung**: nội dung Markdown từ file là dữ liệu, không được biến thành HTML/script tùy ý.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | JavaScript ES2022 chạy trình duyệt; Node.js chỉ dùng để chạy static server |
| Độ khó | Trung bình |
| Điều kiện | Node.js 18+ hoặc Python 3.11+ để phục vụ thư mục; trình duyệt hiện đại |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/claw-code-explain`
- File nguồn: <https://github.com/triet4p/claw-code-explain/blob/main/app.js>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `const PATTERNS = [ { id: 'pattern-01', file: 'pattern-01-persistent-instruction-file', title: '…', cat: 1, catName: 'Memory & Context' } … ]`
  - `history.replaceState(null, '', \`#${pattern.id}\`)` và `window.addEventListener('hashchange', loadFromHash)`
  - `function loadFromHash() { const hash = window.location.hash.replace('#', ''); … PATTERNS.find((p) => p.id === hash || p.file === hash || p.file.startsWith(hash)) … }`
  - `const url = \`${BASE}/docs/${pattern.file}.md\`; const res = await fetch(url); if (!res.ok) throw new Error(\`HTTP ${res.status}\`)`
  - `renderer.code = function (token) { … if (lang === 'mermaid') { … } … }` — biến fence thành vùng render Mermaid.
  - `renderDocNav(idx)` dựng nút `prev`/`next` từ vị trí trong `PATTERNS`.

Phần trên là **hành vi đọc được từ mã nguồn**. Bài tập không sao chép giao diện, không tải Mermaid từ CDN và không dùng thư viện Markdown bên thứ ba.

## Hành vi bài tập yêu cầu (thiết kế của bài)

- Registry `patterns.json` cố định 8 tài liệu, có `id`, `file`, `title`, `group`.
- Hash hợp lệ là `#<id>`; cũng chấp nhận `#<file>` để tương thích liên kết cũ.
- Hash không khớp → hiện màn hình chào, **không** phát sinh request.
- Tải thành công → render nội dung, cập nhật `document.title`, đánh dấu mục đang chọn, dựng prev/next.
- Tải lỗi → khối lỗi có mã HTTP và đường dẫn, không để nội dung cũ.
- Fence ```mermaid``` chỉ được biến thành `<pre class="diagram">` chứa text đã escape; không thực thi.
- Mọi HTML thô trong Markdown bị escape; chỉ các cấu trúc Markdown trong danh sách trắng được sinh HTML.

## Phạm vi

Trong phạm vi: router hash, registry, fetch, render Markdown tối giản, trạng thái, prev/next, test DOM bằng fixture.

Ngoài phạm vi: syntax highlighting, Mermaid thật, tìm kiếm toàn văn, SSR, build pipeline, đa ngôn ngữ, upload tài liệu.

## Fixture offline

Thư mục `fixtures/` chứa `patterns.json`, `docs/*.md` và ba file lỗi có chủ đích. Không có URL ngoài, không CDN, không analytics. Test dùng `fetch` được stub hoặc server tĩnh cục bộ; dữ liệu không chứa thông tin cá nhân.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng hành vi, lỗi, ví dụ và tiêu chí nghiệm thu.
- [GUIDE.md](GUIDE.md) — thiết kế từng bước, bẫy và cách tự kiểm chứng.
