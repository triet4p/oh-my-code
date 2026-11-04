# GUIDE 47 — Gợi ý phiên bằng đồ thị hai phía

## 1. Ba lớp, ba trắc nghiệm

| Lớp | Câu hỏi | Test tương ứng |
|---|---|---|
| Chuẩn hoá | Ma trận có đúng `D^{-1/2} A D^{-1/2}`? | 1.2 của SPEC |
| Lan truyền | Một lớp có đúng một phép nhân? | 2.1 của SPEC |
| Học | Gradient BPR có đúng dấu? | 3.3 của SPEC |

Nếu bạn gộp ba lớp vào một hàm, mọi lỗi sẽ biểu hiện thành "loss không giảm" và bạn sẽ mất hàng giờ. Hãy cài đúng thứ tự và test từng lớp.

## 2. Cấu trúc dữ liệu

```text
Graph:
    U, I, dim, layers
    A: list[list[float]]        # (U+I) x (U+I), dense
    edges: list[(u, i)]

Params:
    E0: list[list[float]]       # (U+I) x dim
```

Gợi ý hàm:

- `build_norm_adj(U, I, edges) -> list[list[float]]`
- `matmul(A, E) -> list[list[float]]`
- `propagate(E0, A, layers) -> list[list[float]]`
- `bpr_gradients(e_u, e_pos, e_neg) -> (g_u, g_pos, g_neg)`
- `train(...) -> TrainReport`
- `recommend(...) -> list[(item, score)]`

## 3. Thứ tự cài đặt

### Bước 1 — Ma trận kề

Duyệt cạnh hai lần (một lần đếm bậc, một lần gán giá trị) hoặc gán `1` rồi chia sau. Cẩn thận: nếu chia ngay khi gán, bạn cần biết bậc trước.

Kiểm tra nhanh bằng tay: in hàng `u0` và so với `[0, 0, 0.7071, 0.5, 0]`.

### Bước 2 — Nhân ma trận

Với kích thước nhỏ, vòng ba lớp là đủ. Viết `matmul` thành hàm riêng để test với ma trận đơn vị.

Một lỗi tinh vi: nếu bạn dùng `sum` trên generator mà không khởi tạo `0.0`, kiểu có thể thành int khi mọi phần tử là `0`. Luôn `0.0`.

### Bước 3 — Trung bình các lớp

Giữ **danh sách** `E[k]` (kể cả `E[0]`) rồi cộng dồn chia `L+1`. Đừng cộng dồn kiểu `E = (E + next)/2` — sai trọng số khi `L > 1` (đó là trung bình luỹ kế, không phải trung bình đều).

### Bước 4 — Gradient

Suy luận một lần rồi viết:

```text
x = s_pos - s_neg
sigma = 1 / (1 + exp(-x))
c = -(1 - sigma)
```

Ba gradient ở SPEC. Test bằng 3.3 trước khi nối vào huấn luyện.

### Bước 5 — Lan ngược qua A_norm

Vì `E_final = (1/(L+1)) * Σ_k A_norm^k E0`, gradient của `E0` là:

```text
G = (1/(L+1)) * Σ_{k=0..L} (A_norm^T)^k g
```

Với `A_norm` đối xứng, `A_norm^T = A_norm`. Cài đặt: bắt đầu `acc = g`, sau đó lặp `L` lần `acc = g + A_norm @ acc`? Hãy tự kiểm tra bằng một ví dụ 2 nút trước khi tin.

Cách an toàn hơn cho người mới: dùng **gradient số** (finite difference) để kiểm tra gradient giải tích trên một mẫu nhỏ. Chênh lệch phải `O(h)`.

### Bước 6 — Huấn luyện

Chọn cạnh dương theo vòng (`i % len(edges)`) thay vì ngẫu nhiên: ít nhất một nguồn ngẫu nhiên (mẫu âm) và dễ tái lập. Mẫu âm bằng LCG; nếu trùng dương, rút lại tối đa 20 lần rồi bỏ mẫu (đếm vào `skipped_samples`).

### Bước 7 — Truy hồi

Chuẩn hoá **cả hai** phía (vector phiên và item). Cosine không chuẩn hoá sẽ thiên về item có norm lớn — đúng thứ mà `faiss.normalize_L2` trong nguồn ngăn chặn.

## 4. Cạm bẫy

- **Thêm self-loop**: LightGCN gốc không có; thêm vào làm embedding "dính" chính nó và kết quả lệch.
- **Chuẩn hoá hàng về 1**: sai mô hình. Xem SPEC 1.2 — hàng tổng `1.2071` là đúng.
- **Trung bình luỹ kế thay vì trung bình đều**: sai khi `L > 1`.
- **Chỉ cập nhật `E_final`**: trông vẫn "học" nhưng không phải lan truyền; phải ghi rõ chế độ.
- **Mẫu âm trùng dương**: làm loss nhiễu và có thể âm; luôn kiểm tra.
- **Chia cho 0 khi chuẩn hoá**: lịch sử rỗng hoặc embedding toàn 0; trả cờ thay vì crash.
- **Sắp xếp không ổn định**: hai item cùng score phải theo `item_id` tăng dần.
- **`exp` tràn**: với `x` rất âm, `exp(-x)` tràn. Dùng dạng số ổn định: nếu `x >= 0`, `loss = log1p(exp(-x))`; ngược lại `loss = -x + log1p(exp(x))`.

## 5. Kiểm chứng

```bash
python --version
python -m unittest discover -s tests -v
python -m src train --graph fixtures/toy_graph.json --steps 200 --log-every 50
python -m src recommend --history fixtures/session_history.json --top-k 3
```

So `losses` với kỳ vọng: bước 0 ≈ `0.6931` (BPR khởi tạo gần như ngẫu nhiên ⇒ `-log 0.5`), bước cuối nhỏ hơn đáng kể. Nếu bước 0 lệch nhiều khỏi `0.6931`, kiểm tra lại khởi tạo (giá trị quá lớn làm score chênh lệch).

Kiểm tra gradient bằng số:

```bash
python -m src gradcheck --graph fixtures/toy_graph.json
```

Kỳ vọng sai lệch tương đối `< 1e-4` với `h = 1e-5`.

## 6. Gợi ý

- Viết `dot`, `norm`, `normalize` thành ba hàm nhỏ, test riêng. Chúng xuất hiện ở cả ba lớp.
- Dùng `math.fsum` cho các tổng dài nếu muốn ổn định hơn; với `dim ≤ 8` thì không cần.
- In `E_final` của fixture toy ra để so bằng mắt với 2.1 trước khi huấn luyện.
- Nếu loss dao động mạnh, giảm `lr` một nửa và so đường cong; đừng đổi kiến trúc.

## 7. Mở rộng

- **Trọng số cạnh**: cho `edges` có trường `w`; chuẩn hoá thành `A * w`. Kiểm tra lại tính đối xứng.
- **Sparse**: chuyển sang danh sách kề và nhân theo láng giềng; so kết quả với bản dense trên toy graph.
- **Đánh giá offline**: chia cạnh cuối mỗi phiên làm test, tính recall@k; so với baseline "phổ biến nhất".
- **Nhiều mẫu âm**: `negatives_per_pos > 1`, lấy trung bình loss; xem tác động lên tốc độ hội tụ.
- **Đối chiếu nguồn**: thêm chế độ đọc embedding có sẵn từ file (mô phỏng `history_with_emb`) để thấy phần nào của nguồn là "học" và phần nào là "truy hồi".
