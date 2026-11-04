# GUIDE 57 — Không gian latent đa hình học

## 1. Vì sao dict, không phải cây kế thừa

Tám hình học chia sẻ **giao diện** nhưng không chia sẻ **công thức**. Kế thừa sẽ tạo một lớp cha rỗng hoặc một chuỗi `if/elif` trong mỗi phương thức. Nguồn chọn "hàm chuyên biệt"; bài tập giữ đúng tinh thần đó:

```text
GEOMETRY_OPS[name] = (validate_fn, distance_fn, interpolate_fn)
```

`LatentSpace` chỉ giữ `geometry` và tra bảng. Thêm hình học thứ chín = thêm một dòng, không sửa lớp.

## 2. Cấu trúc

```text
src/
├── registry.py    # GEOMETRY_OPS, LatentSpace, lỗi
├── linear.py      # dot, norm, matmul, transpose, det, cholesky_solve
├── rotations.py   # so3 check, matrix<->quat, slerp
├── gaussian.py    # gaussian_3d/set
└── __main__.py
```

## 3. Thứ tự cài đặt

### Bước 1 — Tiện ích tuyến tính

Viết trước và test riêng: `dot`, `norm`, `sub`, `mat_mul`, `transpose`, `trace`, `det3`, `mat_vec`.

`det3` viết tay (khai triển theo hàng đầu) — không cần thư viện.

### Bước 2 — Từng hình học, từ dễ

Thứ tự gợi ý: `euclidean` → `unit_norm` → `gaussian_3d` → `gaussian_set` → `discrete_code` → `anisotropic` → `so3` → `se3`.

Mỗi hình học viết xong thì chạy ngay ví dụ tương ứng trong SPEC mục 4. Đừng cài hết rồi mới test.

### Bước 3 — Cholesky

Giải `Σ x = d` mà không cần nghịch đảo:

```text
L = cholesky(Σ)         # tam giác dưới, L Lᵀ = Σ
giải L y = d            # thay xuôi
giải Lᵀ x = y           # thay ngược
mahalanobis = sqrt(dot(d, x))
```

Kiểm tra xác định dương: phần tử chéo `L_ii` phải `> 0`; nếu gặp `<= 0` (hoặc NaN) ⇒ `NotPositiveDefinite`. Với ma trận gần suy biến, dùng ngưỡng nhỏ (`1e-12`) và ghi rõ.

### Bước 4 — SO(3)

Kiểm tra:

```text
RᵀR ≈ I  (mỗi phần tử |delta| <= 1e-6)
det(R) ≈ 1
```

Ma trận → quaternion: dùng phương pháp chọn phần tử chéo lớn nhất (Shepperd). Bốn nhánh; nhớ chuẩn hoá quaternion sau khi tính.

Quaternion → ma trận: công thức chuẩn với `w,x,y,z` đã chuẩn hoá.

Slerp:

```text
dot = q1·q2
nếu dot < 0: q2 = -q2; dot = -dot      # chọn đường ngắn
nếu dot > 0.9995: chuẩn hoá(q1 + t*(q2-q1))
ngược lại: θ = acos(dot); hệ số sin như SPEC
```

Thiếu bước đổi dấu, kết quả vẫn là ma trận quay nhưng đi "đường dài" — test 6 của SPEC (góc π/4) sẽ bắt.

### Bước 5 — SE(3)

Tách 12 số thành `R` (9) và `t` (3). Distance ghép hai thành phần bằng `sqrt(a² + b²)`; đây là metric tích (không phải geodesic đầy đủ của SE(3)) — ghi rõ trong docstring.

### Bước 6 — Registry và lỗi

```python
GEOMETRY_OPS = {name: (validate, distance, interpolate) for ...}
```

`LatentSpace.__init__` kiểm tra tên; lỗi nêu `sorted(GEOMETRY_OPS)`.

## 4. Cạm bẫy

