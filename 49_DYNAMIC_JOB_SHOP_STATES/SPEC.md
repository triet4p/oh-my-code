# SPEC 49 — Trạng thái lịch trình job-shop động

## 1. Mô hình

### 1.1 Fixture

```json
{
  "machines": ["M1", "M2"],
  "rule": "SPT",
  "jobs": [
    {"id": "J1", "arrival": 0, "deadline": 10, "weight": 1,
     "operations": [{"machine": "M1", "duration": 3}, {"machine": "M2", "duration": 2}]},
    {"id": "J2", "arrival": 1, "deadline": 8, "weight": 5,
     "operations": [{"machine": "M1", "duration": 2}]},
    {"id": "J3", "arrival": 2, "deadline": 20, "weight": 1,
     "operations": [{"machine": "M1", "duration": 1}]}
  ]
}
```

| Trường | Ràng buộc |
|---|---|
| `machines` | danh sách không rỗng, tên duy nhất |
| `jobs[].id` | duy nhất, không rỗng |
| `jobs[].arrival` | số nguyên `>= 0`, không giảm theo thứ tự khai báo |
| `jobs[].deadline` | số nguyên `>= arrival` |
| `jobs[].weight` | số nguyên `>= 1` |
| `jobs[].operations` | không rỗng; `machine` thuộc `machines`; `duration` nguyên `>= 1` |
| `rule` | `SPT`, `SLACK`, `WSPT` |

### 1.2 Trạng thái

| Trạng thái | Nghĩa |
|---|---|
| `ARRIVED` | Đã biết job nhưng chưa tới thời điểm phát hành |
| `WAITING` | Đã phát hành, đang chờ công đoạn trước hoàn tất |
| `READY` | Đang nằm trong hàng đợi của một máy |
| `PROCESSING` | Máy đang gia công |
| `FINISHED` | Hoàn tất mọi công đoạn |

### 1.3 Bảng chuyển hợp lệ

| Từ | Đến | Khi nào |
|---|---|---|
| `ARRIVED` | `WAITING` | Khi `now == arrival` |
| `WAITING` | `READY` | Khi không còn công đoạn trước; job vào hàng đợi của máy của công đoạn kế |
| `READY` | `PROCESSING` | Khi máy rảnh và chọn job này |
| `PROCESSING` | `WAITING` | Khi xong một công đoạn và còn công đoạn sau |
| `PROCESSING` | `FINISHED` | Khi xong công đoạn cuối |

Mọi chuyển khác ⇒ `IllegalTransition(job_id, from, to)` và dừng mô phỏng với mã thoát `2`.

## 2. Vòng sự kiện

### 2.1 Thứ tự khi trùng thời điểm

Tại mỗi mốc thời gian, xử lý theo ba pha **cố định**:

1. **Hoàn thành** — theo `job_id` tăng dần.
2. **Phát hành** — job có `arrival == now`, theo `job_id` tăng dần.
3. **Điều phối** — máy rảnh, theo tên máy tăng dần; mỗi máy chọn đúng một job.

Sau pha 3, nếu có máy vừa nhận job với `duration = 0` (không được phép bởi validate, nhưng để chắc), không lặp vô hạn vì `duration >= 1`.

### 2.2 Vòng lặp

```text
now = 0; gán mọi job ARRIVED
while còn job chưa FINISHED:
    nếu không còn sự kiện nào trong tương lai: lỗi Deadlock
    now = mốc kế tiếp (min của: arrival chưa phát hành, thời điểm kết thúc đang chạy)
    pha 1: job PROCESSING có end == now -> chuyển (WAITING hoặc FINISHED), ghi metric
    pha 2: job ARRIVED có arrival == now -> WAITING -> READY (nếu không có công đoạn trước)
    pha 3: với mỗi máy rảnh, chọn từ READY của máy đó theo luật, chuyển PROCESSING, đặt end = now + duration
```

`WAITING → READY` được phép xảy ra **ngay trong cùng mốc** (job vừa xong công đoạn trước). Hai chuyển này ghi hai dòng nhật ký riêng.

