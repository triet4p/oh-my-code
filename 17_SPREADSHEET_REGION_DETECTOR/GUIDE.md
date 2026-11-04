# GUIDE — Spreadsheet region detector

## Bước 0 — Môi trường

```bash
mkdir 17_SPREADSHEET_REGION_DETECTOR/work && cd 17_SPREADSHEET_REGION_DETECTOR/work
uv init . -p 3.12 --lib
uv add openpyxl
uv add --dev pytest
mkdir -p src/sheet_layout tests
```

## Bước 1 — Làm quen openpyxl

Viết một script nhỏ (hoặc REPL) để kiểm tra:

- `ws["A6"].border.top.style`
- `ws["A6"].border.left.style`
- `ws.max_row`, `ws.max_column`
- `ws.iter_rows(min_row=..., max_row=..., min_col=..., max_col=...)`
- `openpyxl.utils.cell.coordinate_to_tuple("Q59")` → `(59, 17)`
- `get_column_letter(17)` → `"Q"`

Các điểm cần nhớ:

- `cell.border` luôn là `Border`; `border.top` luôn là `Side`; `.style` có thể `None`.
- Gán `Border(top=Side(style="medium"), left=Side(style="medium"))` sẽ **thay** toàn bộ border của ô; muốn giữ cạnh khác thì gộp.
- `ws.max_column` có thể lớn hơn vùng có dữ liệu nếu ai đó format cột.
- Workbook đang mở có thể khóa file trên Windows; gọi `wb.close()`.

## Bước 2 — Parse range, đừng đặt tên `range`

Nguồn dùng tham số tên `range`, che built-in. Bài tập đặt `within`.

```text
from openpyxl.utils.cell import range_boundaries
try:
    min_col, min_row, max_col, max_row = range_boundaries(within)
except (TypeError, ValueError) as exc:
    raise InvalidRangeError(within) from exc
```

`range_boundaries` trả `(min_col, min_row, max_col, max_row)` — **cột trước hàng**. Đây là nguồn lỗi số một.

## Bước 3 — Quét góc

Viết helper `_iter_cells(sheet, bounds)` và `_iter_cells_reversed` để không lặp code.

Góc trên-trái:

```text
for row in sheet.iter_rows(min_row=..., max_row=..., min_col=..., max_col=...):
    for cell in row:
        if cell.border.top.style in styles.top and cell.border.left.style in styles.left:
            return cell.coordinate
```

Góc dưới-phải: duyệt ngược. Bạn có thể lấy `list(sheet.iter_rows(...))` rồi `reversed`, nhưng với sheet lớn sẽ tốn bộ nhớ. Bài tập chấp nhận; nếu muốn tối ưu, duyệt hàng ngược bằng `range(max_row, min_row-1, -1)` và cột ngược.

Một cái bẫy: góc trên-trái có thể nằm **sau** góc dưới-phải nếu workbook có nhiều bảng. Bài tập yêu cầu `InvalidRangeError` thay vì trả vùng âm.

## Bước 4 — Split rows

Với mỗi hàng, kiểm tra mọi cột. Dùng `all(...)` nhưng nhớ `cell.border.bottom.style == style` chính xác, không `in`.

Tại sao phải kiểm tra **mọi** cột? Vì một đường kẻ chỉ ở vài cột là đường kẻ trang trí, không phải ngăn bảng. Nguồn làm đúng điều này.

Kiểm tra `end_row` không được tính: nếu hàng cuối có viền dưới medium (rất có thể), nó không phải separator.

## Bước 5 — BFS cụm

Tập active:

```text
def active(cell):
    return (cell.value is not None
            and cell.border.top.style is None
            and cell.border.left.style is None
            and cell.border.right.style is None
            and cell.border.bottom.style in (None, "medium"))
```

BFS:

- Dùng `collections.deque`.
- `visited` toàn cục để không lặp.
- 8 hướng; bỏ `(0,0)`.
- Kiểm tra biên area trước khi tạo tọa độ.
- Không dùng đệ quy (giới hạn đệ quy).

Component là tập tọa độ; tính min/max.

## Bước 6 — Hợp nhất

Sắp component theo `(min_row, min_col, max_row, max_col)`.

Duyệt và gom nhóm:

```text
groups = []
for comp in sorted_components:
    if groups and groups[-1].min_row == comp.min_row and groups[-1].max_row == comp.max_row:
        groups[-1] = union(groups[-1], comp)
    else:
        groups.append(comp)
```

`union` lấy min_col nhỏ nhất, max_col lớn nhất. Điều này xử lý cả 3+ cụm, khắc phục lỗi ghép cặp của nguồn.

