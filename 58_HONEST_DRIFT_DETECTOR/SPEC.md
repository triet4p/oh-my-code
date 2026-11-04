# SPEC 58 — Phát hiện drift với kết luận trung thực

## 1. Đầu vào

```json
{
  "reference": [[0, 0], [1, 0], [-1, 0]],
  "test": [[3, 0], [0, 3], [3, 0]],
  "config": {
    "fit_fraction": 0.0,
    "seed": 7,
    "z": 3.0,
    "shift": 3.0,
    "min_reference_rows": 3,
    "min_test_rows": 3,
    "regularization": 1e-6,
    "model": "fixed:0,0:1,0.8,0.8,4"
  }
}
```

| Khóa | Ý nghĩa |
|---|---|
| `reference` | `n_ref` dòng, mỗi dòng `d` số thực hữu hạn |
| `test` | `n_test` dòng, cùng `d` |
| `fit_fraction` | Tỉ lệ dòng tham chiếu dùng để fit; phần còn lại để calibration |
| `seed` | Seed LCG cho hoán vị cột |
| `z` | Hệ số ngưỡng (mặc định 3.0) |
| `shift` | Độ dịch mỗi chiều cho ca năng lực |
| `min_reference_rows` | Ngưỡng tối thiểu (mặc định 20; ví dụ dùng 3 để chạy tay) |
| `min_test_rows` | Ngưỡng tối thiểu (mặc định 10; ví dụ dùng 3) |
| `regularization` | `λ` cộng vào đường chéo hiệp phương sai khi fit |
| `model` | `"fixed:<mean>:<cov>"` để tiêm mô hình, hoặc `"fit"` để fit thật |

`model = "fixed:0,0:1,0.8,0.8,4"` nghĩa là mean `[0,0]`, hiệp phương sai `[[1,0.8],[0.8,4]]` (row-major).

## 2. Mô hình mật độ

### 2.1 Khi `model = "fit"`

- Lấy `n_fit = floor(fit_fraction * n_ref)` dòng **đầu tiên** của `reference` để fit (quyết định tất định).
- `mean = trung bình cột`.
- `cov = hiệp phương sai quần thể (chia n_fit) + λ * I`.
- Tính nghịch đảo bằng khử Gauss–Jordan **có kiểm tra pivot**; pivot `|p| < 1e-12` ⇒ `unsupported(reason="singular_covariance")`.
- `ln_det` tính bằng tổng log của các pivot trong quá trình khử (không dùng `det` rồi `log`).
- Yêu cầu `n_fit >= 2` và `n_ref - n_fit >= 2`.

### 2.2 Khi `model = "fixed:..."`

Dùng trực tiếp; vẫn kiểm tra nghịch đảo được. Với mô hình cố định, `fit_fraction` phải bằng `0.0` (mặc định trong ví dụ): `n_fit = 0` và `calib` là **toàn bộ** `reference`, để đối chứng không đổi (G2) có đủ hai dòng. Nếu `fit_fraction > 0` với mô hình cố định ⇒ `invalid_config`.

### 2.3 Log-likelihood

```text
ll(x) = -0.5 * ( d*ln(2π) + ln_det(cov) + (x - mean)ᵀ cov⁻¹ (x - mean) )
```

## 3. Thống kê và ngưỡng

```text
calib = n_ref - n_fit dòng còn lại
ll_ref = [ll(x) cho x trong calib]
mu_ref = mean(ll_ref)
var_ref = phương sai quần thể của ll_ref
mu_test = mean([ll(x) cho x trong test])
gap = mu_ref - mu_test
se = sqrt(var_ref / len(calib) + var_ref / n_test)
tau = z * se
```

- `gap > 0` nghĩa là mẫu **ít khả năng** hơn tham chiếu.
- Nếu `se == 0` (mọi `ll_ref` bằng nhau), dùng `tau = 0`.

## 4. Ba cổng kiểm soát

