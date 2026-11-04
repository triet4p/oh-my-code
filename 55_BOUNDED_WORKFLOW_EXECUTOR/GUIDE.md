# GUIDE 55 — Bộ thực thi workflow có ngân sách

## 1. Ba trục phải tách

| Trục | Trách nhiệm | Sai lầm điển hình |
|---|---|---|
| Ngân sách | Đếm và chặn | Kiểm tra sau khi đã tiêu |
| Trạng thái | Hợp lệ hoá chuyển | Gán trực tiếp, bỏ bảng |
| Sổ thao tác | Khử trùng lặp | Phát lại vẫn gọi hàm |

Bài này khó vì ba trục chồng lên nhau ở cùng một vòng lặp. Tách hàm cho từng trục là cách duy nhất để test được.

## 2. Thiết kế

```text
src/
├── limits.py     # WorkflowRunLimits + hằng
├── states.py     # RunState, StopReason, ALLOWED, transition()
├── ledger.py     # operation_key(), Ledger
├── executor.py   # run(script, tools, limits, clock) -> RunResult
└── __main__.py
```

### 2.1 Ngân sách như một đối tượng

```text
class Budgets:
    turns, tool_calls, context_chars
    def can_take_turn(self) -> bool
    def take_turn(self)
    ...
```

Nếu bạn rải `if turns >= 12` khắp vòng lặp, các ngân sách sẽ trôi khỏi nhau khi thêm cái thứ năm (như nguồn có sáu tham số).

### 2.2 Trạng thái như bảng

```python
ALLOWED = {
    (RunState.READY, RunState.GENERATING),
    (RunState.GENERATING, RunState.DISPATCHING),
    ...
}
def transition(run, to):
    if (run.state, to) not in ALLOWED and to != RunState.INCOMPLETE:
        raise IllegalTransition(run.state, to)
    run.state = to
```

`INCOMPLETE` được phép từ mọi trạng thái chưa kết thúc; mã hoá bằng nhánh riêng thay vì thêm 7 cặp.

## 3. Thứ tự cài đặt

### Bước 1 — `operation_key`

```python
def operation_key(tool, args):
    blob = json.dumps({"tool": tool, "args": args},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

Kiểm tra bằng tay: `{"a": 1}` và `{"a": "1"}` phải khác key; `{"a":1,"b":2}` và `{"b":2,"a":1}` phải cùng key. Nếu `sort_keys=False`, key phụ thuộc thứ tự dict — sai.

### Bước 2 — Vòng lặp với thứ tự kiểm tra

Bám đúng mục 4 của SPEC. Thứ tự **không** tuỳ ý: kiểm tra thời gian trước để không tiêu thêm ngân sách khác khi đã quá giờ; kiểm tra vòng lặp trước dispatch để không tăng `tool_calls`.

Một cách viết gọn:

```text
for step in script:
    reason = precheck(step, budgets, ledger, clock, limits)
    if reason: return finish(INCOMPLETE, reason)
    apply(step, ...)
```

`precheck` trả `StopReason | None`, không có tác dụng phụ ngoài việc tăng `occurrences` (đây là ngoại lệ có chủ đích: đếm lần dispatch là một phần của kiểm tra).

### Bước 3 — Xác minh hiệu ứng

Giữ `pending_mutation: str | None`. Ở đầu mỗi bước:

```text
if pending_mutation is not None and step.kind != "verify":
    return finish(INCOMPLETE, EFFECT_NOT_VERIFIED)
