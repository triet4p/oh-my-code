# GUIDE 35 — Thiết kế lint schema

## 1. Kiến trúc

```
sql_guard/
├─ tables.py     # PROTECTED_TABLES
├─ context.py    # schema contextvar, fq_table
├─ validate.py   # validate_sql_schema
├─ errors.py
└─ cli.py
fixtures/
```

`validate.py` chỉ nhận chuỗi; không import DB, không đọc file.

## 2. Tại sao dùng contextvar

Một request có thể chạy nhiều truy vấn với schema tenant khác nhau. `ContextVar` giữ schema theo task/async context, tránh truyền tham số qua mọi hàm. `set_schema` phải `reset(token)` trong `finally`; nếu không, task khác có thể thấy schema sai.

## 3. Thuật toán

```
sql_upper = sql.upper()
for table in sorted(PROTECTED_TABLES):
    t = table.upper()
    for pattern in patterns(t):
        for match in re.finditer(pattern, sql_upper):
            pos = sql_upper.find(t, match.start())
            prefix = sql[:pos].rstrip()
            if not prefix.endswith("."):
                raise UnqualifiedTableError(table)
            # nếu prefix kết thúc '.', tiếp tục match khác
```

Nguồn dùng `re.search` (chỉ lần đầu). Bài dùng `finditer` để nếu lần khớp đầu là qualified (hiếm) vẫn kiểm tra tiếp. Thực tế với mẫu này, prefix kết thúc `.` gần như không xảy ra; giữ để tương thích.

## 4. Vì sao không dùng SQL parser

Mục tiêu là tái hiện lint nhỏ, không phụ thuộc thư viện. Một parser thật sẽ xử lý comment/chuỗi/quote, nhưng bài muốn **phơi bày** giới hạn. Đừng “sửa” bằng regex phức tạp hơn mà không có test; nếu muốn, hãy viết tokenizer SQL ở phần mở rộng.

## 5. Bẫy thường gặp

- **`frozenset` iteration**: thứ tự lỗi đổi. Sort.
- **`sql[:pos]` với `pos` từ upper**: nếu `upper()` đổi độ dài (Unicode), index lệch. Ghi giới hạn; SQL identifier nên ASCII.
- **Quên `rstrip()`**: prefix kết thúc `. ` không được nhận.
- **Regex không escape tên bảng**: tên hiện tại toàn chữ thường/an toàn; nếu thêm bảng có ký tự đặc biệt, phải `re.escape`.
- **Không neo sau tên**: `memory_units_archive` bị bắt nhầm; các lớp kết thúc ngăn điều này.
- **Không xử lý dấu `)`**: `FROM memory_units)` là truy vấn con hợp lệ; phải khớp.
- **Chỉ kiểm tra `FROM`**: bỏ `UPDATE`, `DELETE`, `INSERT`.
- **Coi lint là bảo mật**: sai. Viết cảnh báo trong README/SPEC.
- **`enabled=False` toàn cục**: có thể che lỗi; chỉ dùng có chủ đích.
- **In toàn SQL khi lỗi**: có thể lộ dữ liệu; chỉ in tên bảng.

## 6. Kiểm chứng

```bash
cd 35_SQL_GUARD
python -m sql_guard --sql "SELECT * FROM memory_units"
python -m sql_guard --sql "SELECT * FROM public.memory_units"
python -m sql_guard --sql "SELECT * FROM \"memory_units\""
python -m sql_guard --sql "SELECT 'FROM memory_units'"
```

Test:

```bash
python -m unittest discover -s tests -v
```

Test context:

```python
with set_schema("tenant_a"):
    assert fq_table("memory_units") == "tenant_a.memory_units"
    with set_schema("tenant_b"):
        assert fq_table("memory_units") == "tenant_b.memory_units"
    assert fq_table("memory_units") == "tenant_a.memory_units"
assert current_schema() == "public"
```

Test reset khi exception:

```python
try:
    with set_schema("x"):
        raise RuntimeError
except RuntimeError:
    pass
assert current_schema() == "public"
```

## 7. Gỡ lỗi

- In bảng + mẫu đang thử khi debug; xóa log trước khi nộp.
- Với false positive, thêm ghi chú vào fixture, không sửa mẫu tùy tiện.
- Với false negative, thêm vào mục giới hạn; đừng tuyên bố đã chặn.
- Kiểm tra thứ tự lỗi bằng hai bảng cùng thiếu schema.

## 8. Gợi ý

- Viết `patterns(table)` trả list regex compile sẵn trong test.
- Dùng `re.IGNORECASE` thay vì upper toàn bộ? Nguồn upper; giữ upper để khớp.
- Tách `check_table(sql_upper, sql_raw, table)`.
- Không dùng `assert` trong thư viện; ném exception.

## 9. Mở rộng

1. Tokenizer SQL bỏ comment/chuỗi trước khi lint.
2. Hiểu quoted identifier và schema qualification.
3. Chỉ cho phép schema trong allowlist.
4. Tích hợp CI với `--fail-on-error`.
5. So sánh với `EXPLAIN`/quyền DB, nhưng vẫn không thay thế bảo mật.
