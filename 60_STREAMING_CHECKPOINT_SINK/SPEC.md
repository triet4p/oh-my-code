# SPEC 60 — Ghi streaming có commit manifest và checkpoint

## 1. Lược đồ, layout, cấu hình

### 1.1 Topic

`topic.jsonl`, mỗi dòng một object, offset = số dòng (0-based, tính cả dòng hỏng):

```jsonl
{"event_time": 1700000000, "user_id": "u1", "action": "view", "value": null}
{"event_time": 1700000060, "user_id": "u2", "action": "buy", "value": 9.5}
```

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `event_time` | int | `>= 0`; giây Unix UTC |
| `user_id` | string | không rỗng |
| `action` | string | thuộc `{view, click, buy}` |
| `value` | number hoặc null | nếu `action == "buy"` thì phải là number `>= 0` |

Dòng không parse được JSON, thiếu trường, sai kiểu, hoặc `action` lạ ⇒ **dead-letter**, không làm sập pipeline.

### 1.2 Layout đích

```text
out/
├── data/date=2023-11-14/part-0.jsonl
├── data/date=2023-11-14/part-1.jsonl
├── data/date=2023-11-15/part-2-1.jsonl
├── dead/part-1.jsonl
├── _commits/batch-0.json
├── _commits/batch-1.json
├── _tmp/…
└── checkpoint.json
```

Quy ước tên:

- Batch sinh **một** ngày ⇒ `data/date=<D>/part-<b>.jsonl`.
- Batch sinh **nhiều** ngày ⇒ `data/date=<D>/part-<b>-<seq>.jsonl`, `seq` tăng theo ngày tăng dần.
- Dead-letter của batch (nếu có) ⇒ `dead/part-<b>.jsonl` — **một file mỗi batch**, dòng sắp theo offset.
- Commit manifest ⇒ `_commits/batch-<b>.json`.

### 1.3 Config

```json
{
  "topic": "fixtures/topic_basic.jsonl",
  "output_dir": "out/data",
  "dead_dir": "out/dead",
  "commit_dir": "out/_commits",
  "checkpoint": "out/checkpoint.json",
  "batch_size": 2,
  "starting_offsets": "earliest",
  "fail_on_data_loss": true,
  "schema_version": "v1"
}
```

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `batch_size` | bắt buộc | `1..500` |
| `starting_offsets` | `"earliest"` | Chỉ áp dụng khi **chưa có** checkpoint |
| `fail_on_data_loss` | `true` | Checkpoint trỏ quá cuối topic thì lỗi hay tiếp tục |
| `schema_version` | `"v1"` | Khác với checkpoint ⇒ `SchemaMismatch` |

`dead_dir` và `commit_dir` mặc định là `dead` và `_commits` cạnh `output_dir`.

## 2. Checkpoint và commit manifest

### 2.1 Checkpoint

```json
{
  "schema_version": "v1",
  "next_offset": 4,
  "batch_id": 2,
  "data_loss": false
}
```

- `next_offset`: offset kế tiếp chưa xử lý.
- `batch_id`: số batch đã **commit** (0-based, tăng 1 mỗi batch, kể cả batch chỉ có dòng hỏng).
- Không có checkpoint ⇒ `next_offset = 0` nếu `earliest`, `= len(topic)` nếu `latest`; `batch_id = 0`.

### 2.2 Commit manifest

```json
{
  "batch_id": 1,
  "next_offset": 4,
  "files": [
    {"path": "date=2023-11-14/part-1.jsonl", "rows": 2}
  ],
  "dead": [
    {"path": "part-1.jsonl", "rows": 0}
  ]
}
```

- `path` của `files` tương đối so với `output_dir`; `path` của `dead` tương đối so với `dead_dir`.
- Danh sách rỗng hợp lệ (batch không có dòng hợp lệ / không có dòng hỏng).
- Manifest được ghi **sau** khi mọi part đã nằm đúng chỗ, bằng `tmp` + `os.replace`.

Manifest là **nguồn sự thật duy nhất**: một part tồn tại mà không có manifest nghĩa là batch **chưa** commit.

## 3. Xử lý một batch

```text
rows = dòng [next_offset, min(next_offset + batch_size, len(topic)))
valid, dead = phân loại từng dòng theo lược đồ
b = batch_id

nếu _commits/batch-<b>.json tồn tại:          # đã commit, checkpoint chưa tiến
    bỏ qua publish; next_offset += len(rows); batch_id += 1; ghi checkpoint
    (rows_written += 0)

ngược lại:
    1. DỌN: xoá mọi file khớp
         output_dir/date=*/part-<b>.jsonl
         output_dir/date=*/part-<b>-*.jsonl
         dead_dir/part-<b>.jsonl
       (an toàn vì chưa có manifest cho batch này)
    2. GHI TẠM: mỗi nhóm ngày một file `_tmp/part-<b>-<seq>.jsonl`;
       dead (nếu có) `_tmp/dead-<b>.jsonl`; đóng file trước khi chuyển.
    3. ĐẶT VÀO CHỖ: os.replace từng file tạm sang đích đã định.
       Đây KHÔNG phải thao tác nguyên tử cho cả batch — chính vì vậy cần bước 4.
    4. COMMIT: ghi `_commits/batch-<b>.json` (tmp + os.replace) liệt kê
       đúng các file đã đặt và số dòng.
    5. CHECKPOINT: next_offset += len(rows); batch_id += 1; ghi nguyên tử.
```

