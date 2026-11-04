# GUIDE — Cited role memory

## Bước 0 — Môi trường

```bash
mkdir 12_CITED_ROLE_MEMORY/work && cd 12_CITED_ROLE_MEMORY/work
uv init . -p 3.12 --lib
uv add --dev pytest
mkdir -p src/role_memory tests
```

## Bước 1 — Protocol thay vì ABC

```python
class MemoryStore(Protocol):
    @property
    def enabled(self) -> bool: ...
    def request_context(self, *, role: AgentRole, valid_at_day: int,
                        known_as_of_day: int, stable_prefix: str) -> MemoryContextRead | None: ...
```

Tại sao Protocol? Store thật có thể là client HTTP/DB, không muốn kế thừa lớp của bạn. Protocol chỉ kiểm tra cấu trúc, phù hợp với dependency injection.

Lưu ý: `@property` trong Protocol nghĩa là thuộc tính, không phải method. Fake store có thể là:

```text
class FakeStore:
    def __init__(self, enabled: bool, read): ...
    @property
    def enabled(self): return self._enabled
    def request_context(self, **kwargs): ...
```

Nếu bạn dùng `enabled` như method, hợp đồng lệch và test sẽ bắt được.

## Bước 2 — Bất biến và validate fact

`MemoryFact` frozen. Validate trong `__post_init__`:

- `isinstance(fact_id, str)`, regex.
- `valid_from_day`, `known_as_of_day` là `int`, không `bool`.
- `text` là `str`, độ dài 1..200.
- `role` là `AgentRole`.

Không kiểm tra `known_as_of <= valid_from`; hai trục thời gian độc lập (một fact có thể được biết trước khi có hiệu lực, hoặc ngược lại). Chỉ store lọc.

## Bước 3 — `read_role_memory`

Viết validate đầu vào trước khi chạm store. Điều này quan trọng vì store có thể đắt hoặc có tác dụng phụ.

```text
if isinstance(day, bool) or not isinstance(day, int) or day < 1:
    raise ValueError("day must be an int >= 1")
...
if not store.enabled:
    return None
prefix = f"{role.value} role decision episode {episode_seed} day {day}"
read = store.request_context(
    role=role,
    valid_at_day=day,
    known_as_of_day=day - 1,
    stable_prefix=prefix,
)
if read is None:
    return None
_validate_read(read, role, day)
return read
```

`_validate_read` kiểm tra:

- `read_id` là string không rỗng.
- `role`/`day` khớp.
- `fact_ids` là tuple/list các string, không trùng, ≤5.
- `context_text` là string, ≤400.
- Nếu `fact_ids` rỗng thì `context_text` phải rỗng; nếu không rỗng thì không được rỗng. Đây là bất biến nội bộ giúp citation không nói dối.

Ném `MemoryContractError` (kế thừa `RuntimeError`) với thông điệp nêu store và lỗi.

## Bước 4 — Store tham chiếu

Bộ đếm:

```text
self._counter = 0
...
self._counter += 1
read_id = f"read-{self._counter:04d}"
```

Nếu vượt 9999, format vẫn mở rộng tự nhiên (`read-10000`), chấp nhận.

Lọc:

```text
eligible = [
    f for f in self._facts
    if f.role == role and f.valid_from_day <= valid_at_day and f.known_as_of_day <= known_as_of_day
]
eligible.sort(key=lambda f: (f.known_as_of_day, f.fact_id))
```

Chọn theo ngân sách:

```text
chosen = []
length = 0
for f in eligible:
    extra = len(f.text) + (1 if chosen else 0)
    if len(chosen) >= 5 or length + extra > 400:
        break
    chosen.append(f)
    length += extra
```

Chú ý: `break`, không `continue`. Test phải phân biệt hai cách.

`context_text = "\n".join(f.text for f in chosen)`.

Nếu không có fact, vẫn tăng counter và trả read rỗng. Tại sao? Vì mỗi lần đọc là một sự kiện kiểm toán, kể cả khi không tìm thấy.

## Bước 5 — Citation

