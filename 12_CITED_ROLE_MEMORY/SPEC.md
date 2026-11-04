# SPEC — Cited role memory

## Mục tiêu hành vi

Trước một quyết định của agent ở `day`, đọc một ngữ cảnh bộ nhớ đã giới hạn theo vai và theo hiểu biết tính đến `day - 1`. Trả về bản ghi có `read_id` và danh sách `fact_id`; sau đó sinh câu trích dẫn chính xác để gắn vào đầu ra quyết định.

## Kiểu

```python
from enum import StrEnum
from typing import Protocol

class AgentRole(StrEnum):
    ANALYST = "analyst"
    PLANNER = "planner"

@dataclass(frozen=True, slots=True)
class MemoryFact:
    fact_id: str
    role: AgentRole
    valid_from_day: int      # fact bắt đầu có hiệu lực
    known_as_of_day: int     # fact được biết tới hệ thống từ ngày này
    text: str

@dataclass(frozen=True, slots=True)
class MemoryContextRead:
    read_id: str
    role: AgentRole
    day: int
    fact_ids: tuple[str, ...]
    context_text: str

class MemoryStore(Protocol):
    @property
    def enabled(self) -> bool: ...
    def request_context(
        self,
        *,
        role: AgentRole,
        valid_at_day: int,
        known_as_of_day: int,
        stable_prefix: str,
    ) -> MemoryContextRead | None: ...
```

## API

```python
MAX_FACTS = 5
MAX_CONTEXT_CHARS = 400
MAX_FACT_CHARS = 200

def read_role_memory(
    store: MemoryStore,
    role: AgentRole,
    *,
    episode_seed: int,
    day: int,
) -> MemoryContextRead | None: ...

def memory_citation(read: MemoryContextRead | None) -> str: ...
```

## `read_role_memory`

Thứ tự:

1. `day` phải là `int` (không `bool`), `day >= 1`; nếu không → `ValueError`.
2. `episode_seed` phải là `int` (không `bool`), `>= 0`; nếu không → `ValueError`.
3. `role` phải là `AgentRole`; nếu không → `TypeError`.
4. Nếu `store.enabled is False` → trả `None`, **không** gọi `request_context`.
5. `known_as_of_day = day - 1`.
6. Gọi `request_context(role=role, valid_at_day=day, known_as_of_day=day - 1, stable_prefix=f"{role.value} role decision episode {episode_seed} day {day}")`.
7. Nếu store trả `None` → trả `None`.
8. Kiểm tra hợp đồng của kết quả:
   - `read.role == role`, `read.day == day`.
   - `len(read.fact_ids) <= MAX_FACTS`.
   - `len(read.context_text) <= MAX_CONTEXT_CHARS`.
   - `read.fact_ids` không trùng.
   - Nếu vi phạm → `MemoryContractError`.
9. Trả `read`.

`stable_prefix` là chuỗi chính xác, không thêm dấu, không đổi thứ tự. Nó giúp store tạo cache key ổn định.

## `memory_citation`

| Đầu vào | Kết quả |
|---|---|
| `None` | `""` |
| `fact_ids == ()` | `" Shared memory read {read_id} found no matching shared fact."` |
| có fact | `" Shared memory read {read_id} cited facts: {id1, id2}."` |

Quy tắc:

- Luôn có **một** dấu cách ở đầu khi `read` không phải `None`.
- `read_id` và các id được dùng nguyên văn (`str(...)`).
- Phân tách bằng `", "`.
- Kết thúc bằng dấu chấm.
- Không sắp xếp lại `fact_ids`; thứ tự do store quyết định.
- Không xuất nội dung fact, chỉ id.

## Store tham chiếu

`InMemoryStore(facts: Sequence[MemoryFact])`:

- `enabled` cấu hình được, mặc định `True`.
- Bộ đếm `read_id` tăng dần: `read-0001`, `read-0002`, … (định dạng 4 chữ số, tối thiểu).
- `request_context`:
  1. Kiểm tra `valid_at_day >= 1`, `0 <= known_as_of_day < valid_at_day`.
  2. Lọc fact thỏa **cả ba**:
     - `fact.role == role`
     - `fact.valid_from_day <= valid_at_day`
     - `fact.known_as_of_day <= known_as_of_day`
  3. Sắp theo `(known_as_of_day, fact_id)` tăng dần.
  4. Duyệt, thêm fact nếu tổng độ dài context sau khi thêm (kể cả dấu `\n` phân tách) `<= 400`; dừng ở fact đầu tiên không vừa (không nhảy qua để lấy fact nhỏ hơn).
  5. Tối đa 5 fact.
  6. `context_text = "\n".join(text của các fact được chọn)`.
  7. Trả bản ghi, kể cả khi không có fact (ids rỗng, context rỗng).