## 3. Slack và luật điều phối

### 3.1 Slack

```text
remaining(job) = duration của công đoạn kế + tổng duration các công đoạn sau nó
slack(job, now) = max(0, deadline - now - remaining(job))
```

`remaining` tính cả công đoạn kế (chưa bắt đầu). Với job `FINISHED`, `remaining = 0`.

### 3.2 Ba luật

| Luật | Khóa chọn (nhỏ hơn thắng) | Tie-break |
|---|---|---|
| `SPT` | `JNPT` = duration công đoạn kế | `job_id` tăng |
| `SLACK` | `JS` = slack tại `now` | `job_id` tăng |
| `WSPT` | `-weight / JNPT` (tức `weight/JNPT` lớn hơn thắng) | `job_id` tăng |

### 3.3 Terminal

Cài một `TerminalContext` với sáu terminal tối giản, đúng tên trong nguồn:

| Terminal | Giá trị |
|---|---|
| `TNOW` | thời điểm mô phỏng hiện tại |
| `JNPT` | duration công đoạn kế của job đang xét |
| `JD` | deadline của job |
| `JS` | slack của job tại `TNOW` |
| `MUTIL` | `busy_time(machine) / max(TNOW, 1)` của máy đang xét |
| `AVGWT` | thời gian chờ trung bình của các job đã `FINISHED` (0 nếu chưa có) |

Ba luật ở 3.2 phải được viết **dựa trên** context này (không truy cập trực tiếp thuộc tính job trong hàm chọn), để sau này thay luật bằng biểu thức terminal là việc nhỏ.

## 4. Metric

| Metric | Công thức |
|---|---|
| `makespan` | `max(finish) - min(arrival)` |
| `mean_flow_time` | trung bình `finish - arrival` |
| `mean_tardiness` | trung bình `max(0, finish - deadline)` |
| `max_tardiness` | `max(0, finish - deadline)` lớn nhất |
| `utilization[m]` | `busy_time(m) / makespan` |
| `completed` | số job `FINISHED` |

`busy_time` cộng dồn duration các công đoạn đã chạy trên máy. Utilization làm tròn 6 chữ số khi in.

## 5. Đầu ra

```json
{
  "events": [
    {"job": "J1", "now": 0, "to": "WAITING"},
    {"job": "J1", "now": 0, "to": "READY"},
    {"job": "J1", "now": 0, "to": "PROCESSING", "machine": "M1"}
  ],
  "metrics": {
    "completed": 3,
    "makespan": 7,
    "max_tardiness": 0,
    "mean_flow_time": 4.333333,
    "mean_tardiness": 0.0,
    "utilization": {"M1": 0.857143, "M2": 0.285714}
  },
  "rule": "SPT"
}
```

`events` theo thứ tự phát sinh; cùng `now` thì theo pha rồi `job_id`.

## 6. Sinh instance

```json
{
  "generate": {
    "n_jobs": 20,
    "machines": ["M1", "M2", "M3"],
    "arrival_type": "burst",
    "seed": 99,
    "uniform": {"min_gap": 0, "max_gap": 4},
    "gauss": {"mean": 3.0, "sd": 1.5},
    "burst": {"p": 0.4, "burst_gap": 1, "base_gap": 5},
    "proc_dist": {"kind": "uniform", "lo": 1, "hi": 4},
    "deadline_factor": 2.0,
    "max_operations": 3
  }
}
```

Quy tắc (tất cả dùng LCG 32-bit với `seed`, tiêu thụ theo thứ tự sinh job):

