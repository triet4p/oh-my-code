# GUIDE — Dynamic Time Warping có ràng buộc

## Bước 0 — Môi trường

```bash
mkdir 20_DTW_ALIGNMENT/work && cd 20_DTW_ALIGNMENT/work
uv init . -p 3.12 --lib
uv add numpy
uv add --dev pytest
mkdir -p src/dtw tests
```

## Bước 1 — Viết config trước

`DTWConfig` frozen, `__post_init__` kiểm tra:

- `window`: `isinstance(x, int) and not isinstance(x, bool)`; `>= 0`.
- `max_step_distance`: `int`/`float` không bool, `math.isfinite`, `>= 0`.
- `normalization` trong set.
- `max_cells`: int không bool, `>= 1`.
- `return_cost_matrix`: bool.

Tại sao kiểm tra `bool`? `True` là `1`; một window `True` gần như chắc chắn là lỗi.

## Bước 2 — Chuẩn hóa đầu vào

```text
def as_points(value, name):
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2: raise ValueError(...)
    if points.shape[0] == 0: raise ValueError(...)
    if points.shape[1] == 0: raise ValueError(...)
    if not np.isfinite(points).all(): raise ValueError(...)
    return points
```

`np.asarray` có thể copy; chấp nhận. Không dùng `np.matrix`.

Sau đó kiểm tra `shape[1]` bằng nhau.

## Bước 3 — Guard bộ nhớ

**Trước** khi `np.full((n, m), inf)`:

```text
if n * m > config.max_cells:
    raise ValueError(f"DTW cost matrix has {n*m} cells; max_cells={config.max_cells}")
```

Kiểm tra này phải đứng trước mọi cấp phát lớn. Test bằng `2×2` với `max_cells=1`; nếu code cấp phát trước, test vẫn qua nhưng bài học sai. Có thể test bằng cách monkeypatch `np.full` để đếm, hoặc chỉ tin thứ tự code.

## Bước 4 — Chi phí điểm

Tạo `np.full((n, m), np.inf)`.

Với mỗi `i`:

- `start = 0 if window is None else max(0, i - window)`
- `stop = m if window is None else min(m, i + window + 1)`
- `costs = np.linalg.norm(reference[start:stop] - query[i], axis=1)`
- Nếu `max_step_distance` khác None: `costs = np.where(costs <= max_step, costs, np.inf)`
- Gán vào `point_costs[i, start:stop]`.

Cách vector hóa theo hàng đúng cho Euclidean và nhanh hơn vòng lặp đôi. Nếu làm vòng lặp đôi để dễ hiểu, vẫn đúng; ghi rõ.

## Bước 5 — DP ba hướng

Viết vòng lặp đôi. Với mỗi ô:

```text
c = point_costs[i, j]
if not np.isfinite(c): continue
if i == 0 and j == 0:
    acc[i, j] = c
    continue
best_cost = inf
best_code = -1
if i > 0 and j > 0 and np.isfinite(acc[i-1, j-1]):
    best_cost = acc[i-1, j-1]; best_code = 0
if i > 0 and np.isfinite(acc[i-1, j]):
    cand = acc[i-1, j]
    if cand < best_cost or (cand == best_cost and 1 < best_code):
        best_cost = cand; best_code = 1
if j > 0 and np.isfinite(acc[i, j-1]):
    cand = acc[i, j-1]
    if cand < best_cost or (cand == best_cost and 2 < best_code):
        best_cost = cand; best_code = 2
if best_code >= 0:
    acc[i, j] = c + best_cost
    pred[i, j] = best_code
```

Cẩn thận với `best_code == -1` khi so `1 < best_code`; xử lý bằng cách kiểm tra `best_code >= 0` trước, hoặc khởi tạo `best_code = 99`.

Cách gọn hơn: tạo list `candidates` các `(acc_prev, code, di, dj)` chỉ với ô hữu hạn, rồi `min(candidates, key=lambda x: (x[0], x[1]))`. Dễ đọc hơn và ít lỗi tie-break.

Tie-break theo **mã**, không theo tọa độ. Chéo luôn thắng khi hòa.

## Bước 6 — Traceback

```text
path = []
i, j = n-1, m-1
while True:
    path.append((i, j))
    if i == 0 and j == 0: break
    code = pred[i, j]
    if code == 0: i, j = i-1, j-1
    elif code == 1: i -= 1
    elif code == 2: j -= 1
    else: raise RuntimeError(...)
path.reverse()
```

Kiểm tra `path[0] == (0,0)` và `path[-1] == (n-1,m-1)`.

Chi phí path: `tuple(float(point_costs[i,j]) for i,j in path)`.

