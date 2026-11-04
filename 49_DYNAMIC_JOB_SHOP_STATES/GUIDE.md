# GUIDE 49 — Trạng thái lịch trình job-shop động

## 1. Bốn thứ phải tách

| Thành phần | Trách nhiệm | Không được làm |
|---|---|---|
| Generator | Sinh job từ seed | Không mô phỏng |
| Simulator | Chạy vòng sự kiện, đổi trạng thái | Không sinh dữ liệu |
| Rule | Chọn job từ hàng đợi | Không sửa trạng thái |
| Metrics | Tính từ nhật ký | Không đọc trạng thái nội bộ |

Trộn Generator vào Simulator là lỗi phổ biến nhất: kết quả mô phỏng trở nên phụ thuộc thứ tự sinh, và bạn mất khả năng chạy lại đúng instance.

## 2. Thiết kế

### 2.1 Cấu trúc

```text
Job:
    id, arrival, deadline, weight
    operations: list[Operation(machine, duration)]
    op_index: int          # công đoạn kế tiếp
    status: Status
    enqueued_machine: str | None

Machine:
    name
    busy_until: int
    busy_time: int
    queue: list[job_id]    # READY jobs, giữ thứ tự vào
```

### 2.2 Sự kiện

Hai loại mốc thời gian: `arrival` và `busy_until`. Không cần priority queue phức tạp; mỗi vòng tìm `min` trên các mốc còn hiệu lực (với ≤ 200 job là đủ nhanh).

## 3. Thứ tự cài đặt

### Bước 1 — Bảng chuyển

Viết `transition(job, new_status, now)` là **cửa duy nhất** đổi trạng thái:

```text
ALLOWED = {
  (ARRIVED, WAITING), (WAITING, READY), (READY, PROCESSING),
  (PROCESSING, WAITING), (PROCESSING, FINISHED),
}
nếu (job.status, new) không trong ALLOWED: raise IllegalTransition
job.status = new; ghi event
```

Nếu bạn gán `job.status = ...` ở chỗ khác, bảng chuyển thành vô nghĩa. Grep lại sau khi viết xong.

### Bước 2 — Vòng sự kiện ba pha

```text
while chưa xong:
    now = mốc kế tiếp
    # pha 1
    for job in jobs_sorted_by_id:
        if job.status == PROCESSING and machine_busy_until[job] == now:
            finish op
    # pha 2
    for job in jobs_sorted_by_id:
        if job.status == ARRIVED and job.arrival == now:
            transition WAITING; maybe transition READY
    # pha 3
    for machine in machines_sorted:
        if machine rảnh and queue không rỗng:
            chọn theo rule; transition PROCESSING
```

Điểm khó: ở pha 1, job chuyển `PROCESSING → WAITING` rồi **ngay** `WAITING → READY` (cùng mốc, cùng job). Nếu bạn gộp hai bước, bảng chuyển mất một dòng log và test 8.7 sẽ bắt.

### Bước 3 — Chọn job

Hàm `select(machine, now, ctx) -> job_id`:

- Duyệt queue, tính khóa theo luật.
- Tie-break `job_id`.
- **Không** sắp lại queue vĩnh viễn theo luật — queue giữ thứ tự vào để bạn còn thấy lịch sử. Sắp tại chỗ khi chọn.

### Bước 4 — Terminal context

Cài `TerminalContext(job, machine, now, stats)` với sáu thuộc tính. Hàm chọn nhận `(job, ctx)` — `weight` nằm trên `job`, không phải terminal. Ba luật:

```text
SPT:   key = ctx.JNPT
SLACK: key = ctx.JS
WSPT:  key = -job.weight / ctx.JNPT
```

Nếu `JNPT` bằng 0 hoặc job không còn công đoạn, không được gọi (job đã FINISHED thì không trong queue). Vẫn nên có assert.

### Bước 5 — Metric

Tính **sau** khi mô phỏng xong, từ `finish_time` đã ghi. Đừng cộng dồn trong lúc chạy — dễ đếm hai lần khi job chuyển trạng thái nhiều lần.

`makespan = max(finish) - min(arrival)`, không phải `max(finish)`. Với fixture có `arrival` đầu > 0, hai công thức khác nhau.

### Bước 6 — Generator

