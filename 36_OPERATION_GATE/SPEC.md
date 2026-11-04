# SPEC 36 — OperationGate

## 1. Mô hình

```python
@dataclass(frozen=True)
class ToolPolicy:
    name: str
    role: str = "optional_read"
    required_args: tuple[str, ...] = ()

class OperationGate:
    policies: dict[str, ToolPolicy]
    required_satisfied: set[str]
    pending_calls: dict[str, str]       # call_id -> tool_name
    activated_required: set[str]
```

Vai trò hợp lệ: `optional_read`, `required_action`. Vai trò khác → `ValueError` khi tạo policy.

## 2. API

```python
gate.validate_and_track(tool_name, arguments, tool_result=None, *, call_id=None) -> bool
gate.all_required_satisfied() -> bool
gate.report_unsatisfied() -> list[str]
gate.require_tool(tool_name) -> None
gate.reset() -> None
assert_required_tool_invocation(gate, tool_name) -> None
```

`assert_required_tool_invocation` ném `RuntimeError("Required tool '<name>' was not called…")` nếu tool thuộc diện required (policy hoặc activated) và chưa có trong `required_satisfied`; tool optional/không policy là no-op.

`arguments` phải là dict; nếu không → `ValueError("arguments must be a mapping")` **trước** mọi xử lý khác.

## 3. `validate_and_track`

Thứ tự:

1. Nếu `arguments` không phải dict → `INVALID_ARGUMENTS`.
2. `policy = policies.get(tool_name)`.
3. Nếu `policy is None` → `True`.
4. `is_required = policy.role == required_action or tool_name in activated_required`.
5. Nếu không required → `True` (không đụng `arguments`, `tool_result`, `call_id`).
6. Nếu `tool_result is None` (đây là lần gọi):
   1. Với từng `arg` trong `required_args`:
      - thiếu key, `None`, hoặc chuỗi rỗng/whitespace → `MISSING_REQUIRED_ARG` kèm `arg` và `tool`.
   2. `call_id` rỗng/None → `MISSING_CALL_ID`.
   3. `call_id` đã có trong `pending_calls` → `DUPLICATE_CALL_ID` (kể cả cùng tool).
   4. `pending_calls[call_id] = tool_name`; trả `True`.
7. Ngược lại (lần kết quả):
   1. `call_id` rỗng/None → `MISSING_CALL_ID`.
   2. `pending_calls.get(call_id) != tool_name` → `UNCORRELATED_RESULT`.
   3. Result không “typed non-empty” → `EMPTY_RESULT`; **giữ** pending để có thể gửi lại kết quả đúng.
   4. Pop pending; thêm tool vào `required_satisfied`; trả `True`.

Không kiểm tra `required_args` ở bước 7. Không kiểm tra `call_id` cho tool optional/không policy.

## 4. “Typed non-empty”

| Giá trị | Hợp lệ |
|---|---|
| `None` | không (nhưng được hiểu là lần gọi, không phải result) |
| `""`, `"   "` | không |
| `{}`, `[]`, `()`, `set()` | không |
| `0`, `False` | có |
| object bất kỳ khác | có |
| dict/list không rỗng | có |

Không diễn giải thành công nghiệp vụ. `{"status":"failed"}` vẫn hợp lệ về kiểu; tầng nghiệp vụ quyết định.

## 5. Tập bắt buộc

```
required_names = {name | policy.role == required_action}
              ∪ activated_required
```

- `all_required_satisfied`: `required_names ⊆ required_satisfied`.
- `report_unsatisfied`: `sorted(required_names - required_satisfied)`.
- `require_tool(name)`:
  - name không có policy → `UNKNOWN_ACTIVATED_TOOL`.
  - thêm vào activated.
  - Nếu đã satisfied, vẫn giữ satisfied (không thu hồi).
- `reset`: clear cả ba; policy giữ nguyên.

## 6. Lỗi

| Mã | Điều kiện |
|---|---|
| `INVALID_ARGUMENTS` | arguments không phải dict |
| `MISSING_REQUIRED_ARG` | thiếu/None/rỗng/whitespace |
| `MISSING_CALL_ID` | call_id None/rỗng |
| `DUPLICATE_CALL_ID` | call_id đang chờ |
| `UNCORRELATED_RESULT` | result không khớp call đã chờ |
| `EMPTY_RESULT` | result không typed non-empty |
| `UNKNOWN_ACTIVATED_TOOL` | require_tool không tồn tại |
| `REQUIRED_TOOL_NOT_CALLED` | assertion sau request, required chưa satisfied (`RuntimeError`) |

