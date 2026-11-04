# 28 — Kiểm tra file sơ đồ draw.io

## Mục tiêu

Viết bộ kiểm tra tĩnh cho file `.drawio` được lưu trong source control: bắt buộc không nén, có trang và `mxGraphModel` sửa được, id ô duy nhất, hình học dương, cạnh trỏ đúng đỉnh, và cảnh báo các vấn đề hiển thị như icon không nhúng, icon quá lớn, cạnh không trực giao, nhãn bị icon che.

## Giá trị

- File sơ đồ là mã nguồn: lỗi cấu trúc làm hỏng render mà không ai thấy khi review.
- Học đọc XML có namespace (không) và thuộc tính style dạng `key=value;`.
- Học phân biệt **error** (chặn) và **warning** (cần xem lại), cùng chế độ `--strict`.
- Học đầu ra vừa cho người đọc vừa cho máy đọc (JSON + exit code).

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (`xml.etree.ElementTree`, `dataclasses`) |
| Độ khó | Trung bình |
| Điều kiện | Hiểu cấu trúc `mxfile`/`mxGraphModel` cơ bản |
| Thời lượng gợi ý | 5–6 giờ |

## Nguồn gốc

- Repo: `triet4p/coding-agent-stacks`
- File nguồn: <https://github.com/triet4p/coding-agent-stacks/blob/main/.agents/skills/drawio-architecture-diagram/scripts/validate_drawio.py>
- Hành vi quan sát được:
  - `@dataclass(frozen=True) class Issue: severity, page, cell_id, message`.
  - `Rect.intersects` trả `not (self.x+self.width <= other.x or …)`.
  - `parse_style` tách chuỗi theo `;`, `item.partition("=")`, giữ key không giá trị.
  - `geometry()` đọc `mxGeometry`, mặc định `x/y=0`, `width/height=0`, lỗi số → `None`.
  - `if mxfile.get("compressed", "true").lower() != "false"` → error `Source-controlled diagram must set compressed="false".`
  - Root phải là `mxfile`; phải có `<diagram>`; mỗi trang phải có `mxGraphModel` và `root`.
  - `mxCell` thiếu `id` → error; id trùng → error.
  - Vertex: cần hình học dương; `shape=image`: cần `image` khác rỗng, cảnh báo nếu không bắt đầu `data:image/`, cảnh báo nếu `>64` theo một chiều.
  - Edge: cần `mxGeometry`; `source`/`target` nếu có phải trỏ tới id tồn tại; cảnh báo nếu `edgeStyle != orthogonalEdgeStyle`.
  - Ảnh chồng lên ô có nhãn (không swimlane) → warning.
  - Stats `{pages, vertices, edges, images}`.
  - `--strict` biến warning thành exit 1; `--json` xuất JSON; exit 1 nếu có error.

**Phần là thiết kế của bài:** fixture cụ thể, mã lỗi ổn định, kiểm tra `mxCell` là phần tử trực tiếp của `root`, định nghĩa “text cell”, và các ví dụ số. Nguồn không kiểm tra `parent`; bài cũng không, để giữ phạm vi.

## Hành vi bài tập yêu cầu

- Chạy `validate(path)` không sửa file, không gọi mạng.
- Mọi lỗi cấu trúc được báo, không dừng ở lỗi đầu tiên (trừ khi không parse được file).
- Issue giữ thứ tự phát hiện; stats đếm toàn bộ trang.
- Exit 0 chỉ khi không có error và (không strict hoặc không warning).
- JSON output có `stats` và `issues`, trường issue theo thứ tự `severity,page,cell_id,message`.
- Không crash với file rỗng, XML hỏng, hay thuộc tính số không hợp lệ.

## Phạm vi

Trong phạm vi: parse, validate cấu trúc/hình học/liên kết, cảnh báo hiển thị, CLI, fixture.

Ngoài phạm vi: render ảnh, kiểm tra mỹ thuật, font, theme, mũi tên, layer, kiểm tra `parent`, chuyển đổi draw.io ↔ PNG.

## Fixture offline

`fixtures/` chứa:

- `valid.drawio` — 1 trang, 4 vertex, 1 edge, 1 icon nhúng.
- `compressed.drawio`, `duplicate-id.drawio`, `missing-geometry.drawio`, `dangling-edge.drawio`, `bad-edge-style.drawio`, `non-embedded-image.drawio`, `oversized-image.drawio`, `overlap.drawio`.
- `multipage.drawio`.
- `expected/*.json`.

Không có file thật từ repo nguồn; mọi ô đều tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — quy tắc kiểm tra, output, ví dụ valid.
- [GUIDE.md](GUIDE.md) — thiết kế validator và kiểm chứng.
