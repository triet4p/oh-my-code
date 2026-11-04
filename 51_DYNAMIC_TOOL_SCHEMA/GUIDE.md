# GUIDE 51 — Sinh lược đồ công cụ động từ registry

## 1. Một nguồn, bốn dẫn xuất

```text
registry (dữ liệu)
   ├── json_schema      → hợp đồng cho client/LLM
   ├── validate_args    → hợp đồng runtime
   ├── build_request    → biểu diễn HTTP
   └── parse_argv       → giao diện CLI
```

Cả bốn phải dẫn xuất từ **cùng** mô tả. Nếu bạn viết riêng cho CLI một danh sách cờ, nó sẽ trôi khỏi schema sau lần sửa đầu tiên.

## 2. Cấu trúc gợi ý

```text
src/
├── model.py      # ParamSpec, ToolSpec, ProviderSpec + parse/validate registry
├── schema.py     # json_schema(tool)
├── validate.py   # validate_args, coercion, lỗi
├── request.py    # build_request
├── argv.py       # parse_argv
└── __main__.py   # CLI
```

`ParamSpec` nên là `dataclass(frozen=True)`; `properties` là `dict[str, ParamSpec]` — đệ quy một cấp.

## 3. Thứ tự cài đặt

### Bước 1 — Nạp và kiểm tra registry

Viết `load_provider` với hai lớp kiểm tra:

1. **Bảo mật đường dẫn**: regex tên provider, ghép với thư mục fixture, và kiểm tra file kết quả vẫn nằm trong thư mục đó (`Path.resolve().is_relative_to(root)` — có từ Python 3.9). Đây là thay thế an toàn cho `importlib`.
2. **Tính nhất quán**: placeholder ↔ tham số path, một body, `default` hợp lệ.

Kiểm tra tính nhất quán **lúc nạp** vì lỗi registry là lỗi cấu hình, không phải lỗi người dùng. Nếu để đến lúc gọi, bạn sẽ báo lỗi "thiếu tham số" trong khi vấn đề là spec sai.

### Bước 2 — Sinh schema

Duyệt `params` theo thứ tự khai báo; dựng `properties` và `required`. Với `body`, tái dùng cùng hàm cho `properties` con.

Chú ý `title`: `"get_quote".title()` là `"Get_Quote"`, sau `.replace('_','')` thành `"GetQuote"`. Nếu bạn dùng `"".join(word.capitalize() ...)` cũng ra `"GetQuote"`, nhưng hãy bám đúng biểu thức của nguồn để dễ đối chiếu.

### Bước 3 — Xác thực

Viết một hàm `check_value(spec, value, path) -> value` đệ quy:

- `path` dùng để báo lỗi: `"payload.qty"`.
- Trả giá trị đã ép kiểu, hoặc ném lỗi.

Cẩn thận `bool` là subclass của `int` trong Python: `isinstance(True, int) == True`. Với `type == "integer"`, phải loại `bool` trước.

Ép chuỗi: `"10"` → `10`; `"1.5"` → `1.5`; `"true"` → `True`. Dùng `int(s)`/`float(s)` trong `try`, và từ chối `"1_000"` (Python chấp nhận dấu gạch dưới!). Nếu muốn chặt, kiểm tra bằng regex `^-?\d+$` trước.

### Bước 4 — Dựng request

Sau khi validate, bạn có một dict đã chuẩn hoá. Chia ba nhóm theo `in`:

```text
path_values  -> dùng cho endpoint.format
query_values -> dict, sắp khóa
body_value   -> json (hoặc None)
```

Kiểm tra sau khi format: kết quả không còn `{` hoặc `}`; nếu còn, bạn đã bỏ sót placeholder.

### Bước 5 — argv

Duyệt token theo cặp. Với boolean, nhìn token kế: nếu nó không bắt đầu bằng `--` và là `true`/`false`, tiêu thụ; ngược lại gán `True`.

