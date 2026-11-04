# GUIDE — Non-dominated sorting và crowding

## Bước 0 — Môi trường

```bash
mkdir 19_NONDOMINATED_SORT/work && cd 19_NONDOMINATED_SORT/work
uv init . -p 3.12 --lib
uv add --dev pytest
mkdir -p src/nsga2 tests
```

## Bước 1 — Định nghĩa trước khi code

Viết ra giấy:

- Miền giá trị: minimize.
- `a` chi phối `b` nếu `a` không tệ hơn ở mọi mục tiêu và tốt hơn ở ít nhất một.
- Vector bằng nhau: không chi phối.
- “Không bị chi phối” là quan hệ bộ phận: có cặp không so sánh được.

Nếu bạn không viết ra, rất dễ cài thành “tốt hơn ở mọi mục tiêu” (Pareto yếu) hoặc “tốt hơn ở một mục tiêu” (không phải Pareto).

## Bước 2 — Dùng chỉ số, không dùng `id()`

Nguồn dùng `id(ind)` làm khóa. Cách đó hoạt động nhưng có hai nhược điểm:

- Không tất định về mặt đọc hiểu (id là địa chỉ).
- Nếu cùng một object xuất hiện hai lần trong list, `id` trùng và logic rối.

Bài tập dùng `enumerate(population)` và mảng `dominated: list[list[int]]`, `count: list[int]`.

## Bước 3 — Tính quan hệ

```text
for i in range(n):
    for j in range(i+1, n):
        if dominates(pop[i], pop[j]):
            dominated[i].append(j); count[j] += 1
        elif dominates(pop[j], pop[i]):
            dominated[j].append(i); count[i] += 1
```

Chỉ duyệt `j > i` để không xét cặp hai lần. Nếu cả hai false, không làm gì.

Kiểm tra nhanh với 3 điểm: một điểm trội, hai điểm không so sánh được.

## Bước 4 — Kahn theo lớp

```text
fronts = []
current = [i for i in range(n) if count[i] == 0]
while current:
    current.sort()
    fronts.append(current)
    next_front = []
    for i in current:
        for j in dominated[i]:
            count[j] -= 1
            if count[j] == 0:
                next_front.append(j)
    current = next_front
```

- `current.sort()` đảm bảo thứ tự front theo chỉ số gốc.
- Không cần đánh dấu visited: mỗi node vào đúng một front khi count về 0.
- Nếu có chu trình (không thể với quan hệ chi phối), `fronts` sẽ thiếu node; kiểm tra tổng phần tử == n để phát hiện lỗi.

Gán rank sau khi có front:

```text
for r, front in enumerate(fronts):
    for i in front:
        population[i].rank = r
```

## Bước 5 — Crowding: đọc kỹ lỗi nguồn

Nguồn:

```text
if max_val == min_val or num_inds <= 2:
    return
```

Đặt trong vòng lặp mục tiêu. Hệ quả: nếu mục tiêu đầu tiên có mọi giá trị bằng nhau, hàm dừng và các mục tiêu sau không được xử lý.

Bài tập yêu cầu:

- `n <= 2` xử lý **một lần** trước vòng lặp.
- `hi == lo` → `continue`.

Viết:

```text
dist = [0.0] * n
if n <= 2:
    dist = [inf] * n
else:
    for m in range(num_objs):
        order = sorted(range(n), key=lambda i: (front[i].fitness[m], i))
        dist[order[0]] = inf
        dist[order[-1]] = inf
        lo = front[order[0]].fitness[m]
        hi = front[order[-1]].fitness[m]
        if hi == lo:
            continue
        for k in range(1, n - 1):
            i = order[k]
            dist[i] += (front[order[k+1]].fitness[m] - front[order[k-1]].fitness[m]) / (hi - lo)
```

Gán lại vào `individual.crowding_distance` sau khi tính xong (hoặc cập nhật trực tiếp; nếu cập nhật trực tiếp, nhớ reset về 0 trước).

Trả tuple theo thứ tự `front` ban đầu: `tuple(dist)`.

## Bước 6 — Không sắp xếp front

Nguồn gọi `front.sort(...)` trong vòng lặp, làm thay đổi thứ tự front. Bài tập yêu cầu dùng `order` (danh sách chỉ số) và không chạm `front`.

Kiểm thử: lưu `labels = [ind.label for ind in front]`, gọi, so lại.

## Bước 7 — Test

Nhóm:

1. Dominance: các cặp trong ví dụ 1.
2. Fronts: ví dụ 1.
3. Trùng vector: hai cá thể giống hệt cùng front.
4. Crowding: ví dụ 2, 3.
5. Hằng số đứng đầu (bẫy).
6. n=0,1,2.
7. Lỗi: NaN, inf, fitness rỗng, khác độ dài.
8. Không đổi thứ tự population/front.
9. Tính lại crowding không cộng dồn.

Gợi ý helper:

```text
def labels(fronts): return [[i.label for i in f] for f in fronts]
def dist(front): return tuple(i.crowding_distance for i in front)
```

## Bước 8 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from nsga2 import Individual, non_dominated_sort, crowding_distance
pop = [Individual((1,1),"A"), Individual((2,2),"B"), Individual((2,1),"C"),
       Individual((3,3),"D"), Individual((1,3),"E"), Individual((3,1),"F")]
fronts = non_dominated_sort(pop)
print([[i.label for i in f] for f in fronts])
print([i.rank for i in pop])
crowding_distance(fronts[1])
print([(i.label, i.crowding_distance) for i in fronts[1]])
PY
```

Kỳ vọng:

```text
[['A'], ['C', 'E'], ['B', 'F'], ['D']]
[0, 2, 1, 3, 1, 2]
[('C', inf), ('E', inf)]
```

Kiểm tra bẫy hằng:

```bash
uv run python - <<'PY'
from nsga2 import Individual, crowding_distance
f = [Individual((5,1)), Individual((5,2)), Individual((5,3))]
print(crowding_distance(f))
PY
```

Phải ra `(inf, 1.0, inf)`.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Mọi cá thể cùng front | `dominates` dùng `<` thay vì `<=` toàn bộ + một strict. |
| Không có front | `count` khởi tạo sai hoặc không giảm. |
| Thứ tự front đổi | Không sort `next_front` theo index. |
| Trùng bị tách front | Dùng `id` hoặc so sánh object. |
| Crowding sai khi mục tiêu hằng | `return` thay vì `continue`. |
| Crowding cộng dồn giữa các lần gọi | Không reset 0. |
| Front bị đảo | Dùng `front.sort`. |
| `inf` biến mất | Gán lại distance sau khi cộng đè lên `inf`. |
| NaN lan | Không validate. |
| Rank sai | Gán rank trong lúc duyệt thay vì sau khi có front. |

## Bước 10 — Mở rộng

- Tournament selection theo (rank, crowding).
- Hiệu chỉnh cho maximize bằng cách đảo dấu.
- Constrained NSGA-II với vi phạm ràng buộc.
- So sánh với `pymoo` (không bắt buộc).
- Vẽ front bằng matplotlib.

## Tự đánh giá

1. Vì sao vector bằng nhau không chi phối nhau?
2. Vì sao dùng chỉ số thay vì `id`?
3. Vì sao `hi == lo` phải `continue`?
4. Vì sao biên luôn `inf`, và điều đó ảnh hưởng chọn lọc thế nào?