Sinh job **trước**, đóng băng thành list, rồi mô phỏng. `arrival` phải không giảm; `gauss` có thể âm nên phải `max(1, ...)`.

Thứ tự tiêu thụ PRNG: theo job, trong mỗi job theo thứ tự (gap → số công đoạn → từng công đoạn: máy, duration). Ghi rõ thứ tự này trong docstring, nếu không hai cài đặt "cùng seed" sẽ khác nhau.

## 4. Cạm bẫy

- **Trùng thời điểm không có luật**: kết quả phụ thuộc thứ tự dict. Luôn sắp theo `(now, phase, id)`.
- **`remaining` chỉ tính công đoạn kế**: quên các công đoạn sau làm slack sai hoàn toàn.
- **Slack âm**: phải `max(0, …)`; nếu không luật SLACK ưu tiên job quá hạn theo cách khó đoán.
- **`makespan` trừ nhầm `min(arrival)`**: với fixture bắt đầu ở 0 thì không thấy, với fixture bắt đầu ở 5 thì lệch.
- **Utilization chia cho `max(finish)` thay vì `makespan`**: sai khi arrival đầu > 0.
- **Gộp WAITING→READY**: mất một dòng event, và khó debug vì trạng thái "nhảy".
- **Sắp queue vĩnh viễn**: làm mất thông tin FIFO; một số luật cần thứ tự vào để tie-break.
- **Deadlock không bắt**: nếu một job chờ máy mà không có sự kiện tương lai, vòng lặp treo. Luôn có nhánh `Deadlock`.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `toy_spt` | 7: makespan 7, flow 4.333333, util chính xác |
| `toy_slack` | 7.1: makespan 6 |
| `toy_wspt` | 7.1: makespan 6 |
| `illegal` | chuyển `ARRIVED → PROCESSING` ⇒ `IllegalTransition` |
| `phase_order` | fixture hoàn thành/phát hành cùng mốc: event hoàn thành đứng trước |
| `metrics` | `tight_deadlines` cho `mean_tardiness > 0` |
| `generator_repro` | cùng seed ⇒ cùng list; khác seed ⇒ khác |
| `generator_bounds` | gap trong miền; burst chỉ hai giá trị |
| `all_finished` | mọi job FINISHED; không job PROCESSING |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src run --fixture fixtures/toy_shop.json | python -m json.tool
python -m src run --fixture fixtures/toy_shop.json --rule SLACK | python -c "import json,sys; print(json.load(sys.stdin)['metrics']['makespan'])"
```

Hai lệnh cuối phải in `7` và `6`. Kiểm tra sinh tất định:

```bash
python -m src generate --fixture fixtures/gen_burst.json --seed 99 > a.json
python -m src generate --fixture fixtures/gen_burst.json --seed 99 > b.json
python -c "print(open('a.json').read()==open('b.json').read())"
```

Lưu ý: `--seed` phải ghi đè `seed` trong fixture; nếu bạn chỉ đọc từ fixture thì lệnh trên vô nghĩa.

## 7. Gợi ý

- Viết `assert_invariants(job)` gọi sau mỗi chuyển: `READY` ⇒ có `enqueued_machine`; `PROCESSING` ⇒ `busy_until > now`; `FINISHED` ⇒ `op_index == len(operations)`. Ba dòng này bắt lỗi sớm hơn metric.
- In trace dạng bảng `now | job | from→to | machine` để so bằng mắt với SPEC 7.
- Cài rule như hàm nhận `(job, ctx)` để test riêng không cần mô phỏng.
- Với generator, log danh sách gap ra để so với miền cho phép.

## 8. Mở rộng

- **DSL terminal**: thay ba hàm bằng biểu thức `(JS + JNPT) / 2`, cài parser nhỏ; so kết quả với luật cứng.
- **Máy hỏng**: thêm sự kiện `breakdown(machine, start, duration)`; job đang chạy chuyển về READY (preemption) hoặc tiếp tục sau (resume) — chọn và test.
- **Bộ đệm giới hạn**: nếu queue đầy, job ở WAITING và tính blocking time; đo tác động lên makespan.
- **So sánh luật**: chạy 20 instance với 3 luật, xuất bảng `makespan` trung bình; thấy luật nào ổn định hơn.
- **Đa mục tiêu**: trả `(makespan, mean_tardiness)` và tìm front Pareto trên các instance (nối sang bài 19 của lộ trình).
