# SPEC — Non-dominated sorting và crowding distance

## Mục tiêu hành vi

Cho một quần thể với vector mục tiêu cần **cực tiểu hóa**, phân thành các front không bị chi phối và tính crowding distance trong từng front. Kết quả phải xác định, không phụ thuộc thứ tự duyệt nội bộ, không làm đổi thứ tự mảng đầu vào, và xử lý đúng vector trùng nhau.

## Kiểu

```python
from dataclasses import dataclass, field

@dataclass
class Individual:
    fitness: tuple[float, ...]
    label: str = ""
    rank: int = -1
    crowding_distance: float = 0.0

    def __post_init__(self) -> None:
        ...
```

Quy ước: mọi mục tiêu đều **minimize**. Không có mục tiêu maximize trong bài này.

`__post_init__`:

- `fitness` phải là tuple (chấp nhận list? Không: yêu cầu tuple để tránh mutation) có ít nhất 1 phần tử.
- Mọi giá trị là `int`/`float` thật (không bool), hữu hạn (`math.isfinite`).
- Không ép kiểu; giữ nguyên giá trị số.

## API

```python
def dominates(a: Individual, b: Individual) -> bool: ...

def non_dominated_sort(population: list[Individual]) -> list[list[Individual]]: ...

def crowding_distance(front: list[Individual]) -> tuple[float, ...]: ...

def assign_crowding(fronts: list[list[Individual]]) -> None: ...
```

## `dominates`

`a` chi phối `b` khi:

- Với mọi `i`: `a.fitness[i] <= b.fitness[i]`.
- Tồn tại ít nhất một `j`: `a.fitness[j] < b.fitness[j]`.

Nếu hai vector bằng nhau, cả hai chiều đều `False`.

Nếu độ dài fitness khác nhau → `ValueError` (không so sánh được).

## `non_dominated_sort`

1. `population` rỗng → `[]`.
2. Kiểm tra mọi cá thể cùng số mục tiêu; khác → `ValueError`.
3. Dùng **chỉ số** (0..n-1), không dùng `id()`; hai cá thể khác nhau có thể có cùng nội dung.
4. Tính:
   - `domination_count[i]` = số cá thể chi phối `i`.
   - `dominated[i]` = danh sách chỉ số bị `i` chi phối.
5. Front 0 = các `i` có count 0, theo chỉ số tăng dần.
6. Với mỗi front hiện tại, với từng `i` trong front (theo thứ tự), giảm count của các `j` trong `dominated[i]`; nếu về 0, đưa `j` vào front kế.
7. Front kế phải được sắp theo chỉ số tăng dần trước khi gán rank (để không phụ thuộc thứ tự duyệt).
8. Gán `individual.rank = chỉ số front` (0-based).
9. Lặp đến khi không còn front mới.
10. Trả `list[list[Individual]]`; mỗi front giữ thứ tự chỉ số gốc tăng dần.

Độ phức tạp `O(n²·m)`; chấp nhận cho bài học.

Không được sắp xếp lại `population`. Có thể đặt `rank` trên cá thể.

## `crowding_distance`

1. `front` rỗng → trả `()`.
2. `n = len(front)`.
3. Khởi tạo mọi `crowding_distance = 0.0`.
4. Nếu `n <= 2`: gán tất cả `inf`, trả tuple `(inf, ..., inf)`.
5. Với mỗi mục tiêu `m`:
   - `order = sorted(range(n), key=lambda i: (front[i].fitness[m], i))`.
   - Đặt `front[order[0]].crowding_distance = inf` và `front[order[-1]].crowding_distance = inf`.
   - `lo = front[order[0]].fitness[m]`, `hi = front[order[-1]].fitness[m]`.
   - Nếu `hi == lo`: **bỏ qua mục tiêu này, tiếp tục mục tiêu kế** (không `return`).
   - Với `k` từ 1 đến `n-2`:
     - `i = order[k]`, `prev = order[k-1]`, `next = order[k+1]`.
     - `front[i].crowding_distance += (front[next].fitness[m] - front[prev].fitness[m]) / (hi - lo)`.
6. Trả tuple distance theo **thứ tự ban đầu của `front`**.
7. Không sắp xếp lại `front`.