```

Sau `verify ok`: `pending_mutation = None`; `verify not ok`: dừng.

Ở cuối script: nếu `pending_mutation is not None` ⇒ `EFFECT_NOT_VERIFIED` thay vì `COMPLETED`. Đây là chỗ dễ quên nhất.

### Bước 4 — Đồng hồ

`clock` là `Callable[[], int]` trả milli-giây. Trong test, dùng một hàm đọc từ biến đếm:

```python
ticks = [0]
def clock(): return ticks[0]
# trước mỗi bước: ticks[0] += clock_ticks_ms
```

Không dùng `time.monotonic` trong mã chính; chỉ dùng trong `__main__` khi chạy thật.

### Bước 5 — Quan sát

Giữ `deque(maxlen=limits.max_capture_observations)`; mỗi lần có kết quả mới (không tính replay? — SPEC cho phép cả hai, hãy chọn: chỉ kết quả **thực thi** mới là observation mới) thì `append`. Đếm `dropped` bằng cách so tổng với `maxlen`.

## 4. Cạm bẫy

- **Kiểm tra ngân sách sau khi tiêu**: vượt đúng một đơn vị.
- **Đếm `tool_calls` cả lần bị chặn**: SPEC nói không.
- **Phát lại vẫn gọi hàm**: bug tệ nhất; test `executions == 1` bắt.
- **Đặt lại cờ mutation khi replay**: một mutation đã xác minh, replay sau đó không cần xác minh lại.
- **`EFFECT_NOT_VERIFIED` khi kết thúc**: dễ quên nhánh cuối.
- **`IllegalTransition` cho `INCOMPLETE`**: nếu bạn thêm nó vào bảng cho mọi trạng thái, bảng phình; nếu bạn không cho phép, agent không dừng được.
- **Chuẩn hoá tham số quá tay**: gộp `1` và `"1"` là sai; gộp `{"a":1,"b":2}` và `{"b":2,"a":1}` là đúng.
- **`float` trong args**: `0.1 + 0.2` khác `0.3`; JSON hoá sẽ cho chuỗi khác nhau. Ghi rõ: so sánh theo biểu diễn JSON, không theo ngữ nghĩa số.
- **Chuông báo "gần hết ngân sách"**: nếu bạn trả `COMPLETED` khi còn 1 lượt và script hết, đó là đúng; đừng đánh dấu `INCOMPLETE` chỉ vì sát ngưỡng.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `key_canonical` | hai thứ tự khóa ⇒ cùng key; `1` vs `"1"` ⇒ khác |
| `happy_path` | script 3 bước ⇒ `COMPLETED` |
| `loop_detected` | 8.1: executions 1, replays 2, tool_calls 3 |
| `context_budget` | 8.2 |
| `time_budget` | 8.3 |
| `turn_budget` | 8.4 với 13 generate |
| `tool_budget` | 8.4 với 25 tool khác nhau |
| `effect_unverified` | 8.5 hai biến thể |
| `illegal_transition` | verify không có dispatch |
| `refused` | script refuse ⇒ `REFUSED`, không có stop_reason |
| `observations` | 6 kết quả ⇒ giữ 4, dropped 2 |
| `determinism` | hai lần chạy giống hệt |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src run --fixture fixtures/script_loop.json | python -m json.tool
python -m src run --fixture fixtures/script_effect_unverified.json | python -c "import json,sys; print(json.load(sys.stdin)['stop_reason'])"
```

Lệnh thứ ba phải cho `"executions": 1`; lệnh thứ tư in `EFFECT_NOT_VERIFIED`.

Kiểm tra không có đồng hồ thật:

```bash
grep -Rn "time.time\|time.sleep\|monotonic" src/ ; echo "exit=$?"
```

Kỳ vọng chỉ thấy trong `__main__.py` (nếu có), không trong `executor.py`.

## 7. Gợi ý

- Viết `precheck` và `apply` thành hai hàm; test `precheck` với từng ngân sách mà không cần chạy cả script.
- Viết `RecordingTool` để đếm số lần thực thi — đây là bằng chứng idempotency mạnh nhất.
- Dùng `dataclass(frozen=True)` cho `RunResult`; tránh sửa kết quả sau khi trả.
- Nếu muốn thấy vì sao thứ tự kiểm tra quan trọng, đảo thứ tự 4 và 5 trong một nhánh thử nghiệm và xem `tool_calls` lệch thế nào.

## 8. Mở rộng

- **Huỷ giữa chừng**: thêm `cancel()` set một cờ; kiểm tra ở đầu mỗi bước; test bằng một tool chậm (dùng clock giả).
- **Sổ bền**: ghi ledger ra JSONL sau mỗi thực thi; khôi phục khi chạy lại, chứng minh không có hiệu ứng thứ hai qua hai tiến trình.
- **Ngân sách chi phí**: thêm `max_cost` với chi phí mỗi tool; cùng cơ chế.
- **Đa mutation song song**: nhiều cờ `pending_mutation`; verify phải khớp key.
- **Đo phân bố**: chạy 200 script sinh ngẫu nhiên, thống kê lý do dừng — thấy ngân sách nào chặn nhiều nhất.