Ràng buộc:

- Không bao giờ ghi manifest trước khi mọi part nằm đúng chỗ.
- Không bao giờ coi batch đã xong chỉ vì **một** part tồn tại.
- File data ghi bằng `"w"` (không append) và luôn qua `_tmp` + `os.replace`.

## 4. Bảng resume

| Trạng thái khi khởi động | Hành động |
|---|---|
| Không manifest, không part | Publish bình thường |
| Có **một phần** part, **không** manifest | Dọn part của batch đó, publish lại; nội dung tất định nên kết quả giống hệt |
| Có **đủ** part, **không** manifest | Như trên: dọn và publish lại (không tin part) |
| Có manifest, checkpoint chưa tiến | Không publish lại; chỉ tiến checkpoint; `rows_written` của batch = 0 |
| Có manifest, checkpoint đã tiến | Không làm gì với batch đó |

`rows_written` trong báo cáo chỉ đếm dòng **đã ghi thật** trong lần chạy hiện tại.

## 5. Dead-letter

- Mỗi dòng hỏng ghi `{"offset": <int>, "reason": "<mã>", "raw": "<dòng gốc>"}`.
- Mã lý do: `invalid_json`, `missing_field:<tên>`, `invalid_type:<tên>`, `invalid_action:<giá trị>`, `invalid_value_buy`.
- Dead-letter của batch nằm trong `dead/part-<b>.jsonl`, dòng sắp theo offset tăng.
- Vì dead-letter được **dọn và ghi lại cùng batch** trước manifest, crash trước manifest không thể sinh bản ghi trùng; mỗi offset hỏng xuất hiện đúng **một lần** trong toàn bộ `dead/` sau bao nhiêu lần resume cũng vậy.
- Batch không có dòng hỏng ⇒ không tạo file, `dead: []` trong manifest.

## 6. `fail_on_data_loss` và `starting_offsets`

- `next_offset > len(topic)`:
  - `fail_on_data_loss = true` ⇒ `DataLossDetected(next_offset, len(topic))`.
  - `false` ⇒ `next_offset = len(topic)`, `data_loss = true` ghi vào checkpoint, tiếp tục.
- `next_offset < 0` ⇒ `CorruptCheckpoint`.
- Chưa có checkpoint + `latest` ⇒ bắt đầu ở `len(topic)`, không publish gì, ghi checkpoint `next_offset = len(topic)`, `batch_id = 0`.
- Nếu lần chạy không xử lý batch nào (ví dụ `latest` với topic đã cạn, hoặc chạy lại ngay), **vẫn ghi checkpoint** ở trạng thái hiện tại; nếu không, lần chạy sau sẽ lại bắt đầu từ `latest` và hành vi không quan sát được.

## 7. Đầu ra báo cáo

```json
{
  "batches": 3,
  "data_loss": false,
  "dead_letters": 0,
  "files": [
    "date=2023-11-14/part-0.jsonl",
    "date=2023-11-14/part-1.jsonl",
    "date=2023-11-14/part-2.jsonl"
  ],
  "next_offset": 5,
  "rows_written": 5,
  "skipped_committed": 0
}
```

- `files` chỉ gồm file **đã đặt vào chỗ trong lần chạy này**, sắp theo `(batch_id, seq)`.
- `skipped_committed`: số batch bỏ publish vì manifest đã có.
- `rows_written`: tổng dòng hợp lệ trong các file vừa ghi.

## 8. Ví dụ cụ thể

### 8.1 Chạy sạch

`topic_basic.jsonl` 5 dòng hợp lệ, cùng ngày `2023-11-14` (`event_time = 1700000000` ⇒ `2023-11-14T22:13:20Z`), `batch_size = 2`.

| Batch | Offset | File | Dòng |
|---|---|---|---|
| 0 | 0–1 | `date=2023-11-14/part-0.jsonl` | 2 |
| 1 | 2–3 | `date=2023-11-14/part-1.jsonl` | 2 |
| 2 | 4 | `date=2023-11-14/part-2.jsonl` | 1 |

Báo cáo: `batches = 3`, `rows_written = 5`, `next_offset = 5`.
Checkpoint: `next_offset = 5`, `batch_id = 3`.
Có ba manifest `_commits/batch-0.json` … `batch-2.json`.

### 8.2 Chạy lại ngay

Không có dòng mới ⇒ `batches = 0`, `rows_written = 0`, `files = []`, `skipped_committed = 0`; checkpoint không đổi.

### 8.3 Crash **trước** manifest (sau khi đã đặt part)

