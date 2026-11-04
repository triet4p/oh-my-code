# GUIDE — Plugin registry

## Bước 0 — Môi trường

```bash
mkdir 03_PLUGIN_REGISTRY/work && cd 03_PLUGIN_REGISTRY/work
uv init . -p 3.12 --lib
uv add --dev pytest
mkdir -p src/forensic_registry tests
```

## Bước 1 — Hiểu decorator trước khi viết registry

Decorator có hai dạng bạn sẽ gặp:

```python
@decorator
class X: ...

# tương đương
X = decorator(X)
```

Nhưng API của bài này là **decorator factory**: gọi `register_symptom("burst", Schema)` trước, nhận về một hàm, rồi hàm đó nhận lớp. Nghĩa là:

```python
register = ForensicRegistry.register_symptom("burst", Schema)
X = register(X)
```

Hãy viết một decorator tối giản ngoài registry để chắc mình hiểu thứ tự thực thi:

- Hàm ngoài chạy ngay khi module import.
- Hàm trong chạy khi lớp kế tiếp được định nghĩa.
- Giá trị trả về của hàm trong trở thành tên lớp trong namespace.

## Bước 2 — Chọn nơi lưu trạng thái

Nguồn dùng dict cấp lớp. Bài tập giữ cách đó vì nó phản ánh đúng bài học, nhưng phải chỉ ra hệ quả:

- Trạng thái tồn tại suốt tiến trình.
- Import lại cùng module không reset (Python cache module).
- Test này có thể làm bẩn test khác nếu không snapshot/restore.

Cấu trúc:

```text
ForensicRegistry
├── SYMPTOMS: name -> class
├── SYMPTOMS_CONFIGS: name -> config class
└── PATTERN_SCORERS: name -> class
```

Ba dict độc lập. Đừng gộp thành `name -> (class, schema)` nếu muốn bám sát nguồn; nhưng nếu gộp, bạn phải tự chứng minh tính nguyên tử dễ hơn. Bài tập chọn giữ ba dict để học cách giữ chúng đồng bộ.

## Bước 3 — Kiểm tra tên

Viết một hàm private `_validate_name(name) -> str`:

- Kiểm tra `isinstance(name, str)`.
- Dùng `re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name)`.
- Trả lại name hoặc ném `InvalidNameError`.

Đừng dùng `name.isidentifier()`: nó cho phép chữ hoa, Unicode và bắt đầu bằng `_`, không khớp hợp đồng.

Đừng strip. Nếu người dùng gõ `" burst"`, đó là lỗi của họ; âm thầm sửa sẽ làm tra cứu bằng tên gốc thất bại.

## Bước 4 — Đăng ký nguyên tử

Trật tự quan trọng. Viết theo hướng:

1. Validate name.
2. Validate schema.
3. Nếu tên đã có:
   - Cùng cặp `(class, schema)`? Trả decorator không làm gì (nhưng vẫn phải trả lại lớp).
   - Khác? Ném `DuplicatePluginError`.
4. Trả decorator.

Bên trong decorator:

1. Kiểm tra `symptom_cls` là lớp.
2. Lặp lại kiểm tra trùng — vì giữa lúc gọi factory và lúc decorator chạy, trạng thái có thể đã đổi (trong chương trình đơn luồng hiếm, nhưng vẫn đúng về mặt hợp đồng).
3. Ghi **cả hai** dict.
4. Trả `symptom_cls`.

Câu hỏi thiết kế: nếu bước 3 ghi `SYMPTOMS` rồi bước 4 ném lỗi vì `SYMPTOMS_CONFIGS` đã có tên? Trong thiết kế này hai dict luôn được ghi cùng nhau, nên chỉ cần kiểm tra trùng trên `SYMPTOMS` là đủ — nhưng phải đảm bảo không có đường nào ghi lệch. Viết một helper `_commit_symptom(name, cls, schema)` là nơi duy nhất chạm cả hai dict.

## Bước 5 — Tra cứu

`get_symptom`:

1. Validate name.
2. `try: cls = SYMPTOMS[name]; schema = SYMPTOMS_CONFIGS[name]`.
3. Nếu `KeyError` → `UnknownPluginError(name)`.
4. Trả tuple.