- **Lerp ma trận quay**: kết quả không trực giao. Ở `t=0.5` giữa `I` và `Rz(90°)`, lerp cho ma trận có det ≠ 1; test 6 bắt.
- **Quên đổi dấu quaternion**: quỹ đạo dài, góc sai.
- **Chuẩn hoá quaternion sau slerp**: sai số tích luỹ; luôn chuẩn hoá trước khi chuyển về ma trận.
- **`acos` ngoài miền**: `(trace-1)/2` có thể là `1.0000000002`; luôn kẹp về `[-1,1]`.
- **Mahalanobis với `Σ` không đối xứng**: kiểm tra trước, đừng "đối xứng hoá" âm thầm.
- **`gaussian_set` không kiểm tra `N`**: index lỗi hoặc tính sai thầm lặng.
- **`discrete_code` nhận `bool`**: `True` là `int` trong Python; từ chối `type(x) is bool`.
- **`t` ngoài `[0,1]`**: nội suy vẫn "chạy" nhưng vô nghĩa; từ chối.
- **Sai thứ tự tham số Gauss**: `[x,y,z,scale,opacity,r,g,b]` — ghi thành hằng và dùng chung cho validate/distance/interpolate.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `euclidean_basic` | #1, #2 |
| `unit_norm_basic` | #3, #4; `NotUnitNorm` |
| `gaussian_3d` | #5 |
| `gaussian_set` | #6; `LengthMismatch` |
| `discrete` | #7, #8; `InvalidCode` |
| `anisotropic_identity` | #9; `NotPositiveDefinite` |
| `so3_distance` | #10 |
| `so3_interp` | #6 của mục tiêu; kết quả vẫn là ma trận quay |
| `se3_distance` | #11 |
| `antipodal` | `[1,0]`, `[-1,0]` ⇒ lỗi |
| `endpoints` | `t=0` ⇒ `a`, `t=1` ⇒ `b` |
| `registry` | đúng 8 khóa; lỗi nêu danh sách |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src list
python -m src distance --fixture fixtures/pair_so3.json
python -m src interpolate --fixture fixtures/pair_unit_norm.json --t 0.5
```

`list` phải in tám tên đã sắp. `distance` cho `1.5707963`. `interpolate` cho `[0.7071, 0.7071]`.

Kiểm tra kết quả nội suy SO(3) vẫn hợp lệ:

```bash
python -m src interpolate --fixture fixtures/pair_so3.json --t 0.5 > out.json
python -m src check --fixture out.json
```

Lệnh thứ hai phải in `{"ok": true}`.

## 7. Gợi ý

- Viết `assert_close_matrix(a, b, tol)` trong test; đừng so từng phần tử bằng `==`.
- Với Cholesky, test trên `[[4,2],[2,3]]` (xác định dương) và `[[1,2],[2,1]]` (không) trước khi dùng cho Mahalanobis.
- Với SO(3), test vòng: `R → quat → R` phải trả lại `R` trong `1e-9`.
- Nếu `distance` giữa một điểm và chính nó khác 0, lỗi thường ở chuẩn hoá hoặc kẹp `acos`.
- Đừng thêm `numpy` "cho nhanh"; mục đích là thấy phép toán.

## 8. Mở rộng

- **Ghép cặp Gauss**: dùng Hungarian hoặc tham lam theo khoảng cách; so với bản theo thứ tự.
- **Whiten/unwhiten**: cài `whiten_point` và `unwhiten_point`; test round-trip.
- **SO(3) log/exp**: cài `log(R)` trả vector 3 chiều; dùng để tính geodesic đầy đủ cho SE(3).
- **Hình học thứ chín**: thêm `hyperbolic` (Poincaré ball) với distance và nội suy riêng; chứng minh registry mở rộng không sửa lớp.
- **Chuẩn hoá đầu vào**: hàm `project(point)` chiếu về không gian hợp lệ (SO(3) gần nhất, chuẩn hoá vector) trước khi validate.