Hook `after_parts_moved` ném `RuntimeError` ở batch 1 (batch 0 đã commit):

- Lần chạy 1: `part-0.jsonl` + `batch-0.json` tồn tại; `part-1.jsonl` có thể tồn tại nhưng **không có** `batch-1.json`; checkpoint `next_offset = 2` (sau batch 0).
- Lần chạy 2: batch 1 không có manifest ⇒ dọn `part-1*`, publish lại, ghi `batch-1.json`; tiếp tục batch 2.
- Tổng dòng trong `data/` = **5** (không phải 7). `rows_written` lần 2 = 3 (batch 1 và 2).

### 8.4 Crash **sau** manifest, **trước** checkpoint

Hook `before_checkpoint` ném ở batch 1:

- Lần chạy 1: `batch-1.json` tồn tại, checkpoint vẫn `next_offset = 2`.
- Lần chạy 2: thấy manifest ⇒ **không** publish lại; `skipped_committed = 1`; `rows_written` chỉ tính batch 2 = 1.
- Tổng dòng trong `data/` = 5; không file nào bị ghi hai lần.

### 8.5 Batch sinh hai file

`topic_two_days.jsonl`: offset 0,1 ngày `2023-11-14`; offset 2 ngày `2023-11-15`; `batch_size = 3`.

- Một batch (b = 0) sinh hai part: `date=2023-11-14/part-0-0.jsonl` (2 dòng) và `date=2023-11-15/part-0-1.jsonl` (1 dòng).
- Manifest `batch-0.json` liệt kê **cả hai** file. Nếu crash sau khi mới đặt file thứ nhất, không có manifest ⇒ lần sau dọn `part-0-*` rồi ghi lại cả hai; không mất dòng, không trùng dòng.
- Test mô phỏng trạng thái đó bằng cách đặt sẵn `part-0-0.jsonl` cũ (không manifest) trước khi chạy; trạng thái này tương đương crash sau file đầu và không cần hook chi tiết hơn.
- `rows_written = 3`.

### 8.6 Dead-letter + crash

`topic_with_bad.jsonl`: offset 1 sai `event_time` kiểu chuỗi, `batch_size = 3`.

- Publish: `dead/part-0.jsonl` có đúng một dòng `{"offset": 1, "reason": "invalid_type:event_time", "raw": "…"}`; `rows_written = 2`; `dead_letters = 1`.
- Nếu crash trước manifest ở batch này, lần sau file dead bị **dọn và ghi lại**; tổng số bản ghi dead cho offset 1 vẫn là **1**.

### 8.7 Data loss và `latest`

- Checkpoint `next_offset = 9`, topic 5 dòng, `fail_on_data_loss = true` ⇒ `DataLossDetected(9, 5)`.
- `false` ⇒ checkpoint sửa về 5, `data_loss = true`.
- Chưa có checkpoint, `latest`, topic 5 dòng ⇒ `batches = 0`, `next_offset = 5`.

## 9. Tiêu chí chấp nhận

1. 8.1: đúng ba tên file, đúng số dòng, `rows_written = 5`, ba manifest.
2. 8.3: sau crash + resume, tổng dòng trong `data/` = **5**; `batch-1.json` chỉ xuất hiện một lần; nội dung `part-1.jsonl` giống hệt giữa hai lần ghi.
3. 8.4: lần chạy 2 có `skipped_committed = 1`, `rows_written = 1`, tổng dòng = 5.
4. **Part đơn lẻ không bao giờ được tính là đã commit**: trên thư mục sạch, tạo tay `data/date=<D>/part-0.jsonl` (batch 0 **chưa** commit) với nội dung cũ, rồi chạy pipeline; file phải bị dọn/ghi lại, `batch-0.json` xuất hiện, và không có dòng trùng.
5. 8.5: một manifest liệt kê hai file; crash sau file đầu ⇒ sau resume đủ hai file, `rows_written = 3`, không trùng.
6. 8.6: `dead/part-0.jsonl` có đúng một bản ghi cho offset 1 sau **nhiều** lần resume (chạy 5 lần liên tiếp vẫn 1).
7. 8.7 đúng cả ba nhánh; riêng `latest` phải **tạo** `checkpoint.json` với `next_offset = 5` dù `batches = 0`.
8. Không còn `_tmp/` rỗng sót sau khi chạy xong; không còn `*.tmp` cạnh checkpoint/manifest.
9. `batch_size = 0` hoặc `> 500` ⇒ `InvalidConfig`.
10. `schema_version` khác checkpoint ⇒ `SchemaMismatch`, không sửa dữ liệu.
11. Cùng input ⇒ nội dung data/manifest/checkpoint giống hệt qua hai lần chạy sạch (byte-identical, trừ đường dẫn tuyệt đối).

## 10. Non-goals

- Không Kafka/HDFS/Spark/parquet; không cluster.
- Không đa writer, không lease, không giao dịch phân tán.
- Không `fsync` cho data part; không watermark/cửa sổ/state store; không compaction.