Không dùng `argparse` trực tiếp vì schema là động; nhưng bạn có thể dựng `argparse.ArgumentParser` từ spec nếu muốn — hãy chọn một và ghi rõ.

## 4. Cạm bẫy

- **`importlib` với tên từ dữ liệu**: bỏ hẳn. Đây là điểm yếu của nguồn, không phải mẫu để học.
- **`endpoint.format(**path_values)` với giá trị chứa `{`**: `str.format` sẽ lỗi. Chặn ký tự trước khi format.
- **Không chặn `/` trong path**: `symbol = "../../admin"` tạo URL khác ý định. SPEC yêu cầu `UnsafePathValue`.
- **Query không sắp**: output phụ thuộc thứ tự dict; luôn sắp.
- **`default` không được kiểm tra**: một default sai kiểu chỉ lộ khi có người bỏ trống tham số — tức là hiếm khi test.
- **`bool` lọt vào `integer`**: kiểm tra `type(value) is bool` trước.
- **Tham số body lồng quá một cấp**: SPEC giới hạn một cấp; nếu bạn cho phép sâu hơn, phải test.
- **Báo lỗi không có đường dẫn**: `TypeMismatch("qty")` khó sửa hơn `TypeMismatch("payload.qty")`.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `schema_get_quote` | khớp mục 2.2 |
| `schema_place_order` | object lồng + `required` đúng thứ tự |
| `build_three` | ba ví dụ mục 4 |
| `missing_param` | `{}` cho `get_quote` ⇒ `MissingParam("symbol")` |
| `unknown_param` | `{"ticker": "AAPL"}` ⇒ `UnknownParam` |
| `enum` | `currency = "GBP"` ⇒ `EnumViolation` |
| `unsafe_path` | `"A/B"` ⇒ `UnsafePathValue` |
| `body_type` | `qty = "mười"` ⇒ đường dẫn `payload.qty` |
| `registry_errors` | mỗi lỗi mục 7 một fixture nhỏ |
| `argv_bool` | ba dạng boolean |
| `no_dynamic_import` | grep mã nguồn không có `importlib` |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src schema --provider finance --tool get_quote | python -m json.tool
python -m src request --provider finance --tool get_quote --args fixtures/args_ok.json
python -m src argv --provider finance --tool get_quote -- --symbol AAPL --currency EUR
```

So schema với mục 2.2 của SPEC. Kiểm tra bảo mật đường dẫn:

```bash
python -m src schema --provider ../finance --tool get_quote; echo "exit=$?"
```

Kỳ vọng `exit=2` và `InvalidProviderName`. Kiểm tra không có import động:

```bash
grep -R "importlib\|requests" src/ ; echo "exit=$?"
```

Kỳ vọng `exit=1` (không tìm thấy).

## 7. Gợi ý

- Viết `walk(spec, value, path)` một lần; validator, argv và request đều dùng.
- Giữ `required` là list theo thứ tự khai báo, đừng `sorted` — golden schema của bạn sẽ khớp SPEC.
- Viết `assert_registry_consistent(provider)` gọi ngay trong `load_provider`; test chỉ cần nạp fixture xấu.
- Nếu muốn "thấy" schema: in cả JSON Schema của body để kiểm tra đệ quy.

## 8. Mở rộng

- **`$ref`**: cho phép tham chiếu giữa các định nghĩa trong registry; cần phát hiện vòng.
- **Sinh client**: sinh hàm Python/TS từ schema; chạy golden snapshot.
- **Header/auth**: thêm `in: "header"` và một lớp `AuthSpec`; kiểm tra không rò secret vào log.
- **So sánh với pydantic**: cài lại bằng `create_model` trong một nhánh thử nghiệm, so hành vi xác thực với bản tay viết — thấy khác biệt về coercion.
- **Registry HTTP**: thêm transport có timeout/kích thước tối đa, nhưng giữ nguyên whitelist provider và không dùng `importlib`.
