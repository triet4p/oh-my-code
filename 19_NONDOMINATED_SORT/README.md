# 19 — Non-dominated sorting và crowding distance (NSGA-II)

## Mục tiêu

Tự cài đặt hai viên gạch của NSGA-II: phân tầng các cá thể theo quan hệ không bị chi phối (non-dominated sorting), và tính khoảng cách chen chúc (crowding distance) trong từng tầng. Bài tập rèn định nghĩa toán học chính xác, xử lý trùng lặp, thứ tự tất định, và sửa một lỗi dừng sớm trong nguồn.

## Giá trị học được

- “Không bị chi phối” là quan hệ thứ tự bộ phận, không phải toàn phần: nhiều cá thể không so sánh được.
- Phân tầng là bài toán đồ thị: đếm bậc vào, xử lý theo lớp (Kahn) thay vì đệ quy.
- Hai vector giống hệt không chi phối nhau; chúng cùng tầng.
- Crowding distance cần chuẩn hóa theo từng mục tiêu; biên là vô cực.
- Nếu một mục tiêu có mọi giá trị bằng nhau, đóng góp của nó là 0, **không** phải dừng toàn bộ.
- Sắp xếp trong hàm không được làm thay đổi thứ tự mảng đầu vào.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Khó**.
- Thời lượng gợi ý: 5–7 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- Không cần thư viện ngoài, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/itapia`, file `backend/evo_worker/app/algorithms/dominance.py`.
- URL chính xác: <https://github.com/triet4p/itapia/blob/main/backend/evo_worker/app/algorithms/dominance.py>

Hành vi quan sát được trong nguồn:

- `non_dominated_sorting(inds, dominate_comparator)`:
  - `domination_counts = {id(ind): 0}`, `dominated_sets = {id(ind): []}`, `fronts = [[]]`, `ind_map = {id(ind): ind}`.
  - Duyệt mọi cặp `i < j`; nếu `comparator(p, q)` thì thêm `q` vào `dominated_sets[p]` và tăng count của `q`; ngược lại nếu `comparator(q, p)` thì làm ngược.
  - Front đầu gồm các count 0, gán `rank = 0`.
  - Vòng lặp: với mỗi phần tử front hiện tại, giảm count của các phần tử bị nó chi phối; count về 0 thì vào front kế, gán `rank = front_idx + 1`.
  - Dừng khi front kế rỗng.
- `crowding_distance_assignment(front)`:
  - Nếu rỗng → return.
  - `num_inds`, `num_objs` từ `front[0].fitness`.
  - Gán mọi `crowding_distance = 0.0`.
  - Với từng mục tiêu `m`: `front.sort(key=lambda ind: ind.fitness[m])` (sắp tại chỗ), lấy min/max, gán hai biên `inf`; nếu `max == min` hoặc `num_inds <= 2` → **return** (dừng toàn hàm); ngược lại cộng `(f[i+1]-f[i-1])/(max-min)` cho các điểm giữa.
- Nguồn không kiểm tra NaN/inf, không đảm bảo thứ tự ổn định, và làm thay đổi thứ tự `front` sau khi gọi.

## Phạm vi bài tập

Xây module `nsga2`:

- `Individual` với `fitness: tuple[float, ...]`, `rank`, `crowding_distance`, `label`.
- `dominates(a, b)`.
- `non_dominated_sort(population)`.
- `crowding_distance(front)`.
- `assign_crowding(fronts)`.
- Kiểm tra dữ liệu, xử lý trùng, thứ tự xác định.

Không nằm trong phạm vi: lai ghép, đột biến, chọn lọc tournament, tối ưu thực tế, vẽ Pareto front.

## Liên kết

- [SPEC.md](SPEC.md) — định nghĩa, thuật toán, ví dụ số, tiêu chí.
- [GUIDE.md](GUIDE.md) — Kahn, crowding, bẫy, test.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập giữ thuật toán và công thức, nhưng:

- Sửa lỗi `return` sớm khi một mục tiêu có range 0.
- Không sắp xếp mảng `front` của người gọi.
- Thêm kiểm tra NaN/inf và chiều dài fitness.
- Thêm thứ tự xác định trong front.

Đây là thiết kế của bài tập; không tuyên bố nguồn có các hành vi đã sửa.