`inf + x = inf`; biên giữ nguyên vô cực.

## `assign_crowding`

Gọi `crowding_distance` cho từng front; bỏ qua giá trị trả về.

## Ví dụ 1 — Phân tầng

Quần thể (minimize 2 mục tiêu), theo thứ tự:

| idx | label | fitness |
|---:|---|---|
| 0 | A | (1, 1) |
| 1 | B | (2, 2) |
| 2 | C | (2, 1) |
| 3 | D | (3, 3) |
| 4 | E | (1, 3) |
| 5 | F | (3, 1) |

Kết quả:

| Front | Thành viên (theo idx) | rank |
|---|---|---:|
| 0 | A (0) | 0 |
| 1 | C (2), E (4) | 1 |
| 2 | B (1), F (5) | 2 |
| 3 | D (3) | 3 |

Giải thích ngắn: A chi phối tất cả; C chi phối B, D, F; E chi phối D; B và F không so sánh được; D bị nhiều cá thể chi phối.

## Ví dụ 2 — Crowding 3 điểm

`front = [(1,5), (2,3), (4,1)]` (theo thứ tự này).

Mục tiêu 0: order `[0,1,2]`; biên 0,2 = inf; giữa: `(4-1)/(4-1) = 1`.
Mục tiêu 1: order `[2,1,0]`; biên 2,0 = inf; giữa: `(5-1)/(5-1) = 1`.

Kết quả distance theo thứ tự ban đầu: `(inf, 2.0, inf)`.

## Ví dụ 3 — Mục tiêu hằng (bẫy nguồn)

`front = [(5,1), (5,2), (5,3)]`.

- Mục tiêu 0: `hi == lo == 5` → bỏ qua.
- Mục tiêu 1: order `[0,1,2]`; biên inf; giữa `(3-1)/(3-1) = 1`.

Kết quả: `(inf, 1.0, inf)`.

Nếu làm theo nguồn (dừng khi `max == min`), mục tiêu 0 dừng toàn hàm và điểm giữa nhận `0.0`; đó là lỗi bài tập yêu cầu sửa.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Population rỗng | `[]` |
| Một cá thể | một front, distance `(inf,)` |
| Hai cá thể không so sánh được | cùng front; distance cả hai `inf` |
| Hai cá thể giống hệt | cùng front; cả hai `inf` |
| Mọi fitness giống nhau, n=5 | một front; distance biên `inf` theo từng mục tiêu, giữa `0.0` (vì range 0 và không có mục tiêu nào đóng góp) |
| Fitness khác độ dài | `ValueError` |
| Fitness NaN/inf | `ValueError` khi tạo |
| Fitness rỗng | `ValueError` |
| Front rỗng | `()` |
| Front 2 phần tử | cả hai `inf`, bất kể giá trị |
| Mục tiêu hằng đứng đầu | vẫn xử lý mục tiêu sau |
| Trùng fitness trong một mục tiêu | sort theo index; khoảng cách có thể 0 |
| Gọi lại `non_dominated_sort` | cùng kết quả; rank ghi đè |
| Gọi `crowding_distance` hai lần | giá trị được tính lại từ 0, không cộng dồn |
| `front` bị đảo trước khi gọi | kết quả tương ứng thứ tự mới; không tự sắp |

## Tiêu chí nghiệm thu

1. Ví dụ 1 cho đúng 4 front và thành viên.
2. Ví dụ 2 cho `(inf, 2.0, inf)`.
3. Ví dụ 3 cho `(inf, 1.0, inf)` (bắt lỗi dừng sớm).
4. Vector trùng nằm cùng front.
5. `dominates(a, a) == False`.
6. Không thay đổi thứ tự `population`; chỉ `rank` thay đổi.
7. Không thay đổi thứ tự `front` khi tính crowding.
8. Kiểm tra NaN/inf/độ dài.
9. `pytest -q` xanh.

## Non-goals

- Tournament selection, crossover, mutation.
- Tối ưu đa mục tiêu thực tế.
- Vẽ Pareto front.
- Tăng tốc bằng NumPy hoặc thuật toán `O(n log n)`.
- Xử lý ràng buộc (constrained NSGA-II).