`GateError` là subclass `ValueError`; riêng `REQUIRED_TOOL_NOT_CALLED` là `RuntimeError`.

## 7. Ví dụ cụ thể

Policies:

```json
[
  {"name":"search","role":"optional_read","required_args":[]},
  {"name":"book_flight","role":"required_action","required_args":["flight_id","passenger_id"]},
  {"name":"send_email","role":"optional_read","required_args":[]}
]
```

| Bước | Hành động | Kết quả |
|---|---|---|
| 1 | `validate("search", {})` | True, không tracking |
| 2 | `validate("book_flight", {"flight_id":"F1"})` | `MISSING_REQUIRED_ARG: passenger_id` |
| 3 | `validate("book_flight", {"flight_id":"F1","passenger_id":"P1"}, call_id="c1")` | True, pending c1 |
| 4 | `all_required_satisfied()` | False |
| 5 | `report_unsatisfied()` | `["book_flight"]` |
| 6 | `validate("book_flight", {}, {"status":"ok"}, call_id="c1")` | True, satisfied |
| 7 | `all_required_satisfied()` | True |
| 8 | `validate("book_flight", {}, {"status":"ok"}, call_id="c1")` | `UNCORRELATED_RESULT` |
| 9 | `require_tool("send_email")` | activated |
| 10 | `report_unsatisfied()` | `["send_email"]` |
| 11 | `validate("send_email", {}, call_id="c2")` | True, pending |
| 12 | `validate("send_email", {}, "", call_id="c2")` | `EMPTY_RESULT`, c2 vẫn pending |
| 13 | `validate("send_email", {}, "sent", call_id="c2")` | True, satisfied |
| 14 | `reset()` | mọi tập rỗng |
| 15 | `require_tool("missing")` | `UNKNOWN_ACTIVATED_TOOL` |
| 16 | `validate("unknown_tool", {})` | True |

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | `arguments=None` | `INVALID_ARGUMENTS` |
| 2 | Required arg `0` | hợp lệ (không phải None/str) |
| 3 | Required arg `False` | hợp lệ |
| 4 | Required arg `"  "` | `MISSING_REQUIRED_ARG` |
| 5 | Call id `""` | `MISSING_CALL_ID` |
| 6 | Cùng call id hai tool khác nhau | `DUPLICATE_CALL_ID` ở lần hai |
| 7 | Result trước call | `UNCORRELATED_RESULT` |
| 8 | Result với call id khác | `UNCORRELATED_RESULT` |
| 9 | Result `{}` | `EMPTY_RESULT`, pending giữ |
| 10 | Result `[]`/`()`/`set()` | `EMPTY_RESULT` |
| 11 | Result `0` | hợp lệ |
| 12 | Tool optional có result rác | True, bỏ qua |
| 13 | Tool optional được activate, thiếu call id | `MISSING_CALL_ID` |
| 14 | `require_tool` trước khi gọi | unsatisfied chứa tên |
| 15 | `require_tool` sau khi satisfied | vẫn satisfied |
| 16 | `reset` giữa chừng | pending mất, phải gọi lại |
| 17 | Policy role lạ | `ValueError` lúc tạo |
| 18 | `required_args` trùng | lỗi cấu hình (validate policy) |

## 9. Tiêu chí chấp nhận

- [ ] 16 bước ví dụ khớp.
- [ ] Không kiểm tra args ở bước result.
- [ ] Result rỗng không đánh dấu satisfied và giữ pending.
- [ ] Call id trùng bị chặn.
- [ ] `report_unsatisfied` sorted.
- [ ] Optional tool không bị theo dõi.
- [ ] `reset` xóa đúng ba tập, không xóa policy.
- [ ] Cùng chuỗi bước cho cùng trạng thái.

## 10. Non-goals

- Không gọi tool, không kiểm tra tool thật.
- Không xác thực schema đầy đủ; chỉ required_args.
- Không đảm bảo nghiệp vụ thành công.
- Không lưu trạng thái qua nhiều request.
