# SPEC — Spreadsheet region detector

## Mục tiêu hành vi

Từ một workbook `.xlsx`, trả về layout gồm:

- Bảng chính (một vùng chữ nhật).
- Các hàng ngăn và các chunk bên trong bảng.
- Vùng metadata phía trên bảng (nếu có).
- Bảng metadata nhỏ trong vùng đó (nếu có).
- Các cụm ô văn bản trong vùng metadata.

Mọi kết quả là tọa độ A1 dạng chuỗi, tất định, và có thể kiểm tra bằng mắt trên file.

## Kiểu

```python
@dataclass(frozen=True, slots=True)
class BorderStyles:
    top: frozenset[str]
    left: frozenset[str]
    bottom: frozenset[str]
    right: frozenset[str]

@dataclass(frozen=True, slots=True)
class Layout:
    main_table: str                 # "A6:Q59"
    split_rows: tuple[int, ...]     # (6, 21, 41)
    chunks: tuple[str, ...]         # ("A6:Q20", "A21:Q40", "A41:Q59")
    metadata_area: str | None       # "A1:Q5"
    metadata_table: str | None      # "E1:G3"
    text_regions: tuple[str, ...]   # ("A1:B1", "J2:L3")

class LayoutError(Exception): ...
class NoTableError(LayoutError): ...
class InvalidRangeError(LayoutError): ...
```

## API

```python
DEFAULT_TABLE_STYLES = BorderStyles(
    top=frozenset({"medium"}),
    left=frozenset({"medium"}),
    bottom=frozenset({"medium"}),
    right=frozenset({"medium"}),
)

def find_table_bounds(
    sheet, styles: BorderStyles, *, within: str | None = None
) -> tuple[str, str] | None: ...

def find_chunk_split_rows(
    sheet, top_left: str, bottom_right: str, *, style: str = "medium"
) -> tuple[int, ...]: ...

def find_text_regions(sheet, area: str) -> tuple[str, ...]: ...

def analyze_workbook(
    path: str | Path,
    *,
    metadata_col_padding: int = 5,
    styles: BorderStyles = DEFAULT_TABLE_STYLES,
) -> Layout: ...
```

## Tìm bảng chính

`find_table_bounds`:

1. Nếu `within` khác `None`, parse `range_boundaries(within)`; lỗi → `InvalidRangeError`.
2. Duyệt ô theo thứ tự hàng tăng, trong hàng cột tăng, giới hạn bởi `within`.
3. Ô đầu tiên thỏa **cả**:

    - `cell.border.top.style in styles.top`
    - `cell.border.left.style in styles.left`

    là góc trên-trái.
4. Duyệt ngược (hàng giảm, cột giảm), ô đầu tiên thỏa:

    - `cell.border.bottom.style in styles.bottom`
    - `cell.border.right.style in styles.right`

    là góc dưới-phải.
5. Nếu không có một trong hai → `None`.
6. Nếu tọa độ dưới-phải nằm trước trên-trái theo `(row, col)` → `InvalidRangeError`.
7. Trả `(top_left, bottom_right)` dạng `"A6"`, `"Q59"`.

Ghi chú:

- `border.top.style` có thể là `None`; so sánh với frozenset không khớp.
- Không dùng `cell.border.top` trực tiếp làm boolean; đối tượng `Border` luôn tồn tại.
- `within` là vùng giới hạn tìm kiếm, không phải vùng trả về.

## Hàng ngăn và chunk

`find_chunk_split_rows(sheet, top_left, bottom_right, style="medium")`:

1. Parse bốn tọa độ.
2. `split_rows = [start_row]`.
3. Với `r` từ `start_row` đến `end_row - 1`:
   - Duyệt **mọi** cột `c` từ `start_col` đến `end_col`.
   - Nếu tồn tại ô có `border.bottom.style != style` → không phải hàng ngăn.
   - Nếu tất cả khớp → thêm `r + 1`.
4. Trả tuple.

Chunk:

```text
boundaries = split_rows + (end_row + 1,)
chunks[i] = f"{col(start_col)}{boundaries[i]}:{col(end_col)}{boundaries[i+1]-1}"
```

- Luôn có ít nhất một chunk.
- Hàng ngăn ở `end_row` không được tính (vòng lặp dừng trước `end_row`).
- Hàng ngăn không được tạo chunk rỗng: nếu hai hàng ngăn liên tiếp, chunk giữa có thể rỗng? Ví dụ split rows 5, 6 với end 10 → chunk 5:5 không rỗng; nếu split rows 5,5 không thể vì tăng dần. Không có chunk rỗng vì `r+1 > r`.
- Nếu `start_row == end_row`, `split_rows = (start_row,)`, một chunk một hàng.

## Vùng metadata

`metadata_area`:

- Nếu `start_row == 1`: `None`.
- Ngược lại: `A1:<min(end_col + padding, sheet.max_column)><start_row - 1>`.
- `padding >= 0`; âm → `ValueError`.
- Không mở rộng sang cột ngoài `sheet.max_column`.
- Dùng chữ cột của `end_col + padding` (không phải `end_col` của bảng).

`metadata_table`:

