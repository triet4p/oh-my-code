# SPEC — Dynamic Time Warping có ràng buộc

## Mục tiêu hành vi

Căn hai chuỗi điểm nhiều chiều bằng DTW với chi phí điểm Euclidean, cửa sổ band, ngưỡng bước, và ngân sách ô. Trả về khoảng cách thô/đã chuẩn hóa, đường alignment, chi phí từng điểm trên đường, tóm tắt ma trận, và (tùy chọn) ma trận tích lũy.

## Kiểu

```python
from dataclasses import dataclass
from typing import Any, Literal
import numpy as np

Normalization = Literal["none", "path_length", "query_length", "reference_length"]

@dataclass(frozen=True, slots=True)
class DTWConfig:
    window: int | None = None
    max_step_distance: float | None = None
    normalization: Normalization = "path_length"
    max_cells: int = 2_000_000
    return_cost_matrix: bool = False

@dataclass(frozen=True, slots=True)
class DTWCostSummary:
    shape: tuple[int, int]
    finite_cells: int
    minimum: float
    maximum: float
    terminal_cost: float

@dataclass(frozen=True, slots=True)
class DTWResult:
    distance: float
    raw_distance: float
    path: tuple[tuple[int, int], ...]
    point_costs: tuple[float, ...]
    cost_summary: DTWCostSummary
    normalization: str
    geometry: str
    provenance: dict[str, Any]
    cost_matrix: np.ndarray | None = None

def compute_dtw(query, reference, *, config: DTWConfig | None = None) -> DTWResult
```

## Validate config

| Trường | Quy tắc | Lỗi |
|---|---|---|
| `window` | `None` hoặc `int` (không bool) `>= 0` | `ValueError` |
| `max_step_distance` | `None` hoặc số thực hữu hạn `>= 0` | `ValueError` |
| `normalization` | một trong 4 giá trị | `ValueError` |
| `max_cells` | `int` (không bool) `>= 1` | `ValueError` |
| `return_cost_matrix` | `bool` | `TypeError` |

## Validate dữ liệu

`query`, `reference` được chuyển bằng `np.asarray(..., dtype=np.float64)`:

- Phải là mảng 2D; nếu `ndim != 2` → `ValueError`.
- `shape[1] >= 1` (ít nhất một feature).
- `shape[0] >= 1` (không rỗng).
- Toàn bộ hữu hạn (`np.isfinite(...).all()`); NaN/inf → `ValueError`.
- Hai bên cùng số feature; nếu không → `ValueError`.
- `n_query * n_reference > max_cells` → `ValueError` **trước khi** cấp phát ma trận.

## Chi phí điểm

Với mỗi cặp `(i, j)` trong band:

- Nếu `window is not None` và `abs(i - j) > window`: để `inf`.
- Ngược lại `cost = np.linalg.norm(query[i] - reference[j])`.
- Nếu `max_step_distance is not None` và `cost > max_step_distance`: để `inf`.
- Ngược lại gán `cost`.

`max_step_distance = 0` chỉ cho phép các điểm giống hệt (khoảng cách 0).

## Tích lũy và tie-break

`accumulated` cùng shape, khởi tạo `inf`; `predecessor` `int8`, khởi tạo `-1`.

Duyệt `i` tăng, `j` tăng:

- `c = point_costs[i, j]`; nếu không hữu hạn → bỏ qua.
- `(0,0)`: `accumulated = c`, `predecessor = -1`.
- Ngược lại, xét các ô trước **nằm trong lưới**:
  - chéo `(i-1, j-1)` mã `0`
  - lên `(i-1, j)` mã `1`
  - trái `(i, j-1)` mã `2`
- Với mỗi ô trước có `accumulated` hữu hạn, ứng viên `= accumulated[prev] + c`.
- Chọn ứng viên nhỏ nhất; hòa thì chọn **mã nhỏ nhất** (chéo trước, rồi lên, rồi trái).
- Nếu không có ứng viên hữu hạn → giữ `inf`.
- Gán `accumulated[i,j]` và `predecessor[i,j] = mã`.

Quy tắc tie-break này là một phần của hợp đồng: nó ưu tiên tiến đồng thời trên cả hai chuỗi.

## Terminal và traceback

- `terminal = accumulated[n-1, m-1]`.
- Nếu không hữu hạn → `ValueError("DTW constraints leave no valid alignment path")`.
- Traceback từ `(n-1, m-1)`:
  - Thêm ô hiện tại.
  - Nếu `(0,0)` → dừng.
  - Theo `predecessor`: 0 → `(i-1,j-1)`, 1 → `(i-1,j)`, 2 → `(i,j-1)`.
  - `-1` trước khi tới `(0,0)` → `RuntimeError` (bất biến nội bộ bị vi phạm).
- Đảo ngược để path bắt đầu `(0,0)`, kết thúc `(n-1,m-1)`.
- `point_costs` của path = chi phí điểm tại từng ô, theo thứ tự path.

## Chuẩn hóa

`raw_distance = terminal`.

| `normalization` | Mẫu số |
|---|---|
| `none` | `1.0` |
| `path_length` | `len(path)` |
| `query_length` | `n` |
| `reference_length` | `m` |

