# SPEC 57 — Không gian latent đa hình học

## 1. Giao diện

```text
LatentSpace(geometry: str, *, codebook_size: int | None = None, dim: int | None = None)
    geometry: str
    validate(point) -> None
    distance(a, b) -> float
    interpolate(a, b, t: float) -> point
```

`t` trong `[0, 1]`; ngoài miền ⇒ `InvalidT`.

Registry:

```text
GEOMETRY_OPS = {
  "euclidean": (validate_euclidean, distance_euclidean, interpolate_euclidean),
  "unit_norm": ...,
  "gaussian_set": ...,
  "gaussian_3d": ...,
  "discrete_code": ...,
  "anisotropic": ...,
  "so3": ...,
  "se3": ...,
}
```

`GEOMETRY_OPS.keys()` phải bằng đúng tám tên của nguồn. Không có lớp con nào cho hình học.

## 2. Biểu diễn và kiểm tra

### 2.1 `euclidean`

- Điểm: `list[float]`, độ dài `d >= 1`.
- Nếu `dim` được cấu hình, độ dài phải bằng `dim`.
- `distance(a,b) = sqrt(Σ (a_i - b_i)²)`.
- `interpolate = a + t*(b - a)`.

### 2.2 `unit_norm`

- Điểm: `list[float]`, độ dài `d >= 1`, `| ||x|| - 1 | <= 1e-6`; sai ⇒ `NotUnitNorm(norm)`.
- `distance(a,b) = 1 - Σ a_i*b_i` (vì cả hai đã chuẩn hoá).
- `interpolate = slerp`:

```text
c = dot(a,b) kẹp về [-1,1]
θ = acos(c)
nếu sin θ <= 1e-9:
    nếu c > 0: trả a
    ngược lại: raise AntipodalInterpolation
trả (sin((1-t)θ)/sin θ) * a + (sin(tθ)/sin θ) * b
```

### 2.3 `gaussian_3d`

- Điểm: đúng 8 số theo thứ tự `[x, y, z, scale, opacity, r, g, b]` (ba đầu là `position`, sau là `scale`, `opacity`, `color`).
- `distance = sqrt( ||Δpos||² + Δscale² + Δopacity² + ||Δcolor||² )`.
- `interpolate`: tuyến tính từng thành phần.

### 2.4 `gaussian_set`

- Điểm: `list` gồm `N >= 1` phần tử, mỗi phần tử là một `gaussian_3d` (8 số).
- Hai điểm phải cùng `N`; khác ⇒ `LengthMismatch`.
- `distance = (1/N) * Σ_{i=1..N} dist_gaussian(g_i, g'_i)` — **theo thứ tự**, không ghép cặp tối ưu.
- `interpolate`: từng cặp theo thứ tự.

### 2.5 `discrete_code`

- Điểm: `list[int]`, độ dài `d >= 1`; mỗi giá trị trong `[0, codebook_size)`; `codebook_size >= 2`.
- Sai miền ⇒ `InvalidCode(index, value)`.
- `distance = số vị trí khác nhau` (Hamming).
- `interpolate`: với mỗi vị trí, nếu `a_i == b_i` giữ nguyên; ngược lại `t < 0.5` ⇒ `a_i`, `t >= 0.5` ⇒ `b_i`.

### 2.6 `anisotropic`

- Điểm: `{"mean": [..d..], "cov": [[..d..] x d]}` (object) hoặc cặp `[mean, cov]` — chọn một dạng và ghi rõ; SPEC dùng object.
- `cov` phải đối xứng (`|c_ij - c_ji| <= 1e-9`), đường chéo dương, và xác định dương (kiểm tra bằng Cholesky tự viết); sai ⇒ `NotPositiveDefinite`.
- `distance(a,b)`: dùng `Σ = (cov_a + cov_b) / 2` (phải xác định dương; nếu không ⇒ `NotPositiveDefinite`), `d = a.mean - b.mean`, trả `sqrt(dᵀ Σ⁻¹ d)`.
- `interpolate`: `mean` tuyến tính; `cov = (1-t)*cov_a + t*cov_b`.

### 2.7 `so3`

- Điểm: đúng 9 số, ma trận 3×3 row-major; phải trực giao (`RᵀR = I` trong `1e-6`) và `det(R) = 1` trong `1e-6`; sai ⇒ `NotRotation`.
- `distance = acos( clamp((trace(Raᵀ Rb) - 1) / 2, -1, 1) )`.
- `interpolate`: chuyển cả hai sang quaternion (chọn dấu sao cho `dot >= 0`), slerp quaternion, chuyển lại ma trận.

### 2.8 `se3`

- Điểm: đúng 12 số, `[R(9), t(3)]`.
- Phần `R` phải là ma trận quay như 2.7.
- `distance = sqrt( ||t_a - t_b||² + θ² )` với `θ` là góc quay như 2.7.
- `interpolate`: `R` theo slerp SO(3); `t` tuyến tính.

## 3. Lỗi

