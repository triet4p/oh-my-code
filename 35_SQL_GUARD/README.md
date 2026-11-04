# 35 — Lint kiểm tra tên bảng có schema

## Mục tiêu

Viết bộ kiểm tra tĩnh phát hiện các truy vấn tham chiếu bảng bảo vệ mà **không** có tiền tố schema, dùng đúng năm mẫu `FROM/JOIN/INTO/UPDATE/DELETE FROM`, hỗ trợ schema theo ngữ cảnh và hàm `fq_table()`.

## Giá trị

- Bài học thực tế: một regex tiện dụng có thể bắt lỗi thiếu schema, nhưng **không** phải hàng rào bảo mật.
- Học cách viết lint có ngữ cảnh schema (contextvar/thread-local) và thông điệp sửa lỗi hữu ích.
- Học giới hạn của biểu thức chính quy trên SQL: comment, chuỗi, dấu ngoặc kép, CTE đều có thể làm kết quả sai.
- Học phân biệt “phát hiện sớm lỗi vận hành” với “ngăn chặn tấn công”.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Regex, `contextvars`, hiểu SQL cơ bản |
| Thời lượng gợi ý | 3–5 giờ |

## Nguồn gốc

- Repo: `triet4p/cogmem`
- File nguồn: <https://github.com/triet4p/cogmem/blob/master/cogmem_api/engine/memory_engine.py>
- Hành vi quan sát được:
  - `_current_schema: contextvars.ContextVar[str | None]`.
  - `_PROTECTED_TABLES` gồm `memory_units`, `memory_links`, `unit_entities`, `entities`, `entity_cooccurrences`, `banks`, `documents`, `chunks`, `async_operations`, `file_storage`.
  - `fq_table(table_name)` trả `f"{get_current_schema()}.{table_name}"`.
  - `validate_sql_schema(sql)` upper toàn bộ SQL; với mỗi bảng, thử 5 mẫu:
    - `FROM\s+TABLE(?:\s|$|,|\)|;)`
    - `JOIN\s+TABLE(?:\s|$|,|\)|;)`
    - `INTO\s+TABLE(?:\s|$|\()`
    - `UPDATE\s+TABLE(?:\s|$)`
    - `DELETE\s+FROM\s+TABLE(?:\s|$|;)`
  - Khi khớp, lấy vị trí bảng, xét prefix đã `rstrip()`; nếu không kết thúc bằng `.` thì ném `UnqualifiedTableError("Unqualified table reference '…'. Use fq_table('…') for schema safety.")`.
  - `set_schema_context` đặt contextvar và `reset(token)` trong `finally`.
  - Có cờ `_VALIDATE_SQL_SCHEMAS = True`.

**Phần là thiết kế của bài:** sắp xếp bảng để lỗi tất định, validate định danh schema, API `enabled`, CLI, và bộ fixture nêu rõ false positive/false negative. Nguồn lặp trên `frozenset` nên thứ tự lỗi không ổn định; bài sắp xếp.

## Hành vi bài tập yêu cầu

- `validate_sql_schema(sql)` ném `UnqualifiedTableError` ở lần khớp đầu tiên theo thứ tự bảng đã sắp, rồi thứ tự mẫu cố định.
- So khớp không phân biệt hoa thường; giữ nguyên văn bản gốc khi báo lỗi.
- Chấp nhận câu có `schema.table` vì mẫu không khớp; đây là hành vi lint, **không** phải kiểm tra đúng schema.
- `fq_table(name)` dùng schema hiện tại; schema mặc định tiêm được.
- `set_schema(name)` là context manager, reset kể cả khi lỗi.
- Tên schema/table hợp lệ theo regex; tên bảng bảo vệ vẫn được kiểm tra.
- Không kết nối DB, không chạy SQL.

## Phạm vi

Trong phạm vi: phát hiện theo mẫu, ngữ cảnh schema, fq_table, CLI, test giới hạn.

Ngoài phạm vi: parse SQL, chống SQL injection, kiểm tra quyền, RLS, DB proxy, kiểm tra comment/chuỗi, CTE, quoted identifier.

## Fixture offline

- `fixtures/cases.json`: 20 câu SQL tổng hợp với kết quả mong đợi và ghi chú false positive/negative.
- `fixtures/queries/*.sql`.
- Không có dữ liệu thật, không credential, không kết nối.

## Liên kết

- [SPEC.md](SPEC.md) — thuật toán, bảng mẫu, ví dụ, giới hạn.
- [GUIDE.md](GUIDE.md) — thiết kế lint và cách trình bày giới hạn an toàn.
