# GUIDE 46 — Ma trận đồng truy cập ngoài bộ nhớ

## 1. Vì sao phải làm hai phiên bản

Cách ngây thơ (nạp hết, tự ghép) rất dễ viết đúng và rất dễ kiểm tra bằng mắt. Cách luồng khó hơn nhưng mới là thứ dùng được với dữ liệu lớn. Nếu chỉ viết cách luồng, bạn không có chuẩn để so; nếu chỉ viết cách ngây thơ, bạn không học được gì về bộ nhớ.

Bài tập yêu cầu **cả hai** và một bộ test chứng minh `stream(rows) == batch(rows)` trên nhiều fixture. Đây là mẫu "differential testing" đáng mang theo.

## 2. Mô hình bộ nhớ

### 2.1 Thứ bị giới hạn là gì

`chunk_rows` chỉ giới hạn số dòng đọc mỗi lần; nó **không** giới hạn bộ nhớ thật. Thứ quyết định bộ nhớ là:

```text
Σ_{phiên đang mở} len(đệm(phiên))   ≤   số_phiên_đang_mở × session_window
```

Và số phiên đang mở bị chặn bởi `valid_time`: phiên không có sự kiện mới trong `valid_time` bị xoá.

Ví dụ xấu: nếu bạn giữ mọi phiên suốt file, bộ nhớ là `O(số phiên)` — quay lại đúng vấn đề của phép self-join.

### 2.2 Cấu trúc

```text
open_sessions: dict[str, deque[Event]]     # mỗi deque tối đa session_window
last_seen:     dict[str, int]              # ts của sự kiện cuối mỗi phiên
pairs:         dict[tuple[str, str], float]
```

Có thể gộp `last_seen` vào phần tử cuối của deque; gộp thì ít lỗi đồng bộ hơn.

### 2.3 Hết hạn phiên không cần heap

Vì `ts` không giảm, khi xử lý `ts_now`, mọi phiên có `last_ts < ts_now - valid_time + 1` đều hết hạn (điều kiện ghép cặp là `< valid_time`, nên `ts_now - last_ts >= valid_time` là chết). Bạn có hai lựa chọn:

- Quét toàn bộ `open_sessions` mỗi sự kiện: `O(P)` mỗi sự kiện — chấp nhận được với fixture bài này, nhưng ghi rõ.
- Duy trì `heapq` theo `last_ts`: `O(log P)`; phức tạp hơn, dễ sai khi cập nhật `last_ts`.

SPEC không bắt buộc cách nào; chỉ bắt buộc **thứ tự**: hết hạn trước, ghép cặp sau.

## 3. Thứ tự cài đặt

### Bước 1 — `batch_reference` trước

Đây là bản đặc tả chạy được. Viết theo đúng văn bản SPEC:

```text
theo phiên: lấy list sự kiện (giữ thứ tự file)
với i từ 0..n-1:
    lo = max(0, i - session_window)
    với j từ lo..i-1:
        nếu ts[i] - ts[j] < valid_time và aid[i] != aid[j]:
            pairs[(aid[j], aid[i])] += weight[type[i]]
```

Lưu ý `j` chạy trong cửa sổ **trước** `i`, không phải toàn phiên. Đây chính là điểm khác nguồn (nguồn cắt 30 cuối phiên); ghi chú ngay trong docstring.

### Bước 2 — `stream`

Đọc CSV bằng `csv.reader`, kiểm tra header một lần, lặp chunk bằng `itertools.islice`.

Với mỗi dòng:

1. Parse, kiểm tra `ts >= ts_prev` (biến toàn cục), kiểm tra kiểu.
2. **Hết hạn** các phiên.
3. Ghép với đệm của phiên hiện tại, duyệt **từ mới nhất về cũ nhất**. Thứ tự này không ảnh hưởng tổng (cộng số thực có thể lệch 1 ulp), nhưng cố định để output ổn định.
4. Thêm sự kiện, cắt đệm nếu cần.
5. Cập nhật `max_buffered_events`.

### Bước 3 — Top-k

Sau khi có `pairs`, nhóm theo `aid_x` rồi sắp `(−weight, aid_y)` và cắt `top_k`. Đừng cắt trong lúc cộng dồn: một cặp có thể tăng trọng số sau đó và lọt vào top.

### Bước 4 — In

`json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)`. Để weight in `2.0` chứ không `2`, giữ chúng là `float` từ đầu (`float(config_value)`).

