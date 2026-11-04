# SPEC 47 — Gợi ý phiên bằng đồ thị hai phía

## 1. Đồ thị và ma trận chuẩn hoá

### 1.1 Fixture

```json
{
  "num_users": 2,
  "num_items": 3,
  "edges": [[0, 0], [0, 1], [1, 1], [1, 2]]
}
```

Mỗi cạnh `[u, i]` là một lần tương tác. Cạnh trùng **không** được phép (`DuplicateEdge`); nếu muốn trọng số, đó là phần mở rộng.

### 1.2 Ma trận kề chuẩn hoá

Ma trận kề hai phía kích thước `(U + I) × (U + I)`:

```text
A[u][I + i] = 1 nếu có cạnh (u, i)
A[I + i][u] = 1
bậc d[v] = số láng giềng của v
A_norm[u][v] = A[u][v] / sqrt(d[u] * d[v])      nếu d[u] > 0 và d[v] > 0
A_norm[u][v] = 0                                nếu ngược lại
```

**Không** thêm self-loop. **Không** chuẩn hoá hàng về 1.

Kiểm tra bằng tay với fixture trên:

- `d = [2, 2, 1, 2, 1]` theo thứ tự `[u0, u1, i0, i1, i2]`.
- `A_norm[u0][i0] = 1 / sqrt(2*1) = 0.70710678…`
- `A_norm[u0][i1] = 1 / sqrt(2*2) = 0.5`
- `A_norm[u1][i1] = 0.5`
- `A_norm[u1][i2] = 0.70710678…`
- Hàng `u0` tổng `1.20710678…` — **không** bằng 1. Đây là hành vi đúng.

`A_norm` đối xứng: `A_norm[i][j] == A_norm[j][i]` trong sai số `1e-12` (kiểm tra bằng `math.isclose` với `rel_tol=0, abs_tol=1e-12`).

## 2. Lan truyền

Với embedding gốc `E0` kích thước `(U+I) × dim`:

```text
E[0] = E0
E[k+1] = A_norm @ E[k]          với k = 0..L-1
E_final = (E[0] + E[1] + … + E[L]) / (L + 1)
```

Không có ma trận trọng số, không có activation, không có self-loop. `L >= 0`; `L = 0` nghĩa là `E_final = E0`.

### 2.1 Ví dụ một chiều

Với fixture 1.1, `dim = 1`, `E0 = [1, 0, 0, 0, 0]` (chỉ `u0` khác 0), `L = 1`:

- `E[1][i0] = A_norm[i0][u0] * 1 = 0.70710678`
- `E[1][i1] = 0.5`
- `E[1][i2] = 0`
- `E[1][u0] = 0` (láng giềng của `u0` là item, đều `0`), `E[1][u1] = 0`
- `E_final = (E[0] + E[1]) / 2` ⇒ `[0.5, 0, 0.35355339, 0.25, 0]`

Đây là test số học bắt buộc (dung sai `1e-9`).

## 3. BPR

### 3.1 Loss

Với bộ ba `(u, i_pos, i_neg)`:

```text
s_pos = dot(E_final[u], E_final[i_pos])
s_neg = dot(E_final[u], E_final[i_neg])
x = s_pos - s_neg
loss = -log(sigmoid(x)) = softplus(-x)
```

Loss của batch là trung bình cộng `loss` trên các bộ ba.

### 3.2 Hàm gradient độc lập (bắt buộc có)

Cài thêm một hàm thuần:

```text
bpr_gradients(e_u, e_pos, e_neg) -> (g_u, g_pos, g_neg)
```

Với `sigma = 1/(1+exp(-x))` và `c = -(1 - sigma)`:

```text
g_u   = c * (e_pos - e_neg)
g_pos = c * e_u
g_neg = -c * e_u
```

### 3.3 Ví dụ số cho gradient

`e_u = [1, 0]`, `e_pos = [1, 0]`, `e_neg = [0, 1]`:

- `s_pos = 1`, `s_neg = 0`, `x = 1`
- `sigma(1) = 0.7310585786…`, `c = -0.2689414214…`
- `g_u = [-0.2689414, +0.2689414]` (làm tròn 7 chữ số)
- `g_pos = [-0.2689414, 0]`
- `g_neg = [+0.2689414, 0]`

Sai số cho phép `1e-7`.

### 3.4 Huấn luyện