| Điều kiện | Lỗi |
|---|---|
| `geometry` không thuộc tám tên | `UnknownGeometry(name, available=sorted(...))` |
| sai độ dài | `InvalidShape(geometry, expected, got)` |
| phần tử không phải số hữu hạn | `NonFiniteValue(index)` |
| `unit_norm` sai chuẩn | `NotUnitNorm(norm)` |
| `anisotropic` không đối xứng/không xác định dương | `NotPositiveDefinite` |
| `so3`/`se3` không trực giao hoặc det ≠ 1 | `NotRotation(reason)` |
| `discrete_code` ngoài miền | `InvalidCode(index, value)` |
| `gaussian_set` khác số lượng | `LengthMismatch(got_a, got_b)` |
| `t` ngoài `[0,1]` | `InvalidT(t)` |
| slerp gặp hai vector đối cực | `AntipodalInterpolation` |
| `codebook_size` thiếu khi `geometry == "discrete_code"` | `MissingCodebook` |

## 4. Ví dụ số (dùng trong test)

| # | Hình học | Đầu vào | Kỳ vọng |
|---|---|---|---|
| 1 | euclidean | `[0,0]`, `[3,4]` | `5.0` |
| 2 | euclidean | interp `[0,0]`,`[4,8]`, `t=0.25` | `[1.0, 2.0]` |
| 3 | unit_norm | `[1,0]`, `[0,1]` | `1.0` |
| 4 | unit_norm | interp `[1,0]`,`[0,1]`, `t=0.5` | `[0.70710678, 0.70710678]` |
| 5 | gaussian_3d | `[0,0,0,1,1,1,1,1]`, `[1,0,0,1,1,1,1,1]` | `1.0` |
| 6 | gaussian_set | hai điểm 1 Gauss như #5 | `1.0` |
| 7 | discrete_code | `[0,1,2]`, `[0,2,2]` (`codebook=3`) | `1.0` |
| 8 | discrete_code | interp #7 với `t=0.5` | `[0,2,2]` |
| 9 | anisotropic | `Σ = I`, mean `[0,0]` và `[3,4]` | `5.0` |
| 10 | so3 | `I` và `Rz(90°)`, xem 4.1 | `1.5707963` |
| 11 | se3 | cùng `R`, `t=[1,0,0]` và `[0,0,0]` | `1.8621` (xem 4.2) |

### 4.1 Ma trận quay `Rz(90°)`

Row-major: `[0, -1, 0, 1, 0, 0, 0, 0, 1]`.

`trace(Iᵀ R) = trace(R) = 0 + 0 + 1 = 1` ⇒ `(1-1)/2 = 0` ⇒ `acos(0) = π/2`.

### 4.2 SE(3)

`θ = π/2`, `||Δt|| = 1` ⇒ `sqrt(1 + (π/2)²) = sqrt(1 + 2.4674011) = sqrt(3.4674011) = 1.8620959`.

Sai số cho phép `1e-6` cho các giá trị trên (trừ #11 dùng `1e-6`).

## 5. CLI

| Lệnh | In ra |
|---|---|
| `python -m src list` | tám tên, sắp tăng |
| `python -m src check --fixture fixtures/points_so3.json` | `{"ok": true}` hoặc lỗi |
| `python -m src distance --fixture fixtures/pair_so3.json` | `{"distance": 1.5707963}` |
| `python -m src interpolate --fixture fixtures/pair_unit_norm.json --t 0.5` | điểm đã nội suy |

Output JSON, khóa sắp khi in; lỗi có `{"error": {"code": "...", "message": "..."}}` và mã thoát `2`.

## 6. Tiêu chí chấp nhận

1. Mười một dòng bảng mục 4 đúng (dung sai `1e-6`).
2. `GEOMETRY_OPS.keys()` đúng tám tên; `UnknownGeometry` nêu danh sách đã sắp.
3. `unit_norm` từ chối `[1,1]` với `NotUnitNorm(1.4142…)`.
4. `anisotropic` từ chối `cov = [[1,2],[2,1]]` (không xác định dương) với `NotPositiveDefinite`.
5. `so3` từ chối `[1,0,0, 0,1,0, 0,0,0.9]` với `NotRotation`.
6. Nội suy `so3` tại `t=0.5` giữa `I` và `Rz(90°)` cho góc `π/4` so với `I` (kiểm tra bằng `distance(I, kết quả) ≈ 0.7853982`) và ma trận kết quả vẫn là ma trận quay.
7. Nội suy `unit_norm` đối cực (`[1,0]`, `[-1,0]`) ⇒ `AntipodalInterpolation`.
8. `gaussian_set` khác `N` ⇒ `LengthMismatch`.
9. `interpolate` tại `t=0` trả điểm `a` (trong dung sai), tại `t=1` trả điểm `b`.
10. Hai lần chạy cho cùng output JSON.

## 7. Non-goals

- Không `numpy`/`torch`; không GPU; không tối ưu.
- Không ghép cặp tối ưu cho `gaussian_set`.
- Không học biểu diễn, không giảm chiều, không lưu trữ.