## 4. Cạm bẫy

- **Dùng `<=` cho cửa sổ**: sai theo SPEC và theo nguồn (`< valid_time`).
- **Trọng số theo loại nguồn**: nguồn dùng `type_y`. Đổi sang `type_x` cho kết quả khác hoàn toàn.
- **Hoàn tác cặp khi đẩy khỏi đệm**: sai. Cặp đã cộng là vĩnh viễn; đệm chỉ chặn ghép **về sau**.
- **Cắt top-k quá sớm**: một cặp yếu lúc đầu có thể mạnh về sau.
- **Sắp xếp bằng `sorted(dict.items())`**: sắp theo aid nhưng bỏ qua weight. Phải sắp hai khóa.
- **`ts` giảm trong file**: nếu bạn không kiểm tra, thuật toán vẫn chạy nhưng cửa sổ vô nghĩa. Ném lỗi.
- **Bộ nhớ "đo cho có"**: `max_buffered_events` phải đo **sau** khi thêm sự kiện, không phải trước; nếu không, fixture đúng bằng `session_window + 1` sẽ không bị bắt.
- **Cộng float không tất định**: cùng thứ tự cộng thì tất định; nếu bạn lặp `set` để cộng, thứ tự đổi giữa các lần chạy khiến tổng lệch ulp. Luôn lặp list.

## 5. Kiểm chứng

### 5.1 Tương đương hai cài đặt

```bash
python -m src compare --events fixtures/events.csv --config fixtures/clicks.json
```

Lệnh này phải in `identical: true`. Với fixture ngẫu nhiên:

```bash
python -m src fuzz --events 5000 --seed 7
```

Bên trong: sinh sự kiện ngẫu nhiên đã sắp `ts`, chạy cả hai, so `pairs` và `pairs_counted`.

### 5.2 Giới hạn bộ nhớ

```bash
python -m src run --events fixtures/long_session.csv --config fixtures/clicks.json | python -c "import json,sys; print(json.load(sys.stdin)['stats'])"
```

`max_buffered_events` phải bằng `30` (không phải 40) với `session_window = 30`.

### 5.3 Biên thời gian

Tạo fixture tối thiểu: hai sự kiện cùng phiên, hiệu đúng `valid_time`. Kết quả phải **rỗng**. Đây là test rẻ nhất để phát hiện nhầm `<` thành `<=`.

### 5.4 Hết hạn

Fixture: `s1` ở `ts=0`, `s2` ở `ts=1_000_000`, cấu hình `valid_time=15`. `expired_sessions` phải `>= 1`, và `s1` không tạo cặp.

## 6. Đo và giải thích

In thêm (không bắt buộc, đừng đưa vào JSON chính) số phiên đang mở theo thời gian để thấy profile: với dữ liệu thật, đường cong này thường có đỉnh ở giờ cao điểm. Nếu đỉnh vượt kỳ vọng, `valid_time` quá lớn hoặc session id quá phân tán.

## 7. Gợi ý

- Viết `iter_events(path, chunk_rows)` là generator; cả hai cài đặt dùng chung parser. Chỉ khác phần tích luỹ.
- Viết `add_pair(pairs, x, y, w)` để tập trung logic cộng và dễ thay bằng `Counter` nếu sau này cần đếm.
- Đừng tối ưu bằng `defaultdict(list)` cho pairs; dùng `dict` với `get` để tránh tạo khóa rỗng.
- Nếu muốn thấy khác biệt nguồn/bài tập, thêm cờ `--mode=source` cài "30 hành vi cuối phiên" trên batch reference; so hai chế độ trên `long_session.csv`.

## 8. Mở rộng

- **Hai lượt cho đúng nguồn**: lượt 1 đếm số sự kiện mỗi phiên để biết `lo` cho "30 cuối"; lượt 2 ghép. So với chế độ cửa sổ trượt.
- **Ba biến thể song song**: chạy ba config trong một lượt đọc, chia sẻ parser và đệm.
- **Trọng số thời gian**: nhân thêm `1 / (1 + hiệu)` để ưu tiên cặp gần nhau; kiểm tra tác động lên top-k.
- **Ghi đĩa theo partition**: ghi `pairs` theo bucket `hash(aid_x) % 16` để mô phỏng pipeline out-of-core thật.
- **Đo bộ nhớ thật**: dùng `tracemalloc` và so đỉnh với `max_buffered_events × sizeof(Event)`; giải thích chênh lệch.
