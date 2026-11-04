# GUIDE 56 — Hàng rào ghi cho xuất/nhập dự án

## 1. Bài toán đồng bộ, không phải bài toán HTTP

Phần khó không nằm ở regex phân loại đường dẫn (dễ), mà ở ba tính chất:

1. **Barrier**: epoch xuất phải chặn *mọi* thao tác mới ngay khi bắt đầu, kể cả khi nó còn đang chờ các thao tác cũ.
2. **Không lọt**: sau mỗi `wait()`, writer phải kiểm tra lại điều kiện. `asyncio.Condition` không hứa rằng khi được đánh thức thì điều kiện đã đúng.
3. **Sổ sách tự phát hiện**: nếu ai đó gọi `exit` hai lần, fence phải báo, không âm thầm hỏng.

## 2. Thiết kế

```text
src/
├── fence.py    # ProjectWriteFence + context managers + lỗi
├── routes.py   # classify(method, path)
└── __main__.py # --classify fixture, --scenario fixture
```

### 2.1 Vì sao `Condition` chứ không `Lock`

- `asyncio.Lock` cho writer độc quyền nhưng không diễn đạt "chờ đến khi readers = 0 và writers = 0" một cách rõ ràng.
- `Condition` cho phép một chỗ chờ nhiều điều kiện, và `notify_all` khi state đổi.
- Reader đếm được (không phải lock) nên nhiều reader cùng vào.

### 2.2 Epoch như barrier

Thứ tự trong `export_epoch` quan trọng:

```python
if self._exporting: raise ExportAlreadyRunning
self._exporting = 1            # (1) đặt cờ TRƯỚC
try:
    while self._readers or self._writers:
        await self._cond.wait()
    yield
finally:
    self._exporting = 0        # (2) nhả trong finally
    self._cond.notify_all()
```

Nếu bạn đặt `_exporting = 1` **sau** vòng chờ, cửa sổ giữa "chờ xong" và "đặt cờ" cho phép một writer lọt vào.

## 3. Thứ tự cài đặt

### Bước 1 — Bất biến và một hàm kiểm tra

```python
def _check(self):
    assert ...  # hoặc raise FenceAccountingError với mô tả
```

Gọi **cuối mỗi** hàm thay đổi state. Nếu bạn chỉ gọi trong `__init__`, nó vô dụng.

### Bước 2 — Reader

`enter_read` chờ khi `_writers or _exporting`. Chú ý dùng `while`, không `if` — spurious wake-up là có thật.

### Bước 3 — Writer

Viết vòng lặp có **hai** điều kiện:

```text
while True:
    if self._exporting: raise FenceClosedForExport
    if self._readers == 0 and self._writers == 0: break
    await self._cond.wait()
```

Sai lầm phổ biến: kiểm tra `_exporting` chỉ một lần trước vòng lặp. Khi writer bị đánh thức sau khi export bắt đầu, nó sẽ vào nếu không kiểm tra lại.

### Bước 4 — Context manager

```python
@asynccontextmanager
async def read(self):
    await self.enter_read()
    try:
        yield
    finally:
        self.exit_read()
```

`finally` là bắt buộc; nếu không, một ngoại lệ trong thân `async with` làm reader rò vĩnh viễn.

### Bước 5 — Phân loại

Viết bảng luật theo đúng thứ tự SPEC. Đừng dùng một regex gộp: thứ tự ưu tiên mới là ngữ nghĩa.

Lưu ý `_DELETION_PATH` khớp `^/v1/projects/[^/]+$` — tức chỉ xoá cả dự án, không xoá tài nguyên con. Nếu bạn dùng `^/v1/projects/[^/]+.*`, `DELETE /v1/projects/p1/notes` sẽ thành `DELETION` sai.

## 4. Cạm bẫy

- **`if` thay vì `while` khi chờ**: spurious wake-up hoặc notify sai đối tượng.
- **Đặt `_exporting` sau khi chờ**: writer lọt.
- **Quên `finally`**: fence kẹt sau ngoại lệ; test 5.5 bắt.
- **`notify()` thay `notify_all()`**: writer và reader chờ cùng condition; đánh thức một người có thể bỏ đói người còn lại.
- **Giảm bộ đếm trước khi kiểm tra**: âm thầm về 0 rồi mới raise, state đã hỏng.
- **`exit_write(clean=False)` không đặt cờ**: mất tín hiệu phục hồi.
- **Test bằng `sleep`**: flaky. Dùng `asyncio.Event` để chặn/giải phóng.
- **Regex không neo `$`**: `/v1/projects/p1/exports/extra` lọt vào `EXPORT`.
- **Cho `GET` vào `_MUTATING_METHODS`**: phân loại sai toàn bộ.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `reader_blocks_writer` | 5.1, log đúng thứ tự |
| `export_blocks_new_write` | 5.2, `FenceClosedForExport`, `write_attempted == 1` |
| `writer_blocks_export` | 5.3 |
| `export_exclusive` | 5.4 |
| `export_exception` | 5.5, `exporting == False` |
| `two_readers` | hai reader cùng lúc, không chặn nhau |
| `exit_unbalanced` | hai loại lỗi sổ sách |
| `classify_table` | 9 dòng bảng |
| `no_sleep` | grep test |
| `repeat_20` | chạy 20 lần không flaky |

Cách viết test 5.1 không dùng sleep:

```python
started = asyncio.Event()
release = asyncio.Event()

async def reader():
    async with fence.read():
        log.append("r_in"); started.set()
        await release.wait()
    log.append("r_out")

async def writer():
    async with fence.write():
        log.append("w_in")
```

`await started.wait()` trước khi tạo writer task; sau đó `await asyncio.sleep(0)` vài lần (yield, không phải chờ thời gian) để writer kịp chạy tới `wait()`, rồi khẳng định `"w_in" not in log`. `sleep(0)` chỉ nhường lịch, không phụ thuộc thời gian thực — chấp nhận được, nhưng ghi rõ.

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src classify --fixture fixtures/paths.json
python -m src scenario --fixture fixtures/scenario_export.json
```

`classify` phải in đúng bảng mục 4 của SPEC. Kiểm tra không dùng `sleep`:

```bash
grep -Rn "asyncio.sleep" tests/ src/ ; echo "exit=$?"
```

Chỉ được thấy `asyncio.sleep(0)` ở chỗ nhường lịch (nếu dùng); không có `sleep(0.1)`.

## 7. Gợi ý

- Viết `log.append` trong mọi nhánh enter/exit; so log là cách kiểm tra thứ tự mạnh hơn so state.
- Viết `assert_clean(fence)` gọi ở cuối mỗi test: ba bộ đếm bằng 0/False.
- Với test export, dùng hai task và một `Event` "epoch_entered" để biết khi nào export thực sự vào.
- Nếu muốn thấy vấn đề fairness, viết test 10 reader đến liên tục và một writer; quan sát writer chờ bao lâu (đếm số lần reader vào trước).

## 8. Mở rộng

- **Ưu tiên writer**: thêm `_writers_waiting`; reader chờ khi có writer đang chờ. So sánh fairness.
- **Timeout**: `enter_write(timeout_ms)` dùng `asyncio.wait_for`; test với đồng hồ giả hoặc timeout rất ngắn.
- **Maintenance kind**: thêm chế độ bảo trì (như nguồn có `_maintenance_kind`) chặn ghi nhưng cho đọc.
- **Khoá phân tán**: mô phỏng bằng file lock; nêu rõ giới hạn một máy.
- **Đo lường**: đếm thời gian chờ trung bình của writer (dùng `time.perf_counter` chỉ trong test) để thấy chi phí của fence.