| Cổng | Định nghĩa | Ý nghĩa |
|---|---|---|
| G1 quan sát | `gap > tau` | Có tín hiệu vượt ngưỡng |
| G2 không đổi | `gap_no_shift <= tau` với `gap_no_shift = mu_ref_halfA - mu_ref_halfB` (chia đôi `calib` theo thứ tự) | Bộ dò không báo động trên dữ liệu không đổi |
| G3 năng lực | `gap_shifted > tau` với `shifted = [x + shift cho x trong calib]` | Bộ dò đủ năng lực phát hiện một dịch chuyển đã biết |
| G4 cấu trúc | `gap_null < gap`, với `gap_null` tính trên `test` đã hoán vị từng cột độc lập | Drift không chỉ do phân bố biên |

Hoán vị cột: với mỗi cột `j`, lấy danh sách `n_test` giá trị theo thứ tự dòng rồi xáo bằng **Fisher–Yates** với LCG `state = (1664525*state + 1013904223) mod 2^32`, `u = state / 2^32`, vòng `i` từ `n-1` xuống `1`, `k = floor(u*(i+1))`, đổi chỗ `a[i]` và `a[k]`; duyệt cột theo thứ tự `0..d-1`, dùng **cùng** một chuỗi LCG. `[DESIGN]` nhằm phá ghép cặp giữa các cột mà giữ nguyên phân bố biên.

Hệ quả bắt buộc: nếu mọi dòng của `test` giống hệt nhau thì hoán vị cột là phép không đổi, `gap_null == gap`, và G4 **phải** thất bại vì điều kiện là `<` ngặt. Đây là hành vi đúng — dữ liệu không đủ đa dạng để tách drift biên khỏi drift cấu trúc.

## 5. Kết luận

```text
nếu n_ref < min_reference_rows: unsupported("insufficient_reference_rows")
nếu n_test < min_test_rows:     unsupported("insufficient_test_rows")
nếu len(calib) < 2:             unsupported("insufficient_calibration_rows")
nếu model == "fit" và n_fit < 2: unsupported("insufficient_fit_rows")
nếu hiệp phương sai suy biến:   unsupported("singular_covariance")
nếu tau không hữu hạn:          unsupported("invalid_threshold")
nếu cả G1..G4 đều thoả:         supported
ngược lại:                      inconclusive(reasons=[...])
```

`reasons` liệt kê các cổng **không** thoả, theo thứ tự G1, G2, G3, G4, dạng `"G2_no_shift_control"`.

## 6. Đầu ra

```json
{
  "gates": {
    "G1_observed": true,
    "G2_no_shift": true,
    "G3_power": true,
    "G4_structure": true
  },
  "model": "fixed",
  "n_calibration": 3,
  "n_fit": 0,
  "n_test": 3,
  "outcome": "supported",
  "reasons": [],
  "statistic": {
    "gap": 3.6210317,
    "gap_null": 2.9067460,
    "gap_no_shift": 0.5952381,
    "gap_shifted": 4.5535714,
    "tau": 0.6873217
  }
}
```

Mọi số in 7 chữ số thập phân, khóa sắp khi in.

## 7. Ví dụ số đầy đủ

Mô hình cố định: `mean = [0,0]`, `Σ = [[1, 0.8], [0.8, 4]]`.

```text
Σ⁻¹ = [[1.1904762, -0.2380952], [-0.2380952, 0.2976190]]
det(Σ) = 3.36 ; ln det = 1.2119409
hằng số = 2*ln(2π) + ln det = 3.6757541 + 1.2119409 = 4.8876950
ll(x) = -0.5 * (4.8876950 + xᵀΣ⁻¹x)
```

Cấu hình ví dụ: `model` cố định, `fit_fraction = 0.0` (hợp lệ với mô hình cố định), do đó `n_fit = 0` và `calib` là toàn bộ `reference`, tức `[[0,0], [1,0], [-1,0]]`. `reference` có 3 dòng nên `min_reference_rows` được đặt bằng `3` trong fixture ví dụ; `min_test_rows = 3`.

