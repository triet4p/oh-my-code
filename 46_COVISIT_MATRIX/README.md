# 46 — Ma trận đồng truy cập ngoài bộ nhớ

## Mục tiêu

Xây ma trận **đồng truy cập** (co-visitation) từ luồng sự kiện phiên: cặp `(hành vi trước, hành vi sau)` trong cửa sổ thời gian, có trọng số theo loại hành vi đích, cắt theo độ dài cửa sổ phiên, và lấy top-k cho từng item — **không nạp toàn bộ dữ liệu vào bộ nhớ**.

1. Đọc CSV sự kiện theo chunk, giữ bộ đệm có giới hạn cho từng phiên.
2. Sinh cặp trong cửa sổ `valid_time` (so sánh chặt `<`), loại cặp tự thân.
3. Cộng trọng số theo `type_weight` của **sự kiện đích**, giới hạn 30 hành vi gần nhất.
4. Cắt top-k mỗi `aid_x`, sắp xếp tất định.
5. Chứng minh phiên bản luồng cho kết quả **giống hệt** phiên bản tham chiếu nạp toàn bộ.

## Giá trị

- Đây là bài toán "out-of-core" thật: phép tự-join của nguồn nhân bản phiên và nổ bộ nhớ; bài tập buộc bạn thiết kế cửa sổ trượt có bằng chứng tương đương.
- Cắt top-k và sắp xếp tất định là nơi dễ sinh lỗi "khác nhau giữa hai lần chạy" — bài tập ghim thứ tự hoà.
- Bạn học cách viết **hai cài đặt** (ngây thơ + tối ưu) và một bộ test chứng minh chúng bằng nhau. Đây là kỹ năng kiểm chứng, không chỉ cài đặt.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`csv`, `collections`, `heapq`) |
| Độ khó | Khó |
| Điều kiện | Cấu trúc dữ liệu cửa sổ, `deque`, đọc CSV theo chunk, so sánh chuỗi |
| Runtime | Không mạng, không GPU, không pandas/cuDF |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/otto-rec-sys` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/otto-rec-sys/blob/main/src/candidate_generation/covisit_matrix.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Tự ghép phiên: `df = df.merge(df, on='session')`.
  - Lọc cặp: `df = df.loc[((df.ts_x - df.ts_y).abs() < valid_time) & (df.aid_x != df.aid_y)]`.
  - Cắt 30 hành vi cuối mỗi phiên: `df.groupby('session').cumcount()`.
  - Trọng số theo loại của sự kiện đích: `df['wgt'] = df.type_y.map(type_weight)`.
  - Tổng hợp: `groupby(['aid_x','aid_y']).wgt.sum()`; cộng dồn theo chunk `inner_tmp.add(df, fill_value=0)`.
  - Cắt top-k cuối: `outer_tmp.loc[outer_tmp.n < top_k]`.
  - Ba biến thể cấu hình: `cart_order`, `buy2buy`, `clicks`.
- Giới hạn bằng chứng: nguồn dùng cuDF/GPU và parquet; bài tập không chạy được nguồn, chỉ mô phỏng ngữ nghĩa bằng CPU/thư viện chuẩn.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: ý tưởng tự ghép theo phiên; điều kiện cửa sổ thời gian chặt `<`; loại cặp tự thân; giới hạn 30 hành vi; trọng số lấy theo loại sự kiện **đích**; cộng dồn theo chunk; top-k mỗi item; ba biến thể cấu hình.

Phần **do bài tập định nghĩa**:

- **Quy tắc cửa sổ**: nguồn cắt "30 hành vi cuối mỗi phiên"; bài tập dùng cửa sổ **30 hành vi gần nhất tại thời điểm ghép cặp** để xử lý luồng được. Hai quy tắc trùng nhau khi phiên có ≤ 30 hành vi; khác nhau khi dài hơn. Đây là khác biệt có chủ đích, phải ghi rõ.
- Định dạng CSV, định dạng output JSON, tên lỗi.
- Thuật toán streaming có bộ đệm giới hạn và cơ chế hết hạn phiên.
- Yêu cầu hai cài đặt cho cùng kết quả (tham chiếu + luồng).
- Ba biến thể được biểu diễn bằng file cấu hình, không hard-code.

Nguồn **không** bao gồm: GPU, parquet, hay pipeline candidate-generation đầy đủ.

## Phạm vi

Trong phạm vi:

- Một CLI `python -m src run --events fixtures/events.csv --config fixtures/clicks.json`.
- Hai cài đặt: `batch_reference()` và `stream()`; test so sánh trên nhiều fixture.
- Đo và in số sự kiện đang đệm tối đa để chứng minh giới hạn bộ nhớ.

Ngoài phạm vi:

- Không pandas/cuDF/GPU; không parquet; không đọc dữ liệu thật của Otto.
- Không huấn luyện mô hình; không sinh candidate cho session mới.
- Không xử lý sự kiện đến không theo thứ tự thời gian (yêu cầu đầu vào đã sắp).

## Cảnh báo production

- Nguồn chạy trên GPU với partition theo chunk; bài này chỉ mô phỏng ngữ nghĩa trên CPU. Đừng dùng kết quả để suy ra hiệu năng.
- "30 hành vi cuối phiên" và "30 hành vi gần nhất khi ghép cặp" khác nhau với phiên dài; nếu bạn cần đúng nguồn, phải chấp nhận trễ (chờ phiên đóng) hoặc hai lượt.
- Trọng số theo loại **đích** là quyết định có ảnh hưởng lớn: đổi sang loại nguồn sẽ đổi hoàn toàn ma trận.
- Với `valid_time` lớn, số cặp mỗi sự kiện xấp xỉ bề rộng cửa sổ; chi phí là `O(số sự kiện × 30)` — chấp nhận được, nhưng đừng tăng cửa sổ phiên mà không đo.

## Fixture offline

- `fixtures/events.csv` — 5 sự kiện, 2 phiên, đủ để kiểm tra bằng tay (SPEC mục 7).
- `fixtures/long_session.csv` — một phiên 40 sự kiện, kiểm tra cắt 30.
- `fixtures/ties.csv` — nhiều cặp cùng trọng số, kiểm tra thứ tự hoà.
- `fixtures/clicks.json`, `cart_order.json`, `buy2buy.json` — ba biến thể cấu hình.
- Không có URL ngoài; mọi dữ liệu sinh cục bộ.

## Liên kết

- [SPEC.md](SPEC.md) — định dạng, thuật toán, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế cửa sổ trượt, chứng minh tương đương, kiểm chứng.
