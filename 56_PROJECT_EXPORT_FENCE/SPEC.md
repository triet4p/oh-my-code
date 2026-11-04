# SPEC 56 — Hàng rào ghi cho xuất/nhập dự án

## 1. Trạng thái và bất biến

```text
_readers: int >= 0
_writers: int trong {0, 1}
_exporting: int trong {0, 1}
_write_attempted: int >= 0
_recovery_required: bool
_cond: asyncio.Condition
```

Bất biến kiểm tra **sau mọi thay đổi** (vi phạm ⇒ `FenceAccountingError`):

1. `_readers >= 0`, `_writers in {0,1}`, `_exporting in {0,1}`, `_write_attempted >= 0`.
2. Không đồng thời `_readers > 0` và `_writers > 0`.
3. Không đồng thời `_exporting > 0` và `_writers > 0`.

## 2. API

```python
async def enter_read() -> None
def exit_read() -> None
async def enter_write() -> None
def exit_write(clean: bool = True) -> None
@asynccontextmanager async def read()
@asynccontextmanager async def write()
@asynccontextmanager async def export_epoch()
```

Thuộc tính chỉ đọc: `active_readers`, `active_writers`, `exporting`, `write_attempted`, `recovery_required`.

## 3. Chính sách

### 3.1 Reader

```text
enter_read:
    while _writers > 0 or _exporting > 0: await _cond.wait()
    _readers += 1

exit_read:
    _readers -= 1; kiểm tra bất biến; _cond.notify_all()
```

Reader **không** độc quyền; nhiều reader chạy song song khi không có writer và không có export.

### 3.2 Writer

```text
enter_write:
    _write_attempted += 1
    while True:
        nếu _exporting > 0: raise FenceClosedForExport      # không chờ
        nếu _readers == 0 và _writers == 0: break
        await _cond.wait()
    _writers = 1

exit_write(clean):
    nếu _writers == 0: raise FenceAccountingError("writer exit without enter")
    _writers = 0
    nếu not clean: _recovery_required = True
    kiểm tra bất biến; _cond.notify_all()
```

Điểm cốt lõi: sau mỗi lần `wait()` trả về, phải **kiểm tra lại** `_exporting` — nếu không, một writer có thể lọt vào giữa epoch xuất.

`_write_attempted` tăng ngay khi gọi, kể cả lần bị từ chối.

### 3.3 Epoch xuất

```text
export_epoch:
    nếu _exporting > 0: raise ExportAlreadyRunning
    _exporting = 1
    try:
        while _readers > 0 or _writers > 0: await _cond.wait()
        yield
    finally:
        _exporting = 0; kiểm tra bất biến; _cond.notify_all()
```

- Đặt `_exporting = 1` **trước** khi chờ, để reader/writer mới bị chặn ngay (barrier).
- `finally` bảo đảm nhả kể cả khi thân `async with` ném ngoại lệ.
- Hai epoch đồng thời ⇒ epoch thứ hai `ExportAlreadyRunning`.

### 3.4 Sổ sách không nhất quán

| Tình huống | Kết quả |
|---|---|
| `exit_read()` khi `_readers == 0` | `FenceAccountingError` |
| `exit_write()` khi `_writers == 0` | `FenceAccountingError` |
| sau bất kỳ thay đổi, vi phạm bất biến 2 hoặc 3 | `FenceAccountingError` (không sửa state) |
| `exit_write(clean=False)` | `recovery_required == True`, fence vẫn dùng tiếp |

## 4. Phân loại request

```text
_EXPORT_PATH       = ^/v1/projects/[^/]+/exports$
_IMPORT_APPLY_PATH = ^/v1/projects/[^/]+/imports/[^/]+/apply$
_DELETION_PATH     = ^/v1/projects/[^/]+$
_MUTATING_METHODS  = {POST, PUT, PATCH, DELETE}
```

Thứ tự kiểm tra (dừng ở luật đầu tiên khớp):

