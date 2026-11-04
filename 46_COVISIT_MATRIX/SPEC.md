# SPEC 46 — Ma trận đồng truy cập ngoài bộ nhớ

## 1. Đầu vào

### 1.1 CSV sự kiện

Header bắt buộc, đúng thứ tự này (cột thừa bị bỏ qua):

```csv
session,aid,ts,type
s1,a,0,click
s1,b,10,cart
s1,c,20,order
s2,a,5,click
s2,c,8,click
```

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `session` | chuỗi không rỗng | — |
| `aid` | chuỗi không rỗng | — |
| `ts` | số nguyên `>= 0` | Không giảm dần **trong toàn file** |
| `type` | chuỗi | Phải có trong `type_weight` của config, hoặc bị bỏ qua theo luật 1.2 |

Yêu cầu `ts` không giảm dần trên toàn file, không chỉ trong phiên.

### 1.2 Config

```json
{
  "name": "clicks",
  "valid_time": 15,
  "session_window": 30,
  "top_k": 2,
  "type_weight": {"click": 1.0, "cart": 2.0, "order": 3.0},
  "chunk_rows": 1000
}
```

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `valid_time` | bắt buộc | Cửa sổ thời gian, đơn vị của `ts`; điều kiện là `<` chặt |
| `session_window` | `30` | Số sự kiện gần nhất được ghép cặp |
| `top_k` | `20` | Số cặp giữ lại cho mỗi `aid_x` |
| `type_weight` | bắt buộc | Bản đồ loại → trọng số, giá trị `>= 0` |
| `chunk_rows` | `1000` | Số dòng mỗi lần đọc; **không** phải giới hạn bộ nhớ chính |

Loại không có trong `type_weight`: sự kiện vẫn được đệm nhưng không tạo cặp khi nó là **đích**; đếm vào `stats.skipped_types`.

## 2. Quy tắc sinh cặp

Khi xử lý sự kiện mới `e = (s, aid_y, ts_y, type_y)`:

```text
với mỗi sự kiện trước p = (aid_x, ts_x) trong đệm của phiên s (tối đa session_window phần tử gần nhất,
                                                         duyệt từ mới nhất tới cũ nhất):
    nếu ts_y - ts_x < valid_time  và  aid_x != aid_y:
        pairs[(aid_x, aid_y)] += type_weight[type_y]   # trọng số của ĐÍCH
        cặp_được_tính += 1
sau đó thêm e vào cuối đệm; nếu vượt session_window, bỏ phần tử cũ nhất
```

Ghi chú thiết kế:

- `ts_y - ts_x` (không phải trị tuyệt đối) vì đầu vào đã sắp tăng; nếu âm thì dữ liệu sai (lỗi 4.1).
- Điều kiện là `< valid_time`, không phải `<=`. Ví dụ với `valid_time = 15`, hiệu đúng `15` bị loại.
- Trọng số lấy từ `type_y` — khớp `df.type_y.map(type_weight)` của nguồn.
- Bỏ phần tử cũ khỏi đệm **không** hoàn tác các cặp đã cộng; đệm chỉ giới hạn việc ghép cặp về sau.

## 3. Hết hạn phiên

Một phiên chỉ có thể tạo cặp khi có sự kiện mới trong `valid_time`. Vì `ts` tăng dần, khi xử lý sự kiện tại `ts_now`, mọi phiên có `ts_now - last_ts(s) >= valid_time` không thể ghép cặp nữa và phải bị **xoá khỏi bộ nhớ**.

Thứ tự bắt buộc: hết hạn **trước** khi ghép cặp với sự kiện hiện tại.

`stats.expired_sessions` đếm số lần xoá. `stats.max_buffered_events` là tổng số phần tử trong mọi đệm tại đỉnh cao nhất, đo sau khi thêm sự kiện.

## 4. Output

```json
{
  "name": "clicks",
  "pairs": {
    "a": [["b", 2.0], ["c", 1.0]],
    "b": [["c", 3.0]]
  },
  "stats": {
    "expired_sessions": 0,
    "input_events": 5,
    "max_buffered_events": 2,
    "pairs_counted": 3,
    "sessions_seen": 2,
    "skipped_types": 0
  }
}
```

Quy tắc:

- `pairs` chỉ chứa `aid_x` có ít nhất một cặp; mỗi danh sách đã cắt top-k.
- Sắp trong mỗi danh sách: `weight` giảm dần; hoà thì `aid_y` tăng dần (so sánh chuỗi).
- Sắp khóa của `pairs`: theo thứ tự từ điển khi in (`json.dumps(..., sort_keys=True)`).
- Trọng số in dạng số thực; nếu là số nguyên (ví dụ `2.0`) thì JSON in `2.0` (không in `2`).
- Không có `aid_x` với danh sách rỗng.

## 5. Hai cài đặt phải bằng nhau

| Hàm | Cách làm | Mục đích |
|---|---|---|
| `batch_reference(rows, config)` | Nạp toàn bộ vào `dict[session] -> list`, cắt `session_window`, ghép mọi cặp | Làm chuẩn dễ đọc |
| `stream(path, config)` | Đọc theo chunk, đệm giới hạn, hết hạn phiên | Làm thật |

