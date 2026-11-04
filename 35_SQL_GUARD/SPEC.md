# SPEC 35 — Schema-qualified table lint

> **Cảnh báo phạm vi:** đây là lint phát hiện thiếu schema, **không phải** ranh giới bảo mật SQL. Nó không chống SQL injection, không thay parameterized query, quyền DB, row-level security, hay kiểm tra schema thực tế. Xem mục 10.

## 1. API

```python
PROTECTED_TABLES = frozenset({...})   # 10 bảng nguồn

def current_schema() -> str
def set_schema(name: str) -> ContextManager[None]
def fq_table(name: str) -> str
def validate_sql_schema(sql: str, *, enabled: bool = True) -> None
```

- `UnqualifiedTableError(Exception)` có thuộc tính `table`.
- `DEFAULT_SCHEMA = "public"`; có thể đổi qua `set_schema`.
- `enabled=False` → no-op (dùng cho migration/DDL đặc biệt, phải ghi log).

## 2. Tập bảng bảo vệ

`async_operations`, `banks`, `chunks`, `documents`, `entities`, `entity_cooccurrences`, `file_storage`, `memory_links`, `memory_units`, `unit_entities` — **sắp xếp Unicode** khi duyệt.

## 3. Mẫu

Với mỗi bảng `T` (upper):

| # | Regex | Ví dụ khớp |
|---|---|---|
| 1 | `FROM\s+T(?:\s|$\|,\|\)\|;)` | `FROM memory_units`, `FROM memory_units,` |
| 2 | `JOIN\s+T(?:\s\|$\|,\|\)\|;)` | `JOIN memory_units ON` |
| 3 | `INTO\s+T(?:\s\|$\|\()` | `INSERT INTO memory_units(...)` |
| 4 | `UPDATE\s+T(?:\s\|$)` | `UPDATE memory_units SET` |
| 5 | `DELETE\s+FROM\s+T(?:\s\|$\|;)` | `DELETE FROM memory_units` |

Thứ tự: bảng sorted, trong mỗi bảng mẫu 1→5; dừng ở lỗi đầu tiên.

Khi khớp tại `start`:

1. `pos = sql_upper.find(T, start)`.
2. `prefix = sql[:pos].rstrip()`.
3. Nếu `prefix.endswith(".")` → bỏ qua (coi như đã qualified).
4. Ngược lại ném:

```text
Unqualified table reference '<table>'. Use fq_table('<table>') for schema safety.
```

`<table>` là tên gốc chữ thường trong tập, không phải chuỗi upper.

## 4. Schema context

- `set_schema(name)` validate `^[A-Za-z_][A-Za-z0-9_$]{0,62}$`; sai → `ValueError`.
- Dùng `ContextVar`; trong `finally` gọi `reset(token)`.
- Lồng nhau: context trong trả về schema ngoài.
- `fq_table(name)`:
  - validate `name` cùng regex;
  - trả `f"{current_schema()}.{name}"`.
- Không kiểm tra `name` có thuộc `PROTECTED_TABLES` hay không.

## 5. CLI

```bash
python -m sql_guard --schema public --file fixtures/queries/unqualified.sql
python -m sql_guard --schema public --sql "SELECT * FROM memory_units"
python -m sql_guard --no-validate --sql "SELECT * FROM memory_units"
```

- `--sql` hoặc `--file`, không đồng thời.
- In `OK` và exit 0; in `ERROR: <message>` và exit 1; lỗi tham số exit 2.
- Không in toàn bộ SQL (có thể nhạy cảm).

## 6. Ví dụ cụ thể

