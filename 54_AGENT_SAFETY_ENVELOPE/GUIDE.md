# GUIDE 54 — Phong bì an toàn cho agent

## 1. Bốn thứ nhỏ, bốn loại lỗi lớn

| API | Lỗi nếu làm ẩu |
|---|---|
| `check_input` | Lệch một ký tự ở biên; đếm byte thay vì codepoint |
| `StepBudget` | Tăng bộ đếm trước khi kiểm tra ⇒ vượt một bước |
| `run_sync` | Gọi `asyncio.run` trong loop ⇒ `RuntimeError` giữa request |
| `safe_messages` | Sửa bản gốc; hoặc rò khối nội bộ ra client |

Cả bốn đều là "code glue" mà người ta ít test nhất — và đều là nơi sự cố production hay bắt đầu.

## 2. Thứ tự cài đặt

### Bước 1 — Hằng số và lỗi

Khai báo hằng ở một nơi. Viết lớp lỗi có `code` và thuộc tính số (limit/actual) để test so sánh được, không cần parse chuỗi.

```text
class EnvelopeError(Exception): code: str
class InputTooLong(EnvelopeError): limit, actual
class StepBudgetExceeded(EnvelopeError): limit, attempted
```

### Bước 2 — `check_input`

```python
def check_input(text):
    if not isinstance(text, str): raise InvalidInputType(type(text).__name__)
    n = len(text)
    if n > MAX_REQUEST_INPUT_CHARACTERS:
        raise InputTooLong(MAX_REQUEST_INPUT_CHARACTERS, n)
```

Không dùng `len(text.encode("utf-8"))`: nguồn nói "characters", và test emoji phân biệt hai cách.

### Bước 3 — `StepBudget`

```python
def consume(self):
    attempted = self._used + 1
    if attempted > self._max:
        raise StepBudgetExceeded(self._max, attempted)
    self._used = attempted
    return self._used
```

Điểm tinh tế: `attempted` tính từ `_used` chứ không lưu riêng, nên gọi lại sau khi ném vẫn báo `attempted == 13` với `max_steps = 12` — đúng ví dụ SPEC.

### Bước 4 — `run_sync`

```python
def run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
```

Ba điều cần biết:

1. Coroutine **object** được tạo ở thread gọi nhưng chạy ở thread khác — hợp lệ miễn nó chưa được await.
2. `ThreadPoolExecutor` dạng `with` sẽ join thread khi thoát, nên không rò thread.
3. `contextvars` **không** tự truyền sang thread mới. Nếu cần, dùng `contextvars.copy_context().run(pool.submit, ...)` — ghi chú, không bắt buộc.

Đừng dùng `asyncio.new_event_loop()` + `run_until_complete` mà quên `close()`; rò loop là lỗi khó thấy.

### Bước 5 — `make_sync_tool`

```python
@functools.wraps(async_fn)
def sync_tool(*args, **kwargs):
    return run_sync(async_fn(*args, **kwargs))
return sync_tool
```

`functools.wraps` giữ `__name__`/`__doc__`; test khẳng định.

### Bước 6 — `safe_messages`

```python
def safe_messages(messages):
    out = []
    for m in messages:
        nm = {k: v for k, v in m.items() if not k.startswith("_")}
        c = nm.get("content")
        if isinstance(c, list):
            nm["content"] = [
                {"type": "text", "text": b.get("text", "")}
                for b in c
                if isinstance(b, dict) and b.get("type") == "text"
            ]
        out.append(nm)
    return out
```

Sai lầm phổ biến: `nm = dict(m)` rồi `nm["content"] = ...` sửa list gốc nếu bạn thao tác tại chỗ trên `c`. Hãy tạo list mới (như trên). Với `str`, giữ nguyên.

Cũng đừng bỏ `content` khi nó là `None`; quy tắc chỉ nói về `str` và `list`.

## 3. Cạm bẫy