Không có fact phù hợp **không** phải `None`; `None` chỉ dành cho trường hợp store tắt hoặc store quyết định không trả.

## Kiểm tra `MemoryFact`

- `fact_id`: string khớp `^[a-z0-9][a-z0-9_.:-]{0,63}$`.
- `valid_from_day`, `known_as_of_day`: `int` (không bool), `>= 0`.
- `text`: string, `1 <= len <= 200` (đếm code point Python).
- `role` là `AgentRole`.

## Ví dụ

Fact:

| id | role | valid_from | known_as_of | text |
|---|---|---:|---:|---|
| `f1` | analyst | 1 | 1 | `alpha` |
| `f2` | analyst | 1 | 2 | `beta` |
| `f3` | analyst | 5 | 3 | `gamma` |
| `f4` | planner | 1 | 1 | `delta` |

Ngày 4, cutoff 3, role analyst:

- `f1` thỏa; `f2` thỏa; `f3` có `valid_from_day = 5 > 4` → loại; `f4` sai role.
- Thứ tự `(1,f1)`, `(2,f2)`.
- `fact_ids = ("f1","f2")`; `context_text = "alpha\nbeta"`.
- Citation: `" Shared memory read read-0001 cited facts: f1, f2."`

Ngày 5, cutoff 4: thêm `f3` (`valid_from 5 <= 5`, `known 3 <= 4`) → `f1,f2,f3`.

Ngày 1, cutoff 0: `f1` có `known_as_of 1 > 0` → loại; kết quả rỗng.
Citation: `" Shared memory read read-0001 found no matching shared fact."`

Store tắt: `read_role_memory` trả `None`; citation `""`.

## Ngân sách ký tự

Ví dụ 3 fact, mỗi text dài 150 ký tự:

- Thêm fact 1: 150 ≤ 400 → nhận.
- Thêm fact 2: 150 + 1 + 150 = 301 ≤ 400 → nhận.
- Thêm fact 3: 301 + 1 + 150 = 452 > 400 → dừng; không nhận fact 3 dù còn chỗ cho một fact ngắn hơn.

Đây là quy tắc “dừng”, không phải “bỏ qua rồi thử tiếp”. Ghi rõ để test ổn định.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `day = 0` | `ValueError` |
| `day = True` | `ValueError` (bool) |
| `episode_seed = -1` | `ValueError` |
| `role = "analyst"` (str) | `TypeError` |
| Store tắt | `None`, store không được gọi |
| Store trả read sai `day` | `MemoryContractError` |
| Store trả 6 fact | `MemoryContractError` |
| Store trả context 401 ký tự | `MemoryContractError` |
| Fact trùng id trong read | `MemoryContractError` |
| Không có fact | `read` với ids rỗng, không `None` |
| Fact có `known_as_of > cutoff` | loại |
| Fact có `valid_from > day` | loại |
| Fact `text` 201 ký tự | `ValueError` khi tạo |
| `fact_id` có chữ hoa | `ValueError` |
| `read_id` rỗng | `MemoryContractError` |

## Tiêu chí nghiệm thu

1. Ba ví dụ ngày 4/5/1 cho đúng `fact_ids`, `context_text`, citation.
2. Store tắt trả `None` và không gọi `request_context` (dùng spy).
3. Test cutoff: fact biết ở ngày `day` bị loại khi cutoff `day-1`.
4. Test role isolation: planner không thấy fact analyst.
5. Test giới hạn 5 fact và 400 ký tự với quy tắc dừng.
6. Test citation rỗng và None.
7. Test contract error cho sai day/role/quá giới hạn.
8. `pytest -q` xanh.

## Non-goals

- Vector search, embedding, ranking theo ngữ nghĩa.
- Gọi LLM hoặc tóm tắt fact.
- Đồng bộ nhiều store, phân quyền người dùng.
- Nén ngữ cảnh hoặc cắt giữa fact.
- Đo chất lượng recall.