## Bước 7 — Định dạng

```text
def format_range(r1, c1, r2, c2):
    if r1 == r2 and c1 == c2:
        return f"{col(c1)}{r1}"
    return f"{col(c1)}{r1}:{col(c2)}{r2}"
```

Với một hàng, `r1 == r2`; với một cột, `c1 == c2`. Không cần nhánh riêng; công thức chung cho `"A1:C1"` và `"A1:A3"`.

## Bước 8 — Fixture

Viết `tests/conftest.py` hàm `build_workbook(path)`:

- Tạo `Workbook()`, `ws = wb.active`.
- Gán giá trị A1, B1; J2..L3.
- Gán border:
  - A6: `Border(top=Side("medium"), left=Side("medium"))`.
  - Q59: `Border(bottom=Side("medium"), right=Side("medium"))`.
  - Mỗi ô A20:Q20 và A40:Q40: `Border(bottom=Side("medium"))` (ghi đè cạnh khác không quan trọng).
  - E1: top+left thin; G3: bottom+right thin.
- Lưu.

Cẩn thận: gán border cho A6 xong, nếu sau đó gán border khác cho A6 (ví dụ hàng separator) sẽ mất top/left. Không gán trùng.

Kiểm tra fixture bằng mắt: mở bằng LibreOffice/Excel nếu có; nếu không, in `ws["A6"].border`.

## Bước 9 — Test

1. `analyze_workbook` so khớp `Layout` toàn bộ.
2. `find_table_bounds` với `within="A1:Q10"` không thấy bảng (vì bảng bắt đầu A6 nhưng bottom-right ngoài range) — hoặc thấy top-left và bottom-right trong range? Với range A1:Q10, Q10 không có bottom/right medium → `None`. Kiểm tra.
3. `within="A5:Q60"` thấy.
4. `find_chunk_split_rows` với 0/1/2 separator.
5. Text: một ô, hai ô cùng hàng, ba cụm cùng hàng, khác hàng.
6. `padding=0` → metadata area `A1:Q5`.
7. `padding=-1` → `ValueError`.
8. Range sai → `InvalidRangeError`.
9. Workbook trống → `NoTableError`.

## Bước 10 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from sheet_layout import analyze_workbook
import json, dataclasses
layout = analyze_workbook("tests/fixtures/layout.xlsx")
print(json.dumps(dataclasses.asdict(layout), ensure_ascii=False, indent=2))
PY
```

Kỳ vọng đúng khối SPEC. Nếu `chunks` ra `A6:Q19`, bạn đã dùng hàng separator làm điểm kết thúc thay vì `r-1`, hoặc split row sai.

Kiểm tra đóng file trên Windows:

```bash
uv run python -c "from sheet_layout import analyze_workbook; analyze_workbook('tests/fixtures/layout.xlsx'); import os; os.remove('tests/fixtures/layout.xlsx')"
```

Nếu `PermissionError`, bạn chưa `wb.close()`.

## Bước 11 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Bảng không tìm thấy | Gán border sai cạnh; hoặc `Side(style=...)` thiếu. |
| `max_column` quá lớn | Format cột; metadata area bị kéo rộng. |
| Chunk lệch 1 hàng | Dùng `r` thay vì `r-1` khi kết thúc chunk. |
| Split row cuối bị tính | Vòng lặp chạy đến `end_row` thay vì `end_row-1`. |
| Text region nuốt bảng metadata | Ô có top/left thin vẫn được coi active; kiểm tra đủ bốn cạnh. |
| Cụm một ô mất | Bạn giữ logic `continue` của nguồn. |
| Hợp nhất sai | Dùng `max_row` của cụm sau làm `max_col`. |
| `range_boundaries` trả sai thứ tự | Nhớ `(min_col, min_row, max_col, max_row)`. |
| File bị khóa | Không `close()`. |
| BFS treo | Không đánh dấu visited trước khi đẩy queue. |

## Bước 12 — Mở rộng

- Hỗ trợ merged cells bằng cách đọc `ws.merged_cells.ranges` và map anchor.
- Chọn sheet theo tên.
- Xuất Markdown table từ chunk.
- Thêm phát hiện header row theo font đậm.
- Tối ưu quét ngược không tạo list toàn sheet.
- Thêm CLI in JSON.

## Tự đánh giá

1. Vì sao phải quét ngược cho góc dưới-phải?
2. Vì sao split row yêu cầu mọi cột?
3. Khác biệt giữa BFS và bước hợp nhất là gì?
4. Ba lỗi nào của nguồn được sửa, và mỗi lỗi gây ra triệu chứng gì?