| # | Điều kiện | Kết quả |
|---|---|---|
| 1 | `POST` và khớp `_EXPORT_PATH` | `EXPORT` |
| 2 | `POST` và khớp `_IMPORT_APPLY_PATH` | `IMPORT_APPLY` |
| 3 | `DELETE` và khớp `_DELETION_PATH` | `DELETION` |
| 4 | method thuộc `_MUTATING_METHODS` | `MUTATION` |
| 5 | method thuộc `{GET, HEAD}` | `READ` |
| 6 | còn lại | `OTHER` |

Bảng ví dụ:

| Method | Path | Kết quả |
|---|---|---|
| `GET` | `/v1/projects/p1` | `READ` |
| `GET` | `/v1/projects/p1/exports` | `READ` |
| `POST` | `/v1/projects/p1/exports` | `EXPORT` |
| `POST` | `/v1/projects/p1/imports/job1/apply` | `IMPORT_APPLY` |
| `DELETE` | `/v1/projects/p1` | `DELETION` |
| `PUT` | `/v1/projects/p1` | `MUTATION` |
| `PATCH` | `/v1/projects/p1/exports` | `MUTATION` |
| `OPTIONS` | `/v1/projects/p1` | `OTHER` |
| `DELETE` | `/v1/projects/p1/exports` | `MUTATION` |

Ghi chú: `DELETE` trên đường dẫn export **không** phải `EXPORT` — regex export chỉ áp cho `POST`.

## 5. Kịch bản tất định

Test dùng `asyncio.Event` để điều khiển thứ tự; **không** dùng `sleep`.

### 5.1 Reader chặn writer

```text
log = []
reader task:  enter_read();  log.append("r_in");  await gate.wait();  exit_read(); log.append("r_out")
main:         await started;  writer task: enter_write(); log.append("w_in")
main:         assert "w_in" không có trong log
main:         gate.set(); await writer
```

Kết quả log: `["r_in", "r_out", "w_in"]`.

### 5.2 Export chặn ghi mới

```text
reader đang giữ (readers = 1)
task A: export_epoch() -> _exporting = 1, chờ readers = 0
task B: enter_write() -> FenceClosedForExport (ngay, không chờ)
reader exit -> A vào epoch
```

`write_attempted == 1` dù B thất bại.

### 5.3 Writer chặn export

```text
writer đang giữ (writers = 1)
task A: export_epoch() -> _exporting = 1, chờ writers = 0
writer exit -> A vào
```

Trong lúc chờ, `enter_read()` của task khác phải chờ (vì `_exporting > 0`).

### 5.4 Hai epoch

`task A` trong epoch; `task B` gọi `export_epoch()` ⇒ `ExportAlreadyRunning` ngay.

### 5.5 Ngoại lệ trong epoch

`async with fence.export_epoch(): raise ValueError` ⇒ `exporting == False` sau khi thoát, và writer kế tiếp vào được.

## 6. Tiêu chí chấp nhận

1. 5.1 log đúng `["r_in","r_out","w_in"]`; writer không vào khi reader còn giữ.
2. 5.2 ném `FenceClosedForExport` **trước** khi writer vào; `write_attempted == 1`.
3. 5.3 export chỉ vào sau khi writer thoát; reader mới bị chặn trong lúc `exporting`.
4. 5.4 `ExportAlreadyRunning`; epoch đầu vẫn hoạt động.
5. 5.5 sau ngoại lệ, `exporting is False` và writer vào được.
6. Bảng phân loại mục 4 đúng cả 9 dòng.
7. `exit_read`/`exit_write` không cân xứng ⇒ `FenceAccountingError`; state không đổi sau lỗi.
8. Sau mọi kịch bản sạch: `active_readers == 0`, `active_writers == 0`, `exporting is False`.
9. Không có `asyncio.sleep` trong test (grep).
10. Chạy lại toàn bộ test 20 lần liên tiếp không flaky.

## 7. Non-goals

- Không khoá phân tán; không nhiều tiến trình.
- Không timeout cho reader/writer giữ lâu.
- Không công bằng giữa các writer (có thể đói).
- Không HTTP server, không DB.
