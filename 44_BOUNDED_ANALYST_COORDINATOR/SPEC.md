# SPEC 44 — Coordinator có ngân sách analyst

## 1. Mô hình thế giới

### 1.1 Fixture

```json
{
  "episode_seed": 7,
  "day": 3,
  "world": {
    "resources": {"oven": {"capacity": 10}, "fryer": {"capacity": 6}},
    "assignments": []
  },
  "requests": [
    {"id": "r1", "kind": "bake", "amount": 6},
    {"id": "r2", "kind": "bake", "amount": 6},
    {"id": "r3", "kind": "fry", "amount": 4}
  ],
  "kind_to_resource": {"bake": "oven", "fry": "fryer"},
  "analyst_script": [
    {"r1": 6, "r2": 6, "r3": 4},
    {"r1": 4, "r2": 6, "r3": 4}
  ]
}
```

| Khóa | Kiểu | Ý nghĩa |
|---|---|---|
| `episode_seed` | int | Phải khớp tham số truyền vào `coordinate` |
| `day` | int `>= 0` | Phải khớp tham số `day` |
| `world.resources` | object `tên -> {capacity: int}` | `capacity >= 0` |
| `world.assignments` | list | Trạng thái ban đầu, thường rỗng |
| `requests` | list `{id, kind, amount}` | `amount >= 0`; `id` duy nhất |
| `kind_to_resource` | object | Mọi `kind` trong requests phải có mặt |
| `analyst_script` | list object `id -> amount` | Tùy chọn; nếu thiếu, dùng analyst mặc định |

### 1.2 Luật khả thi

Một đề xuất `plan: dict[request_id, amount]` là **khả thi** khi và chỉ khi:

1. Mọi `request.id` xuất hiện đúng một lần trong `plan` (không thiếu, không thừa).
2. Với mỗi yêu cầu, `plan[id] == requests[id].amount` — bài này không cho phép phục vụ một phần. (Quyết định `[DESIGN]`; ghi rõ nếu bạn muốn mở rộng.)
3. Tổng khối lượng theo từng tài nguyên không vượt `capacity`:

```text
sum(plan[id] for id where kind_to_resource[kind] == res) <= resources[res].capacity
```

Đề xuất không khả thi phải trả **lý do** dạng chuỗi ổn định, ví dụ:

- `"missing_request:r2"`
- `"unknown_request:r9"`
- `"amount_mismatch:r1:expected=6:got=4"`
- `"capacity_exceeded:oven:used=12:capacity=10"`

Lý do được ghi vào `trace` và làm đầu vào cho lần sửa tiếp theo.

## 2. `ActionExecutor` trên bản sao

`execute(world, plan)` nhận một **bản sao sâu** và trả `Feasibility(ok: bool, reasons: list[str], world_after)`.

Yêu cầu:

- Không được đọc/ghi thế giới gốc dưới bất kỳ hình thức nào (không alias list/dict).
- Với mỗi yêu cầu hợp lệ, trừ `amount` khỏi `capacity` của tài nguyên tương ứng và thêm một bản ghi vào `assignments`.
- Khi phát hiện vi phạm, vẫn trả `reasons` đầy đủ (có thể nhiều lý do), không dừng ở lý do đầu.

## 3. `Analyst`

```text
propose(requests, world_view, feedback: list[str] | None) -> dict[str, int] | None
```

- `world_view` là **bản sao chỉ đọc** (bạn có thể truyền bản sao sâu; analyst không được giữ tham chiếu).
- `feedback` là `reasons` của lần trước, `None` ở lần đầu.
- Trả `None` nghĩa là **bỏ qua lượt** (abstain): tăng `analyst_calls`, **không** tăng `revision_count`, ghi trace `kind="abstain"`. Đây là đường để ngân sách 6 lần gọi thực sự quan sát được.
- `ScriptedAnalyst` trả phần tử thứ `k` của `analyst_script` ở lần gọi thứ `k`; nếu hết script, lặp lại phần tử cuối. Phần tử `null` trong script nghĩa là abstain.
- `DefaultAnalyst` (khi không có script): gán đủ `amount` cho mọi yêu cầu, không quan tâm sức chứa — cố ý để tạo tình huống vượt.

## 4. Vòng lặp và ngân sách

```text
analyst_calls = 0
revision_count = 0
trace = []
while True:
    nếu analyst_calls >= 6:  -> bounded_stop
    plan = analyst.propose(...)          # analyst_calls += 1
    nếu plan is None:
        ghi trace "abstain"
        nếu analyst_calls >= 6: -> bounded_stop
        continue
    feas = execute(deepcopy(world), plan)
    nếu feas.ok:
        -> decided
    nếu revision_count >= 2:  -> bounded_stop
    revision_count += 1
    feedback = feas.reasons
```

Điểm mấu chốt: **kiểm tra ngân sách trước khi gọi**. Với script luôn sai, kết quả là `analyst_calls = 3`, `revision_count = 2`, `outcome = "bounded_stop"` — không phải 4 và 3.

`MAX_ANALYST_CALLS = 6`, `MAX_REVISIONS = 2` là hằng của module, không phải tham số fixture (người dùng không được nới ngân sách bằng dữ liệu).