```text
if read is None:
    return ""
ids = tuple(str(x) for x in read.fact_ids)
if ids:
    return f" Shared memory read {read.read_id} cited facts: {', '.join(ids)}."
return f" Shared memory read {read.read_id} found no matching shared fact."
```

Đừng `strip()` kết quả; dấu cách đầu là hợp đồng (nó được ghép sau một câu khác).

Đừng sắp xếp `ids`; nếu store đã sắp theo `(known, id)`, citation phản ánh thứ tự đó. Nếu bạn muốn citation ổn định bất kể store, hãy sắp trong `read_role_memory` — nhưng bài tập chọn tôn trọng store, và store tham chiếu đã tất định.

## Bước 6 — Test

Dùng fixture fact như SPEC. Các nhóm:

1. **Lọc theo ngày**: day 4, 5, 1.
2. **Cutoff**: thêm fact `known_as_of = day` để chứng minh bị loại.
3. **Role**: planner không thấy analyst.
4. **Giới hạn**: 6 fact → 5; text dài → dừng.
5. **Citation**: so khớp từng ký tự.
6. **Contract**: store giả trả read sai; kiểm tra exception.
7. **Store tắt**: spy đếm số lần gọi = 0.

Gợi ý spy:

```text
class SpyStore:
    def __init__(self): self.calls = []
    @property
    def enabled(self): return True
    def request_context(self, **kwargs):
        self.calls.append(kwargs)
        return None
```

Kiểm tra `stable_prefix` chính xác trong `calls[0]`.

## Bước 7 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from role_memory import AgentRole, InMemoryStore, MemoryFact, read_role_memory, memory_citation
facts = [
    MemoryFact("f1", AgentRole.ANALYST, 1, 1, "alpha"),
    MemoryFact("f2", AgentRole.ANALYST, 1, 2, "beta"),
    MemoryFact("f3", AgentRole.ANALYST, 5, 3, "gamma"),
]
store = InMemoryStore(facts)
r4 = read_role_memory(store, AgentRole.ANALYST, episode_seed=0, day=4)
print(r4.read_id, r4.fact_ids, repr(r4.context_text))
print(memory_citation(r4))
r1 = read_role_memory(store, AgentRole.ANALYST, episode_seed=0, day=1)
print(memory_citation(r1))
PY
```

Kỳ vọng:

```text
read-0001 ('f1', 'f2') 'alpha\nbeta'
 Shared memory read read-0001 cited facts: f1, f2.
 Shared memory read read-0002 found no matching shared fact.
```

## Bước 8 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `day=1` thấy fact biết ở ngày 1 | Cutoff sai (`day` thay vì `day-1`). |
| Store tắt vẫn bị gọi | Kiểm tra `enabled` sau khi gọi. |
| `None` bị citation thành chuỗi | Thiếu nhánh `None`. |
| Citation thiếu dấu cách đầu | `f"..."` không có space. |
| Chọn 6 fact | Thiếu kiểm tra `len(chosen)`. |
| Nhảy qua fact lớn để lấy fact nhỏ | Dùng `continue` thay vì `break`. |
| `read_id` lặp | Counter là biến cục bộ trong method. |
| `context_text` không khớp ids | Chọn fact hai lần hoặc quên join. |
| Protocol không khớp | `enabled` là method thay vì property. |

## Bước 9 — Mở rộng

- Thêm `read_id` do store cấp từ UUID và kiểm tra duy nhất.
- Thêm `scope` (project/user) vào fact và lọc.
- Thêm xếp hạng theo độ mới/độ liên quan nhưng vẫn tất định.
- Thêm cache theo `stable_prefix` (bài học về key ổn định).
- Thêm kiểm tra “citation phải là tập con của fact_ids” ở lớp quyết định.

## Tự đánh giá

1. Vì sao `known_as_of_day = day - 1`?
2. Vì sao không trả `None` khi không có fact?
3. Vì sao citation chỉ chứa id, không chứa nội dung?
4. Vì sao Protocol phù hợp hơn ABC ở đây?