| Đại lượng | Giá trị |
|---|---|
| `ll(0,0) = -0.5*4.8876950` | `-2.4438476` |
| `ll(1,0) = ll(-1,0) = -0.5*(4.8876950+1.1904762)` | `-3.0390856` |
| `mu_ref` | `-2.8406730` |
| `var_ref` | `0.0787352` |
| `ll(3,0) = -0.5*(4.8876950+10.7142857)` | `-7.8009904` |
| `ll(0,3) = -0.5*(4.8876950+2.6785714)` | `-3.7831333` |
| `mu_test` (một dòng `(0,3)`, hai dòng `(3,0)`) | `-6.4617047` |
| `gap` | `3.6210317` |
| `se = sqrt(0.0787352/3 + 0.0787352/3)` | `0.2291072` |
| `tau = 3 * se` | `0.6873217` |

Các cổng:

- **G1**: `3.6210317 > 0.6873217` ⇒ `true`.
- **G2**: chia `calib` đôi theo thứ tự: A = `[[0,0]]` (`mu = -2.4438476`), B = `[[1,0],[-1,0]]` (`mu = -3.0390856`) ⇒ `gap_no_shift = 0.5952381 <= tau` ⇒ `true`.
- **G3**: `shifted = [[3,3],[4,3],[2,3]]`; `ll` lần lượt `-6.9974190`, `-10.4497999`, `-4.7355142`; `mu = -7.3942444` ⇒ `gap_shifted = 4.5535714 > tau` ⇒ `true`.
- **G4**: hoán vị cột `test` với `seed = 7` cho `[[3,0],[0,0],[3,3]]` ⇒ `ll` lần lượt `-7.8009904`, `-2.4438476`, `-6.9974190`; `mu_null = -5.7474190` ⇒ `gap_null = 2.9067460 < gap = 3.6210317` ⇒ `true`.

⇒ `outcome = "supported"`.

### 7.1 Cùng dữ liệu, mẫu suy biến (mọi dòng giống hệt)

`test = [[0,3],[0,3],[0,3]]` (ba dòng giống hệt): `ll = -3.7831333` mỗi dòng; `mu_test = -3.7831333`; `gap = 0.9424603 > tau` (G1 true). Nhưng hoán vị từng cột trên các dòng giống hệt là **phép không đổi** ⇒ `gap_null = 0.9424603 = gap` ⇒ G4 false (điều kiện là `<` ngặt) ⇒ `inconclusive(["G4_structure_control"])`.

Đây là ca dạy học quan trọng: một mẫu chỉ có **một** kiểu dòng không cho phép tách drift biên khỏi drift cấu trúc, nên kết luận trung thực là `inconclusive`, dù `gap` lớn.

### 7.2 Quá ít dữ liệu

`reference` 2 dòng với `min_reference_rows = 20` ⇒ `unsupported(["insufficient_reference_rows"])`, và **không** fit, **không** tính thống kê.

## 8. Tiêu chí chấp nhận

1. Ví dụ 7 cho đúng bảng số (dung sai `1e-3`) và `outcome = "supported"`.
2. 7.1 ⇒ `inconclusive` với `reasons = ["G4_structure_control"]`.
3. 7.2 ⇒ `unsupported`, `n_fit == 0`, không có `statistic`.
4. `model = "fit"`: mô hình chỉ nhận `n_fit` dòng đầu; test dùng bộ đếm trong `fit` để khẳng định số dòng và **không** có dòng nào của `test`.
5. Đổi một dòng trong `test` **không** làm đổi `mu_ref`, `var_ref`, `tau` (chứng minh không fit trên test).
6. Hiệp phương sai suy biến (ví dụ mọi dòng giống nhau, `λ = 0`) ⇒ `unsupported("singular_covariance")`.
7. `n_test < min_test_rows` ⇒ `unsupported("insufficient_test_rows")`.
8. `reasons` theo đúng thứ tự G1..G4; mỗi cổng false sinh đúng một lý do.
9. Cùng fixture, cùng seed ⇒ cùng output từng byte.
10. `outcome` chỉ thuộc `{"supported","inconclusive","unsupported"}`.

## 9. Non-goals

- Không GMM/EM, không kernel density, không `numpy`.
- Không hiệu chỉnh đa kiểm định, không p-value chính xác.
- Không streaming/theo dõi drift qua thời gian.
- Không đánh giá trên dữ liệu latent thật.