- **`>=` thay vì `>`** trong `check_input`: chặn nhầm đúng biên 100 000.
- **Đếm byte**: `len("😀".encode())` là 4, `len("😀")` là 1. SPEC chọn codepoint.
- **Tăng bộ đếm trước khi kiểm tra**: `attempted` sai và có thể vượt.
- **Lưu `attempted` trong state**: gọi lại sau lỗi sẽ ra 14 thay vì 13.
- **Bắt `RuntimeError` quá rộng** trong `run_sync`: nuốt cả lỗi thật từ coroutine. Chỉ dò `get_running_loop`.
- **Tạo coroutine rồi không await**: nếu nhánh nào đó trả sớm, Python cảnh báo "coroutine was never awaited"; hãy để một nhánh duy nhất chịu trách nhiệm.
- **`safe_messages` trả cùng list**: client hoặc tầng sau sửa sẽ ảnh hưởng state nội bộ.
- **Giữ khối `image`**: SPEC cấm; nếu muốn, phải có hàm riêng.

## 4. Kiểm thử

| Test | Nội dung |
|---|---|
| `len_99999` / `len_100000` / `len_100001` | ba biên |
| `emoji_len` | 100 000 emoji OK |
| `type_error` | `check_input(b"x")` ⇒ `InvalidInputType` |
| `budget_12_13` | 12 OK, 13 ném, `attempted` ổn định |
| `budget_remaining` | giảm đúng |
| `run_sync_plain` | trả 3 |
| `run_sync_nested` | trả 5, không cảnh báo |
| `run_sync_error` | `ValueError("boom")` truyền nguyên hai nhánh |
| `threads_clean` | sau 100 lần, `active_count` bằng ban đầu |
| `sync_tool_meta` | `__name__`, `__doc__` |
| `safe_messages_example` | khớp mục 6 SPEC |
| `no_mutation` | `deepcopy` trước/sau bằng nhau |
| `empty` | `[]` ⇒ `[]` |

## 5. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -c "from src.envelope import check_input; check_input('a'*100000); print('boundary ok')"
python -c "from src.envelope import check_input, InputTooLong
try: check_input('a'*100001)
except InputTooLong as e: print(e.limit, e.actual)"
```

Lệnh thứ ba phải in `boundary ok`; lệnh thứ tư in `100000 100001`.

Kiểm tra nhánh nested bằng một script nhỏ (đặt trong `tests/`):

```python
import asyncio
from src.envelope import run_sync

async def add(a, b): return a + b

async def main():
    return run_sync(add(2, 3))

print(run_sync(add(1, 2)), asyncio.run(main()))
```

Phải in `3 5` và không có traceback.

## 6. Gợi ý

- Viết `assert_raises(exc_type, fn)` nhỏ trong test để so thuộc tính (`limit`, `actual`) thay vì so chuỗi thông điệp.
- Với `run_sync`, thêm một biến đếm số lần tạo thread trong test (bọc `ThreadPoolExecutor`) để chắc chắn nhánh 1 không tạo thread.
- Với `safe_messages`, viết thêm test "message chỉ có `_trace`" ⇒ kết quả `{}`… nhưng SPEC nói giữ khóa công khai; message rỗng là hợp lệ.
- Đừng đặt các hằng số trong `config` đọc từ file; phong bì phải cố định, nếu không người dùng sẽ nới nó.

## 7. Mở rộng

- **Ngân sách thời gian**: thêm `max_wall_clock_ms` với `time.monotonic` tiêm được (bài 55 làm đầy đủ hơn).
- **Giới hạn kích thước egress**: cắt `safe_messages` theo tổng ký tự, có đánh dấu `truncated`.
- **Contextvars**: truyền context sang thread trong `run_sync`; test bằng một biến `ContextVar` đặt trước khi gọi.
- **Đo lường**: đếm số lần bị chặn theo `code`, xuất metric — nhưng đừng log nội dung đầu vào.
- **Adapter ngược**: `make_async_tool(sync_fn)` dùng `asyncio.to_thread`; so sánh chi phí.