Đừng trả `None`. `None` buộc mọi caller kiểm tra null và dễ bị bỏ qua; exception có ngữ nghĩa “lập trình viên quên đăng ký”.

`get_pattern_scorer` tương tự.

## Bước 6 — Snapshot và restore

`snapshot()`:

```text
{
  "symptoms": dict(SYMPTOMS),
  "configs": dict(SYMPTOMS_CONFIGS),
  "scorers": dict(PATTERN_SCORERS),
}
```

`restore(state)`:

- Kiểm tra đủ ba khóa; thiếu → `ValueError`.
- `clear()` ba dict hiện tại.
- `update()` từ bản sao của state (không giữ tham chiếu).

`clear()` dùng `.clear()` trên dict hiện tại, không gán dict mới — nếu ai đó đang giữ tham chiếu tới `ForensicRegistry.SYMPTOMS`, gán mới sẽ làm họ nhìn thấy dict cũ. Đây là chi tiết nhỏ nhưng là bài học thật về alias.

## Bước 7 — Test cô lập

Dùng pytest fixture:

```text
@pytest.fixture(autouse=True)
def registry_state():
    before = ForensicRegistry.snapshot()
    yield
    ForensicRegistry.restore(before)
```

Gợi ý: đừng dùng `clear()` trong fixture nếu module khác đã đăng ký plugin hợp lệ; snapshot/restore giữ trạng thái nền.

Viết test cho:

- Đăng ký rồi tra cứu.
- Idempotent.
- Trùng khác lớp → snapshot không đổi.
- Schema instance → snapshot không đổi.
- Tên xấu → lỗi, không ghi.
- Symptom/scorer cùng tên.
- Snapshot độc lập: sửa dict trả về, registry không đổi.

## Bước 8 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from forensic_registry import ForensicRegistry, DuplicatePluginError

class Cfg: ...
@ForensicRegistry.register_symptom("demo", Cfg)
class Demo: ...

print(ForensicRegistry.get_symptom("demo"))
try:
    ForensicRegistry.register_symptom("demo", Cfg)(type("Other", (), {}))
except DuplicatePluginError as e:
    print("duplicate:", e)
print(len(ForensicRegistry.SYMPTOMS))
PY
```

Kỳ vọng: in ra `(<class ...Demo>, <class ...Cfg>)`, `duplicate: demo`, và `1`.

Kiểm tra không rò rỉ:

```bash
uv run pytest -q tests/test_registry.py::test_lookup_after_register
uv run pytest -q
```

Cả hai phải cùng kết quả. Nếu chạy cả file đỏ mà chạy riêng xanh, fixture chưa cô lập.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Decorator trả `None` | Quên `return symptom_cls`. |
| Lớp biến mất khỏi namespace | Decorator trả một hàm thay vì lớp. |
| Test sau thấy plugin của test trước | Thiếu snapshot/restore. |
| Trùng tên không báo | Chỉ kiểm tra trong decorator sau khi đã ghi. |
| `UnknownPluginError` không bắt được | Lớp lỗi không kế thừa `RegistryError` hoặc bị import sai module. |
| `snapshot` sửa được registry | Trả thẳng dict gốc thay vì bản sao. |
| Đăng ký schema instance vẫn qua | Thiếu `isinstance(config_schema, type)`. |

## Bước 10 — Mở rộng

- Thêm `unregister_*` có kiểm tra đang được dùng.
- Thêm decorator `@ForensicRegistry.plugin` gộp cả hai loại.
- Thêm `describe()` trả bảng tên → loại → schema để CLI in.
- Thêm entry-point discovery bằng `importlib.metadata`, nhưng vẫn giữ đăng ký thủ công làm đường chính.
- Nếu đi xa: thay dict bằng `MappingProxyType` cho tra cứu và giữ dict private, để không ai sửa trực tiếp.

## Tự đánh giá

1. Vì sao decorator phải trả lại lớp thay vì `None`?
2. Vì sao kiểm tra trùng phải diễn ra trước khi ghi bất kỳ dict nào?
3. Snapshot nông có đủ cho bài này không? Khi nào cần snapshot sâu?
4. Nếu hai module cùng đăng ký `"burst"` với hai lớp khác nhau, ai nên thắng? Thiết kế của bạn trả lời câu đó ở đâu?
