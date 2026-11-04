# SPEC 54 — Phong bì an toàn cho agent

## 1. Hằng số

```text
MAX_REQUEST_INPUT_CHARACTERS = 100_000
MAX_AGENT_GRAPH_STEPS = 12
```

Đơn vị "ký tự" = **codepoint Python** (`len(str)`), không phải byte UTF-8, không phải grapheme cluster.

## 2. `check_input`

```text
check_input(text: str) -> None
```

- `len(text) <= 100_000` ⇒ trả `None`.
- `len(text) == 100_001` ⇒ ném `InputTooLong(limit=100_000, actual=100_001)`.
- `text` không phải `str` ⇒ `InvalidInputType(got)`.

`InputTooLong` có `code = "input_too_long"` và thuộc tính `actual`.

Ví dụ:

| Chuỗi | Kết quả |
|---|---|
| 99 999 ký tự `"a"` | OK |
| 100 000 ký tự `"a"` | OK (biên cho phép) |
| 100 001 ký tự `"a"` | `InputTooLong(100_000, 100_001)` |
| 100 000 emoji `"😀"` | OK — `len` là 1 mỗi emoji |
| 50 000 emoji `"😀"` | OK |

## 3. `StepBudget`

```text
budget = StepBudget(max_steps=12)      # max_steps là tham số, mặc định 12
budget.consume() -> int                # trả số bước đã dùng sau khi tăng
budget.remaining -> int
```

- `consume()` lần thứ 1..12 thành công với `max_steps = 12`.
- Lần thứ 13 ném `StepBudgetExceeded(limit=12, attempted=13)`; bộ đếm **không** tăng khi ném.
- `max_steps < 1` ⇒ `InvalidBudget` tại constructor.

Ví dụ: `max_steps = 2`; `consume()` → 1; `consume()` → 2; `remaining == 0`; `consume()` → `StepBudgetExceeded(2, 3)`; gọi lại `consume()` vẫn `attempted == 3`.

## 4. `run_sync`

```text
run_sync(coro) -> Any
```

Hai nhánh:

1. **Không có event loop đang chạy** trong thread hiện tại ⇒ `asyncio.run(coro)`.
2. **Có** event loop đang chạy ⇒ chạy coroutine trong một thread riêng với `asyncio.run` của thread đó, chờ kết quả, rồi trả.

Bắt buộc:

- Không bao giờ ném `RuntimeError("asyncio.run() cannot be called from a running event loop")`.
- Ngoại lệ từ coroutine truyền nguyên (cùng kiểu, cùng thông điệp).
- Không rò thread: thread được join trước khi trả.
- Không dùng `asyncio.get_event_loop()` (đã deprecated theo cách dùng này).

Ví dụ:

```text
async def add(a, b): return a + b

run_sync(add(1, 2)) == 3                      # ngoài loop: nhánh 1

async def outer():
    return run_sync(add(2, 3))                # trong loop: nhánh 2
asyncio.run(outer()) == 5
```

## 5. `make_sync_tool`

```text
make_sync_tool(async_fn) -> Callable[..., Any]
```

- Trả một hàm sync gọi `run_sync(async_fn(*args, **kwargs))`.
- Giữ `async_fn.__name__` và `__doc__` trên hàm trả về (dùng `functools.wraps`).
- Gọi được cả trong và ngoài loop.
- Ngoại lệ của `async_fn` truyền nguyên.

Ví dụ: tool async `fetch_order(order_id)` trả `{"id": order_id}`; bản sync gọi `fetch_order("A1")` trả cùng dict, `__name__ == "fetch_order"`.

## 6. `safe_messages`

```text
safe_messages(messages: list[dict]) -> list[dict]
```

Đây là **hàm xuất** (egress), không sửa đầu vào.

Quy tắc:

1. Trả list mới; mỗi phần tử mới.
2. `content` dạng `str` ⇒ giữ nguyên chuỗi.
3. `content` dạng list ⇒ chỉ giữ block có `type == "text"`; mỗi block rút gọn còn `{"type": "text", "text": <str>}`. Block khác bị bỏ.
4. Khóa nội bộ (bắt đầu bằng `_`) bị bỏ khỏi mỗi message.
5. Khóa công khai khác (`role`, `name`) giữ nguyên.
6. Không sửa `messages` gốc: so sánh sâu sau khi gọi phải bằng trước khi gọi.

Ví dụ:

```json
[
  {"role": "assistant", "content": "Xin chào", "name": "bot", "_trace": "t-1"},
  {"role": "assistant", "_trace": "t-2", "content": [
    {"type": "text", "text": "Giá là 10", "annotations": ["x"]},
    {"type": "internal", "data": {"sql": "select 1"}},
    {"type": "text", "text": "Liên hệ sau"}
  ]}
]
```

Kết quả:

```json
[
  {"role": "assistant", "content": "Xin chào", "name": "bot"},
  {"role": "assistant", "content": [
    {"type": "text", "text": "Giá là 10"},
    {"type": "text", "text": "Liên hệ sau"}
  ]}
]
```

Block `internal` biến mất; `annotations` bị bỏ; `_trace` bị bỏ.

## 7. Tích hợp

```text
handle(request):
    check_input(request.text)
    budget = StepBudget()
    ...
    budget.consume()   # mỗi bước graph
    ...
    return {"messages": safe_messages(state.messages)}
```

`handle` chỉ là ví dụ tích hợp; không cần cài agent thật.

## 8. Tiêu chí chấp nhận

1. Bảng ở mục 2 cho đúng kết quả, kể cả emoji.
2. `StepBudget`: 12 lần OK, lần 13 ném; `attempted` không tăng khi ném; gọi lại vẫn `attempted == 13`.
3. `run_sync` trả `3` ngoài loop và `5` trong loop như ví dụ mục 4; không có cảnh báo `RuntimeError`.
4. Ngoại lệ từ coroutine (`ValueError("boom")`) truyền nguyên qua cả hai nhánh.
5. `make_sync_tool` giữ `__name__`, `__doc__`, và gọi được trong loop.
6. `safe_messages` khớp ví dụ mục 6 từng khóa; đầu vào không đổi (so sánh sâu).
7. `safe_messages([])` trả `[]`; message không có `content` giữ nguyên các khóa công khai còn lại.
8. Không tạo thread rò: sau 100 lần gọi `run_sync` trong loop, `threading.active_count()` trở về giá trị ban đầu.
9. CLI `check` trả `0` cho 100 000 và `2` cho 100 001.

## 9. Non-goals

- Không gọi mạng, không SDK, không framework agent.
- Không đếm token, không cắt ngữ cảnh theo token.
- Không xử lý streaming; không giới hạn tần suất.