Bắt buộc: với **mọi** fixture hợp lệ, `stream` và `batch_reference` cho cùng `pairs` và cùng `pairs_counted`. Khác biệt duy nhất được phép là `stats.max_buffered_events` (chỉ `stream` báo).

## 6. Kiểm tra hợp lệ

| Điều kiện | Lỗi |
|---|---|
| Thiếu header hoặc sai tên cột | `BadHeader` |
| `ts` giảm so với dòng trước | `NonMonotonicTimestamp(line)` |
| `ts` không phải số nguyên | `MalformedRow(line)` |
| `session`/`aid` rỗng | `MalformedRow(line)` |
| `valid_time <= 0` | `InvalidConfig` |
| `session_window < 1` hoặc `top_k < 1` | `InvalidConfig` |
| trọng số âm hoặc không hữu hạn | `InvalidConfig` |
| `chunk_rows < 1` | `InvalidConfig` |

Mặc định dừng ở lỗi đầu tiên (tất định). Cờ `--skip-bad` biến `MalformedRow` thành đếm trong `stats.skipped_rows`, nhưng **không** bỏ qua `NonMonotonicTimestamp` (vì nó phá giả định của thuật toán).

## 7. Ví dụ cụ thể

Với CSV ở mục 1.1 và config `valid_time = 15`, `top_k = 2`, `type_weight = {click: 1, cart: 2, order: 3}`:

| Sự kiện | Đệm trước | Cặp sinh ra | Luỹ kế |
|---|---|---|---|
| `s1,a@0 click` | — | — | — |
| `s2,a@5 click` | — | — | — |
| `s2,c@8 click` | `s2: [a@5]` | `(a,c)` hiệu 3 `< 15`, trọng số `1` | `(a,c)=1` |
| `s1,b@10 cart` | `s1: [a@0]` | `(a,b)` hiệu 10 `< 15`, trọng số `2` | `(a,b)=2` |
| `s1,c@20 order` | `s1: [a@0, b@10]` | `(a,c)` hiệu 20 **không** `< 15` → loại; `(b,c)` hiệu 10, trọng số `3` | `(b,c)=3` |

Top-k 2: `a -> [["b",2.0],["c",1.0]]`, `b -> [["c",3.0]]`. Khớp output ở mục 4.

### 7.1 Biên cửa sổ

Thêm sự kiện `s1,d@30 click` vào phiên `s1` (đệm `[a@0,b@10,c@20]`):

- `(a,d)` hiệu 30 → loại.
- `(b,d)` hiệu 20 → loại.
- `(c,d)` hiệu 10 → nhận, trọng số `1` ⇒ `(c,d)=1`.

Nếu ai đó dùng `<= valid_time`, `(b,d)` sẽ lọt và test này bắt được.

### 7.2 Cặp tự thân

`aid` lặp lại trong cùng phiên (ví dụ `s1,a@0` rồi `s1,a@5`): hiệu 5 `< 15` nhưng `aid_x == aid_y` ⇒ không tạo cặp.

### 7.3 Cắt cửa sổ phiên

Một phiên 40 sự kiện `aid` khác nhau, `ts = 0..39`, `valid_time = 100`, `session_window = 30`:

- Sự kiện thứ 31 (`idx = 30`) chỉ ghép với 30 sự kiện trước (idx 0..29) — tất cả vẫn trong cửa sổ thời gian.
- Sự kiện thứ 40 (`idx = 39`) ghép với idx 9..38; idx 0..8 đã bị đẩy khỏi đệm.
- `pairs_counted = 30 + 30 + … = 30 * 40 - 30*31/2 = 1200 - 465 = 735`? Không: với `idx i`, số cặp là `min(i, 30)`. Tổng `= sum_{i=0}^{39} min(i,30) = (0+1+…+29) + 10*30 = 435 + 300 = 735`.

Đây là con số dùng trong test.

## 8. Tiêu chí chấp nhận

1. Ví dụ 7 cho đúng output ở mục 4, kể cả `pairs_counted = 3`, `max_buffered_events = 2`.
2. `stream` và `batch_reference` cho cùng `pairs` trên ít nhất 5 fixture, gồm fixture ngẫu nhiên 5000 sự kiện.
3. Điều kiện cửa sổ là `<`: 7.1 loại `(b,d)`.
4. `stats.max_buffered_events <= sessions_đang_mở * session_window` tại mọi thời điểm, và với một phiên đơn độc thì `<= session_window`.
5. Phiên bị hết hạn: fixture có `s1` ở `ts=0` rồi sự kiện khác ở `ts=10^6` phải tăng `expired_sessions` và không làm hỏng kết quả.
6. Sắp xếp hoà: `fixtures/ties.csv` cho thứ tự `aid_y` tăng dần ổn định.
7. Chạy hai lần cho JSON giống hệt (`sort_keys=True`).
8. Fixture `long_session.csv` cho `pairs_counted = 735` với cấu hình ở 7.3.

## 9. Non-goals

- Không GPU, không pandas/cuDF, không parquet.
- Không xử lý sự kiện không sắp thứ tự; không có watermark chịu trễ.
- Không sinh candidate cho phiên mới, không đánh giá chất lượng gợi ý.
- Không hỗ trợ nhiều tiến trình hay ghi đĩa từng phần.