`distance = raw_distance / denominator`. Mẫu số luôn `>= 1`.

## Tóm tắt

`DTWCostSummary`:

- `shape = accumulated.shape`.
- `finite_cells = số ô hữu hạn trong accumulated`.
- `minimum = min` các ô hữu hạn.
- `maximum = max` các ô hữu hạn.
- `terminal_cost = terminal`.

Có ít nhất một ô hữu hạn (ô terminal), nên min/max xác định.

## Kết quả

- `geometry = "euclidean"`, `provenance` gồm `query_length`, `reference_length`, `dim`, `window`, `max_step_distance`, `normalization`, `metric="l2"`, `geometry`.
- `cost_matrix` là **bản sao** của `accumulated` nếu `return_cost_matrix=True`, ngược lại `None`.

## Ví dụ 1 — Cơ bản

`query = [[0],[1],[2]]`, `reference = [[0],[2]]`, config mặc định (`path_length`).

Chi phí điểm:

| | r0=0 | r1=2 |
|---|---:|---:|
| q0=0 | 0 | 2 |
| q1=1 | 1 | 1 |
| q2=2 | 2 | 0 |

Tích lũy:

| | r0 | r1 |
|---|---:|---:|
| q0 | 0 | 2 |
| q1 | 1 | 1 (diag) |
| q2 | 3 | 1 (diag từ (1,0)) |

Terminal `1`; traceback: `(2,1) → (1,0) → (0,0)`.

Kết quả:

- `path = ((0,0), (1,0), (2,1))`
- `point_costs = (0.0, 1.0, 0.0)`
- `raw_distance = 1.0`
- `path_length = 3` → `distance = 1/3`
- `query_length` → `1/3`; `reference_length` → `1/2`; `none` → `1.0`.

## Ví dụ 2 — Band

Cùng dữ liệu, `window=0`: chỉ ô `i == j` được phép. `(0,0)` và `(1,1)` hữu hạn; `(2,1)` nằm ngoài band vì `|2-1| = 1 > 0` → terminal `inf` → `ValueError`.

`window=1`: toàn bộ ví dụ 1 nằm trong band, kết quả như trên.

## Ví dụ 3 — Ngưỡng bước

`query=[[0]]`, `reference=[[0],[2]]`, `max_step_distance=1.0`.

Chi phí: `(0,0)=0`; `(0,1)=2 > 1` → `inf`. Terminal `(0,1)` `inf` → `ValueError`.

## Ví dụ 4 — Tie-break chéo

`query = [[1],[2]]`, `reference = [[1],[2]]`.

Tại `(1,1)`, cả ba hướng đều cho tổng `0` (vì chi phí điểm bằng 0). Tie-break chọn chéo, path `((0,0),(1,1))`, `raw=0`, `path_length=2`.

Nếu implementation chọn “lên” hoặc “trái”, path sẽ dài hơn dù cùng chi phí 0. Đây là test phân biệt.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `query` 1 chiều, `reference` 1 chiều | hợp lệ, scalar distance |
| `query` rỗng | `ValueError` |
| `reference` rỗng | `ValueError` |
| Mảng 1D | `ValueError` |
| `shape=(3,0)` | `ValueError` |
| NaN trong query | `ValueError` |
| `inf` trong reference | `ValueError` |
| Khác số feature | `ValueError` |
| `window=-1` | `ValueError` |
| `window=True` | `ValueError` |
| `max_step_distance=-0.1` | `ValueError` |
| `max_step_distance=inf` | `ValueError` |
| `max_cells=0` | `ValueError` |
| `n*m > max_cells` | `ValueError`, không cấp phát |
| `normalization="Path_Length"` | `ValueError` |
| Không có đường hợp lệ | `ValueError` |
| `path` một ô (cả hai chuỗi dài 1) | `((0,0),)`, `raw=cost` |
| Điểm giống hệt | `raw=0`, `distance=0` |
| `return_cost_matrix=True` | matrix copy, `shape=(n,m)`, terminal khớp |
| Sửa `result.cost_matrix` | `result` khác không đổi (vì là bản sao độc lập) |
| `window` lớn hơn độ dài | tương đương không window |

## Tiêu chí nghiệm thu

1. Ví dụ 1 khớp path, point costs, raw, distance cho cả 4 normalization.
2. Ví dụ 2 (window 0) báo lỗi không có đường.
3. Ví dụ 3 (max_step) báo lỗi.
4. Ví dụ 4 chứng minh tie-break chéo (path 2 ô).
5. `max_cells` báo lỗi trước khi tạo mảng lớn (kiểm tra bằng `max_cells=1` trên 2×2).
6. Validation: 2D, rỗng, NaN, inf, khác chiều, config.
7. `cost_matrix` là bản sao; `finite_cells`, min/max, terminal đúng.
8. Không phụ thuộc thứ tự gọi; không dùng random.
9. `pytest -q` xanh.

## Non-goals

- Nhiều metric (cosine, Mahalanobis), hình học SO(3)/SE(3).
- FastDTW, pruning, band tùy biến phi tuyến.
- Batch nhiều cặp.
- Tính gradient/học.
- Trực quan hóa alignment.