| SQL | Kết quả | Ghi chú |
|---|---|---|
| `SELECT * FROM memory_units` | ERROR `memory_units` | khớp mẫu 1 |
| `SELECT * FROM MEMORY_UNITS` | ERROR | không phân biệt hoa thường |
| `SELECT * FROM\n\tmemory_units` | ERROR | `\s+` |
| `SELECT * FROM memory_units m` | ERROR | khoảng trắng sau bảng |
| `SELECT * FROM memory_units, banks` | ERROR `banks`? | bảng sorted: `banks` trước `memory_units`; mẫu `FROM banks` không khớp vì sau FROM là `memory_units`; `FROM memory_units,` khớp → lỗi `memory_units` |
| `SELECT * FROM memory_units_archive` | OK | `_` không thuộc lớp kết thúc |
| `SELECT * FROM public.memory_units` | OK | không khớp mẫu (xem giới hạn) |
| `SELECT * FROM "memory_units"` | OK | quoted identifier — **false negative** |
| `SELECT * FROM (memory_units)` | OK | ngoặc — **false negative** |
| `-- FROM memory_units` | ERROR | comment — **false positive** |
| `SELECT 'FROM memory_units'` | ERROR | chuỗi — **false positive** |
| `UPDATE memory_units SET x=1` | ERROR | mẫu 4 |
| `UPDATE public.memory_units SET x=1` | OK | qualified |
| `DELETE FROM memory_units WHERE id=1` | ERROR | mẫu 5 |
| `DELETE FROM public.memory_units` | OK | qualified |
| `INSERT INTO memory_units(id) VALUES (1)` | ERROR | mẫu 3 |
| `INSERT INTO public.memory_units(id) VALUES (1)` | OK | qualified |
| `WITH x AS (SELECT * FROM memory_units) SELECT * FROM x` | ERROR | inner |
| `SELECT * FROM memory_units; SELECT * FROM banks` | ERROR | dừng ở lỗi đầu |
| `SELECT 1` | OK | không có bảng bảo vệ |

## 7. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | SQL rỗng | OK |
| 2 | `enabled=False` | OK mọi câu |
| 3 | Schema `"my-schema"` | `ValueError` |
| 4 | Schema bắt đầu số | `ValueError` |
| 5 | Lồng `set_schema` | trả đúng sau khi thoát |
| 6 | Exception trong context | schema vẫn reset |
| 7 | `fq_table("x")` | `<schema>.x` |
| 8 | `fq_table("bad name")` | `ValueError` |
| 9 | Bảng bảo vệ viết hoa | phát hiện |
| 10 | `FROM\tmemory_units` | phát hiện |
| 11 | `FROM memory_units)` | phát hiện |
| 12 | `FROM memory_units;` | phát hiện |
| 13 | `FROM memory_units.` | OK — `.` không thuộc lớp kết thúc nên mẫu không khớp (giới hạn lint) |
| 14 | `FROM memory_units/*x*/` | không khớp (sau bảng là `/`) |
| 15 | Nhiều bảng thiếu schema | lỗi bảng sorted đầu tiên |
| 16 | Unicode `ſ` trong tên | không phát hiện (giới hạn upper) |

## 8. Tiêu chí chấp nhận

- [ ] 20 dòng bảng mục 6 khớp.
- [ ] Thứ tự lỗi tất định giữa các lần chạy.
- [ ] `set_schema` reset trong `finally`.
- [ ] `fq_table` và `set_schema` validate định danh.
- [ ] CLI exit code đúng.
- [ ] Có tài liệu nêu rõ false positive/negative.
- [ ] Không kết nối DB, không chạy SQL.

## 9. Non-goals

- Không parse SQL, không hiểu comment/chuỗi/CTE/quote.
- Không kiểm tra schema thực tồn tại.
- Không chống injection, không thay quyền DB/RLS.
- Không kiểm tra bảng không nằm trong danh sách bảo vệ.

## 10. Giới hạn an toàn — đọc kỹ

Lint này có thể bị qua mặt bởi:

- identifier trong ngoặc kép: `FROM "memory_units"`;
- comment chèn giữa: `FROM /*x*/ memory_units` (sau `FROM` là `/`, không khớp);
- ngoặc: `FROM (memory_units)`;
- schema viết tách: `FROM public . memory_units`;
- Unicode/case folding khác ASCII;
- bảng lấy từ biến/động.

Nó cũng báo nhầm khi từ khóa nằm trong comment hoặc chuỗi. Vì vậy:

1. Luôn dùng parameterized query cho giá trị.
2. Đặt quyền DB theo schema/bảng, bật RLS nếu có.
3. Dùng `fq_table()` khi sinh SQL nội bộ.
4. Coi lint là tín hiệu review, không phải cổng bảo mật duy nhất.