- `uniform`: `gap = min_gap + floor(next_u() * (max_gap - min_gap + 1))`; job đầu có `arrival = 0`.
- `gauss`: `z = (Σ_{i=1..12} next_u()) - 6`; `gap = max(1, round(mean + sd * z))`.
- `burst`: `gap = burst_gap` nếu `next_u() < p`, ngược lại `base_gap`.
- `proc_dist.kind = "uniform"`: `lo + floor(next_u() * (hi - lo + 1))`; `"fixed"`: `lo`.
- `deadline = arrival + max(1, round(deadline_factor * total_proc))`.
- Số công đoạn mỗi job = `1 + floor(next_u() * max_operations)`, cắt theo `max_operations`.
- Máy mỗi công đoạn chọn bằng `pick(len(machines))` trên danh sách máy; hai công đoạn liên tiếp có thể cùng máy.

## 7. Ví dụ cụ thể

Với fixture 1.1 và `rule = "SPT"`:

| Mốc | Việc xảy ra | Kết quả |
|---|---|---|
| 0 | `J1` phát hành → READY → M1 rảnh, nhận `J1` | M1 bận `0..3` |
| 1 | `J2` phát hành → READY hàng đợi M1 | chờ |
| 2 | `J3` phát hành → READY hàng đợi M1 | chờ |
| 3 | `J1` xong công đoạn 1; còn công đoạn M2 → M2 rảnh, nhận `J1` (`3..5`). M1 rảnh, chọn giữa `J2` (2) và `J3` (1): SPT chọn `J3` | M1 `3..4` |
| 4 | `J3` xong công đoạn cuối → FINISHED | — |
| 5 | `J1` FINISHED; M1 rảnh nhận `J2` | M1 `5..7` |
| 7 | `J2` FINISHED | hết |

Metric của lượt `SPT`:

- `makespan = 7`, `completed = 3`
- `mean_flow_time = (5 + 6 + 2) / 3 = 4.333333`
- `mean_tardiness = 0`, `max_tardiness = 0`
- `utilization = {"M1": 6/7 = 0.857143, "M2": 2/7 = 0.285714}`

### 7.1 Cùng fixture, luật khác, kết quả khác

`rule = "SLACK"`:

- Tại mốc 3: `JS(J2) = max(0, 8 - 3 - 2) = 3`; `JS(J3) = max(0, 20 - 3 - 1) = 16` ⇒ chọn `J2`.
- `J2` chạy `3..5`; `J3` chạy `5..6`.
- `makespan = 6`; `mean_flow_time = (5 + 4 + 4) / 3 = 4.333333`; `utilization = {"M1": 1.0, "M2": 0.333333}`.

`WSPT` cũng chọn `J2` (`5/2 = 2.5` so với `1/1 = 1.0`) nên cho cùng kết quả với `SLACK`.

Bài học: SPT **không** luôn tốt hơn; ở đây nó làm makespan xấu đi một đơn vị.

## 8. Tiêu chí chấp nhận

1. Ví dụ 7 cho đúng `makespan`, `mean_flow_time`, `utilization` (dung sai `1e-6`).
2. 7.1 cho `makespan = 6` với `SLACK` và `WSPT`.
3. Mọi sự kiện trong `events` tuân bảng chuyển 1.3; test dựng một chuyển sai và khẳng định `IllegalTransition`.
4. Không job nào ở `PROCESSING` khi kết thúc; `completed == len(jobs)`.
5. `mean_tardiness >= 0`; với `fixtures/tight_deadlines.json` phải `> 0`.
6. Sinh instance: cùng seed ⇒ cùng danh sách job; `gap` của `uniform` nằm trong `[min_gap, max_gap]`; `gap` của `burst` chỉ nhận `burst_gap` hoặc `base_gap`; mọi `gap >= 1` với `gauss`; `deadline` khớp công thức.
7. Thứ tự pha: fixture có job hoàn thành đúng lúc job khác phát hành phải cho `events` theo pha 1 trước pha 2.
8. `python -m src run --fixture fixtures/toy_shop.json` in JSON hợp lệ, mã thoát `0`.

## 9. Non-goals

- Không tối ưu lịch trình; không GA/MILP/LLM.
- Không máy hỏng, bảo trì, preemption, thời gian chuyển máy.
- Không 18 terminal đầy đủ và không parser biểu thức.
- Không thời gian thực; không đo bằng đồng hồ hệ thống.
