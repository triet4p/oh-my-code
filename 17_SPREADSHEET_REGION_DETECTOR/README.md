# 17 — Spreadsheet region detector: suy layout từ viền ô

## Mục tiêu

Tự viết công cụ đọc file `.xlsx` và suy ra layout: vùng bảng chính, các hàng ngăn chunk, vùng metadata phía trên, bảng metadata nhỏ, và các cụm văn bản rời. Bài tập dạy cách dùng viền ô như tín hiệu cấu trúc, cách làm việc với tọa độ ô, BFS trên lưới, và cách sửa những thuật toán “gần đúng” thành hợp đồng kiểm thử được.

## Giá trị học được

- Viền ô (`Border`) là metadata có cấu trúc, nhưng `None`/`thin`/`medium` khác nhau và có thể không tồn tại.
- Quét xuôi để tìm góc trên-trái, quét ngược để tìm góc dưới-phải; thứ tự duyệt là một phần của đặc tả.
- Một hàng ngăn chunk chỉ hợp lệ nếu **mọi** ô trong khoảng cột đều có viền dưới cùng kiểu.
- Connected components 8 láng giềng trên lưới; hợp nhất theo hàng là một bước riêng, không phải BFS.
- Tọa độ `A1`, chuyển đổi hàng/cột, và giới hạn `max_row/max_column`.
- Ba lỗi thật trong nguồn: biến `range` che built-in, merge dùng nhầm `max_row` làm `max_col`, và bỏ mất cụm một ô.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Khó**.
- Thời lượng gợi ý: 6–8 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `openpyxl`, `pytest`.
- Không cần Excel/LibreOffice; test tạo workbook bằng openpyxl.

## Nguồn gốc

- Nguồn: `triet4p/excel2md`, file `src/excel_utils.py`.
- URL chính xác: <https://github.com/triet4p/excel2md/blob/main/src/excel_utils.py>

Hành vi quan sát được trong nguồn:

- `find_table_bounds(sheet, style='medium', top_styles=[], left_styles=[], bottom_styles=[], right_styles=[], range=None)`:
  - Nếu `style` khác `None`, ghi đè cả bốn danh sách style bằng `[style]`.
  - Dùng `range_boundaries(range)` nếu có, rồi gọi `sheet.iter_rows(**params)`.
  - Quét xuôi, dừng ở ô đầu tiên có `border.top.style in top_styles` **và** `border.left.style in left_styles`.
  - Quét ngược, dừng ở ô đầu tiên có `border.bottom.style in bottom_styles` **và** `border.right.style in right_styles`.
  - Trả `(top_left, bottom_right)` hoặc `None`.
- `find_chunk_split_rows(sheet, table_start_row, table_end_row, table_start_col, table_end_col, style='medium')`:
  - Khởi tạo `split_rows = [table_start_row]`.
  - Với `r_idx` từ `table_start_row` đến `table_end_row - 1`, kiểm tra **mọi** cột trong khoảng; nếu tất cả có `border.bottom.style == style`, thêm `r_idx + 1`.
- `is_metadata_text_cell` yêu cầu `cell.value is not None`, `border.bottom.style in {'medium', None}`, và top/left/right đều `None`.
- `find_text_regions_within_area`:
  - Thu các ô “active” trong vùng.
  - BFS 8 láng giềng (bỏ `dr=0,dc=0`).
  - Bỏ cụm một ô.
  - Chuyển cụm thành bounding box.
  - Sắp theo `(min_row, max_row, min_col, max_col)`.
  - Hợp nhất các cặp liên tiếp có cùng `min_row` và `max_row`.
- `find_layout_regions(filepath, metadata_col_padding=5)` mở workbook active sheet, tìm bảng, chunks, metadata area `A1:<end_col+padding><start_row-1>`, tìm metadata table với style `thin`/`thin|medium`, trả dict.

## Phạm vi bài tập

Xây package `sheet_layout`:

- `BorderStyles`, `Layout`.
- `find_table_bounds`, `find_chunk_split_rows`, `find_text_regions`, `analyze_workbook`.
- Lỗi có kiểu cho workbook không có viền, range sai, sheet rỗng.
- Test với workbook dựng bằng openpyxl.

Không nằm trong phạm vi: chuyển Excel sang Markdown, đọc công thức, merged cells phức tạp, nhiều sheet, màu sắc/font.

## Liên kết

- [SPEC.md](SPEC.md) — định nghĩa vùng, thuật toán, ví dụ với workbook cụ thể.
- [GUIDE.md](GUIDE.md) — openpyxl, BFS, merge, test fixture, các lỗi nguồn.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập giữ ý tưởng dùng viền và BFS, nhưng sửa ba lỗi đã nêu, định nghĩa lại metadata area, và yêu cầu lỗi rõ thay vì `Exception` chung. Đây là thiết kế của bài tập; không tuyên bố nguồn có hành vi đã sửa.