## 5. `CoordinationResult`

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `episode_seed` | int | Bằng tham số |
| `day` | int | Bằng tham số |
| `requests` | list | Giữ nguyên thứ tự fixture |
| `recommendations` | list | Các đề xuất **đã thử**, cùng thứ tự |
| `decision` | object hoặc `null` | `null` khi `bounded_stop` |
| `outcome` | `"decided"` hoặc `"bounded_stop"` | Chỉ hai giá trị |
| `analyst_calls` | int | `0..6` |
| `revision_count` | int | `0..2` |
| `trace` | list `TraceEntry` | Xem 5.1 |

`TraceEntry`:

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `step` | int | Bắt đầu từ `0`, tăng dần |
| `kind` | `"propose"` / `"feasibility"` / `"abstain"` / `"revise"` / `"decide"` / `"stop"` | Loại sự kiện |
| `detail` | str | `"ok"`, hoặc lý do nối bằng `";"` |

**Từ chối trường lạ**: khi dựng `CoordinationResult` từ dict (fixture `expected_result` trong test), mọi khóa không thuộc danh sách trên ⇒ `ExtraFieldForbidden(key)`. Đây là mô phỏng `extra="forbid"`.

## 6. Kiểm tra hợp lệ

| Điều kiện | Ngoại lệ |
|---|---|
| `episode_seed` tham số khác fixture | `EpisodeMismatch` |
| `day` tham số khác fixture | `DayMismatch` |
| `requests` rỗng | `EmptyRequests` |
| `id` trùng trong requests | `DuplicateRequestId` |
| `kind` không có trong `kind_to_resource` | `UnknownKind` |
| `amount < 0` hoặc không hữu hạn | `InvalidAmount` |
| `capacity < 0` | `InvalidCapacity` |
| analyst trả `id` lạ | `UnknownRequest` (ghi vào reasons, **không** ném) |
| analyst trả thiếu `id` | ghi `missing_request:<id>` vào reasons |

Lưu ý: analyst sai **không** phải ngoại lệ — đó là dữ liệu để vòng lặp sửa. Chỉ fixture hỏng mới ném.

## 7. Ví dụ cụ thể

### 7.1 Sửa một lần rồi quyết

Fixture 1.1 với `analyst_script = [{"r1":6,"r2":6,"r3":4}, {"r1":4,"r2":6,"r3":4}]`:

| Bước | kind | detail |
|---|---|---|
| 0 | propose | `""` |
| 1 | feasibility | `capacity_exceeded:oven:used=12:capacity=10` |
| 2 | revise | `1` |
| 3 | propose | `""` |
| 4 | feasibility | `ok` |
| 5 | decide | `ok` |

Kết quả: `outcome = "decided"`, `analyst_calls = 2`, `revision_count = 1`, `decision = {"r1":4,"r2":6,"r3":4}`.

### 7.2 Luôn không khả thi

`analyst_script = [{"r1":10,"r2":10,"r3":4}]`:

- Lần 1: `capacity_exceeded:oven:used=20:capacity=10` ⇒ revise (1)
- Lần 2: cùng đề xuất ⇒ revise (2)
- Lần 3: cùng đề xuất, `revision_count == 2` ⇒ `bounded_stop`

Kết quả: `analyst_calls = 3`, `revision_count = 2`, `decision = null`, `outcome = "bounded_stop"`.

### 7.3 Thiếu yêu cầu

`script = [{"r1":6,"r3":4}]` ⇒ reasons chứa `missing_request:r2`; nếu lần sau bổ sung đủ thì `decided`.

### 7.4 Cô lập thế giới

Sau khi chạy 7.1 và 7.2 trên cùng fixture **không** tái nạp, `fixture["world"]` phải giống hệt ban đầu: `resources.oven.capacity == 10` và `assignments == []`.

### 7.5 Cạn ngân sách gọi analyst

`analyst_script = [null, null, null, null, null, null]`:

- Sáu lượt `abstain`, `analyst_calls = 6`, `revision_count = 0`.
- `trace` có 7 mục: sáu `abstain` (step 0..5) và một `stop` (step 6).
- `outcome = "bounded_stop"`, `decision = null`.
- `recommendations = [null, null, null, null, null, null]`.

Đây là khác biệt quan trọng với 7.2: hết ngân sách **gọi** không giống hết ngân sách **sửa**. Test phải phân biệt hai đường.

## 8. Tiêu chí chấp nhận quan sát được

1. Ví dụ 7.1 và 7.2 cho đúng `trace`, hai bộ đếm và `outcome`.
2. Bất biến: `analyst_calls <= 6`, `revision_count <= 2` với mọi fixture — kể cả script dài 100 phần tử.
3. `execute` không làm đổi thế giới gốc (so sánh `json.dumps(sort_keys=True)` trước/sau).
4. `decision` khác `null` **chỉ khi** `outcome == "decided"` và đề xuất cuối khả thi.
5. `CoordinationResult` từ chối khóa lạ, chấp nhận đúng 9 khóa.
6. Fixture sai `episode_seed`/`day` ⇒ đúng ngoại lệ, không gọi analyst lần nào.
7. Hai lần chạy cho cùng output (không có trạng thái ẩn).
8. `threading.active_count()` không tăng sau `coordinate` (mô phỏng "no parallel calls").

## 9. Non-goals

- Không tối ưu hóa việc phân bổ (không phải solver).
- Không gọi LLM, không memory, không I/O mạng.
- Không lưu episode giữa các lần chạy.