- Nếu `metadata_area is None` → `None`.
- Gọi `find_table_bounds` trong `metadata_area` với styles:
  - top = `{"thin"}`
  - left = `{"thin"}`
  - bottom = `{"thin", "medium"}`
  - right = `{"thin", "medium"}`
- Nếu `None` → `None`.
- Nếu tìm thấy, trả `"E1:G3"`.
- Không yêu cầu bảng metadata phải nằm trọn trong area? `within` đã giới hạn.

## Cụm văn bản

`find_text_regions(sheet, area)`:

1. Parse area; lỗi → `InvalidRangeError`.
2. Ô “active” khi:
   - `cell.value is not None`
   - `cell.border.bottom.style in {"medium", None}`
   - `cell.border.top.style is None`
   - `cell.border.left.style is None`
   - `cell.border.right.style is None`
3. BFS 8 láng giềng; không vượt area; chỉ đi qua active.
4. Mỗi component → bounding box.
5. **Giữ cả component một ô** (khác nguồn).
6. Sắp component theo `(min_row, min_col, max_row, max_col)`.
7. Hợp nhất: gom các component liên tiếp có **cùng** `(min_row, max_row)`; hợp nhất min_col nhỏ nhất và max_col lớn nhất. Làm cho đến hết nhóm.
8. Định dạng:
   - Một ô: `"A1"`.
   - Cùng hàng: `"A1:C1"`.
   - Cùng cột: `"A1:A3"`.
   - Còn lại: `"A1:C3"`.
9. Trả tuple.

Tại sao hợp nhất theo hàng? Vì hai cụm văn bản trên cùng một dải hàng thường là hai cột của cùng một dòng metadata; gộp lại cho vùng đọc được. Không hợp nhất theo cột (khác hàng) để tránh nuốt hai khối.

## `analyze_workbook`

1. Mở workbook (`load_workbook(path)`), lấy `wb.active`.
2. Nếu sheet `max_row == 1` và `max_column == 1` và ô A1 rỗng → `NoTableError`.
3. Tìm bảng; `None` → `NoTableError("cannot determine main table bounds")`.
4. Tính split/chunks.
5. Tính metadata area/table.
6. Nếu metadata area có, tính text regions; ngược lại `()`.
7. Trả `Layout`.

Không đóng workbook? Dùng `try/finally wb.close()`.

## Fixture chuẩn

Xây workbook bằng openpyxl:

- Bảng chính `A6:Q59`.
  - A6: top + left `medium`.
  - Q59: bottom + right `medium`.
  - Hàng 20 và 40: mọi ô A..Q có bottom `medium`.
- Metadata area `A1:Q5`.
  - Bảng metadata `E1:G3`: E1 top+left `thin`; G3 bottom+right `thin`.
  - Cụm text `A1:B1`: A1, B1 có value, không viền.
  - Cụm text `J2:L3`: sáu ô có value, không viền.
  - Không đặt text ở các ô khác trong A1:Q5.
- Ô trong bảng chính có thể có value; không ảnh hưởng.

Kết quả mong đợi:

```python
Layout(
    main_table="A6:Q59",
    split_rows=(6, 21, 41),
    chunks=("A6:Q20", "A21:Q40", "A41:Q59"),
    metadata_area="A1:Q5",
    metadata_table="E1:G3",
    text_regions=("A1:B1", "J2:L3"),
)
```

(`metadata_col_padding=5`, cột Q là 17; `17 + 5 = 22` nhưng `max_column` là 17 → Q.)

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Không có viền medium | `NoTableError` |
| Bảng bắt đầu A1 | `metadata_area is None`, `metadata_table is None`, text regions rỗng |
| Bảng một hàng | một chunk đúng hàng đó |
| Bảng một cột | chunk `"A6:A20"` |
| Split row ngay trước end | chunk cuối một hàng |
| Split row ở end | không tính; không tạo chunk rỗng |
| Ô active đơn lẻ | giữ `"A2"` (khác nguồn) |
| Hai cụm cùng dải hàng | hợp nhất |
| Ba cụm cùng dải hàng | hợp nhất cả ba (nguồn chỉ ghép cặp) |
| Cụm cùng cột khác hàng | không hợp nhất |
| `within` ngược | `InvalidRangeError` |
| `padding < 0` | `ValueError` |
| Sheet trống | `NoTableError` |
| Merged cell | không đảm bảo; coi như non-goal |
| Border object với `style=None` | không active/không khớp |

## Tiêu chí nghiệm thu

1. Fixture chuẩn cho đúng `Layout` từng trường.
2. `find_table_bounds` với `within` chỉ tìm trong vùng.
3. Test split rows với 0, 1, 2 hàng ngăn.
4. Test text regions: một ô, hợp nhất 2, hợp nhất 3, không hợp nhất khác hàng.
5. Test `NoTableError`, `InvalidRangeError`, padding âm.
6. `analyze_workbook` đóng file (có thể chạy trên Windows không khóa file).
7. `pytest -q` xanh.

## Non-goals

- Chuyển sang Markdown.
- Đọc style theme, màu, font.
- Merged cells, hidden rows/columns.
- Nhiều sheet hoặc chọn sheet.
- Bảng không có viền nhưng có header đậm.