```text
khởi tạo E0 ~ Uniform(-0.1, 0.1) bằng LCG với seed
lặp steps lần:
    chọn một cạnh dương theo thứ tự vòng (không ngẫu nhiên)
    chọn item âm bằng LCG, khác item dương; nếu trùng, rút lại (tối đa 20 lần, sau đó bỏ mẫu)
    tính E_final bằng lan truyền
    cộng dồn gradient vào E0 (gradient xuyên qua A_norm và phép trung bình)
    E0 -= lr * grad
ghi loss mỗi `log_every` bước
```

Gradient xuyên lan truyền: vì `E_final` là tổ hợp tuyến tính của `E0`, gradient lan ngược qua `A_norm^T` và hệ số `1/(L+1)`. Nếu bạn chỉ cập nhật `E_final` mà không lan ngược, **loss vẫn có thể giảm** nhưng đó không phải LightGCN — hãy ghi rõ chế độ (`--mode=direct` cho phép, mặc định là `--mode=graph`).

## 4. Gợi ý

```text
session_vector = normalize(mean(E_final[item] cho item trong lịch sử))
score(i) = dot(session_vector, normalize(E_final[i]))
loại item đã có trong lịch sử
sắp xếp: score giảm dần, hoà thì item_id tăng dần
lấy top_k
```

`normalize(v)` = `v / ||v||_2`; nếu `||v|| == 0`, trả vector 0 và `recommend` trả danh sách rỗng (kèm cờ `degenerate_vector: true`).

### 4.1 Ví dụ cosine

Embedding item (2 chiều): `A = [1, 0]`, `B = [0, 1]`, `C = [0.70710678, 0.70710678]`.
Lịch sử `[A, B]`:

- trung bình `= [0.5, 0.5]`; chuẩn hoá `= [0.70710678, 0.70710678]`
- `score(A) = 0.70710678`, `score(B) = 0.70710678`, `score(C) = 1.0`
- loại `A`, `B` ⇒ top-1 `C` với `1.0`; top-2 `C` rồi (không còn) — danh sách chỉ có 1 phần tử.

## 5. Đầu ra CLI

```json
{
  "losses": [{"step": 0, "loss": 0.6931}, {"step": 100, "loss": 0.5123}],
  "recommendations": [{"item": 7, "score": 0.9123}],
  "degenerate_vector": false
}
```

- `losses` chứa mốc `0`, `log_every`, `2*log_every`, …, và mốc cuối.
- `loss` in 4 chữ số thập phân.
- `recommendations` theo thứ tự top-k đã sắp.
- Output sắp khóa khi in.

## 6. Kiểm tra hợp lệ

| Điều kiện | Lỗi |
|---|---|
| `num_users < 1` hoặc `num_items < 1` | `InvalidShape` |
| cạnh ngoài miền | `EdgeOutOfRange` |
| cạnh trùng | `DuplicateEdge` |
| `dim < 1` hoặc `layers < 0` | `InvalidConfig` |
| `lr <= 0`, `steps < 0` | `InvalidConfig` |
| `top_k < 1` | `InvalidConfig` |
| lịch sử rỗng hoặc chứa item ngoài miền | `InvalidHistory` |
| vector toàn 0 khi chuẩn hoá | **không** ném; trả cờ `degenerate_vector` |

## 7. Tiêu chí chấp nhận

1. `build_norm_adj` cho đúng các giá trị ở 1.2 (dung sai `1e-9`) và đối xứng.
2. Hàng `u0` của `A_norm` tổng `≈ 1.20710678`; test khẳng định **không** bằng 1 (bảo vệ chống "sửa cho đẹp").
3. `propagate` với ví dụ 2.1 cho `[0.5, 0, 0.35355339, 0.25, 0]`.
4. `bpr_gradients` khớp 3.3 trong `1e-7`.
5. Trên `fixtures/train_small.json`, loss tại bước cuối **nhỏ hơn** loss tại bước 0 ít nhất 5%; mọi giá trị hữu hạn.
6. `recommend` với 4.1 trả `[("C", 1.0)]` cho `top_k=1` và loại đúng item đã xem.
7. Vector phiên 0 ⇒ danh sách rỗng + `degenerate_vector: true`, không chia cho 0.
8. Cùng seed + cùng fixture ⇒ output giống hệt (so `json.dumps(sort_keys=True)`).
9. `L = 0` cho `E_final == E0` chính xác.

## 8. Non-goals

- Không `torch`, không autograd, không GPU, không FAISS.
- Không đánh giá chất lượng gợi ý trên dữ liệu thật; không NDCG/recall.
- Không cold-start, không đặc trưng phụ (giá, thời gian).
- Không tối ưu hiệu năng; đồ thị nhỏ là chủ đích.