## Bước 7 — Chuẩn hóa

```text
denominator = {
    "none": 1.0,
    "path_length": float(len(path)),
    "query_length": float(n),
    "reference_length": float(m),
}[normalization]
distance = terminal / denominator
```

Không dùng `len(path)` cho `query_length`; dễ nhầm.

## Bước 8 — Tóm tắt

```text
finite = accumulated[np.isfinite(accumulated)]
summary = DTWCostSummary(
    shape=accumulated.shape,
    finite_cells=int(finite.size),
    minimum=float(finite.min()),
    maximum=float(finite.max()),
    terminal_cost=float(terminal),
)
```

`finite` không rỗng vì terminal hữu hạn.

## Bước 9 — Cost matrix copy

```text
matrix = accumulated.copy() if config.return_cost_matrix else None
```

Nếu trả `accumulated` trực tiếp, người dùng sửa sẽ ảnh hưởng kết quả (dù dataclass frozen, numpy mutable). Test: lưu `before = result.cost_matrix.copy()`, sửa `result.cost_matrix[0,0] = 999`, kiểm tra `result.cost_summary` không đổi; nhưng để chứng minh copy độc lập, cần so với một lần gọi khác.

## Bước 10 — Test

1. Ví dụ 1: so path, point_costs, raw, distance 4 chế độ.
2. Window 0 → lỗi; window 1 → như ví dụ 1.
3. Max step → lỗi.
4. Tie-break: path 2 ô cho chuỗi giống hệt.
5. `max_cells`: 2×2 với 1 → lỗi.
6. Validation: mảng 1D, rỗng, NaN, inf, khác chiều, config xấu.
7. `return_cost_matrix`: shape, terminal, finite_cells, min/max.
8. `normalization="none"`.
9. Một ô: query [[5]], ref [[2]] → path ((0,0)), raw 3, distance 3.

Gợi ý dùng `np.testing.assert_allclose` cho float.

## Bước 11 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
import numpy as np
from dtw import DTWConfig, compute_dtw
r = compute_dtw([[0],[1],[2]], [[0],[2]])
print(r.path, r.point_costs, r.raw_distance, r.distance)
r2 = compute_dtw([[1],[2]], [[1],[2]], config=DTWConfig(normalization="none"))
print(r2.path, r2.raw_distance, r2.distance)
PY
```

Kỳ vọng:

```text
((0, 0), (1, 0), (2, 1)) (0.0, 1.0, 0.0) 1.0 0.3333333333333333
((0, 0), (1, 1)) 0.0 0.0
```

Nếu path ví dụ 1 là `((0,0),(1,1),(2,1))`, tie-break của bạn chọn “lên” ở ô `(2,1)` thay vì chéo. Cả hai đều chi phí 1, nhưng hợp đồng yêu cầu chéo.

Kiểm tra window:

```bash
uv run python -c "from dtw import *; compute_dtw([[0],[1],[2]], [[0],[2]], config=DTWConfig(window=0))"
```

Phải ném `ValueError` với thông điệp không có đường.

## Bước 12 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Terminal inf dù có chi phí | Band quá hẹp hoặc max_step quá nhỏ. |
| Path không bắt đầu `(0,0)` | Traceback dừng sai hoặc đảo hai lần. |
| Path dài hơn cần thiết khi hòa | Tie-break không ưu tiên chéo. |
| `raw` khác tổng `point_costs` | Traceback lấy sai ô hoặc cộng thừa. |
| `distance` lệch | Dùng nhầm độ dài chuẩn hóa. |
| `finite_cells` sai | Đếm `point_costs` thay vì `accumulated`. |
| `max_cells` không chặn | Kiểm tra sau khi `np.full`. |
| NaN lọt | `np.isfinite` chỉ kiểm tra sau khi đã tính. |
| Sửa matrix ảnh hưởng kết quả | Không copy. |
| Window off-by-one | `stop = i + window` thay vì `+ window + 1`. |
| Nhầm `abs(i-j) > window` | Dùng `>=` làm mất biên. |

## Bước 13 — Mở rộng

- Thêm metric cosine.
- Thêm `max_cells` theo band thực tế (số ô khả dụng) thay vì n×m.
- FastDTW xấp xỉ.
- Batch nhiều cặp với vector hóa.
- Trả alignment dưới dạng cặp điểm gốc.
- Trực quan hóa ma trận và path.

## Tự đánh giá

1. Vì sao tie-break phải là một phần của spec?
2. Vì sao `max_step_distance` và `window` không thay thế nhau?
3. Vì sao `path_length` normalization có thể làm distance nhỏ hơn?
4. Vì sao phải kiểm tra `max_cells` trước khi cấp phát?
