# 20 — DTW có cửa sổ, ngưỡng bước và ngân sách ô

## Mục tiêu

Tự cài đặt Dynamic Time Warping (DTW) cho hai chuỗi điểm nhiều chiều: tính ma trận chi phí, tìm alignment tối ưu với tie-break xác định, traceback đường đi, chuẩn hóa khoảng cách, và bảo vệ bộ nhớ bằng `max_cells`. Bài tập kết thúc lộ trình bằng một thuật toán có nhiều quyết định thiết kế ảnh hưởng trực tiếp đến kết quả.

## Giá trị học được

- DTW không chỉ là “khoảng cách”; nó là một **alignment** với ràng buộc bước.
- Cửa sổ (Sakoe–Chiba band) và ngưỡng bước là hai bộ lọc khác nhau: một giới hạn ô, một giới hạn giá trị.
- Tie-break phải được định nghĩa; nếu không, hai implementation đúng đều cho path khác nhau.
- Chuẩn hóa theo độ dài path/chuỗi thay đổi thang đo; phải chọn và ghi rõ.
- `max_cells` là guard trước khi cấp phát, không phải sau.
- Traceback cần predecessor; nếu chỉ giữ chi phí, không dựng lại được path.
- NaN/inf trong đầu vào phải bị chặn ở biên.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Khó**.
- Thời lượng gợi ý: 7–9 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `numpy`, `pytest`.
- Không cần GPU, không cần dữ liệu ngoài.

## Nguồn gốc

- Nguồn: `triet4p/latent-anything`, file `src/latent_anything/dtw.py`.
- URL chính xác: <https://github.com/triet4p/latent-anything/blob/main/src/latent_anything/dtw.py>

Hành vi quan sát được trong nguồn:

- `DTWConfig(window=None, max_step_distance=None, normalization="path_length", max_cells=2_000_000, return_cost_matrix=False)`.
- `__post_init__` từ chối `window < 0`, `max_step_distance < 0`, `normalization` ngoài `{none, path_length, reference_length, query_length}`, `max_cells < 1`.
- `_as_points`: chấp nhận `Trajectory` hoặc array; yêu cầu 2D, ít nhất một feature, toàn giá trị hữu hạn.
- `compute_dtw(query, reference, space, config=None)`:
  - Kiểm tra số chiều điểm khớp `space` và hai bên cùng chiều.
  - Từ chối chuỗi rỗng.
  - Từ chối nếu `n_query * n_reference > max_cells`.
  - Tính `point_costs` với cửa sổ `|i-j| <= window`; nếu vượt `max_step_distance` thì `inf`.
  - Với Euclidean, tối ưu theo hàng; ngược lại gọi `space.distance`.
  - DP: `accumulated` khởi tạo `inf`; ô `(0,0) = cost`; mỗi ô chọn min trong `(diag, up, left)` với tie-break theo thứ tự `(cost, code)` code 0/1/2; lưu predecessor `int8`.
  - Terminal `inf` → `ValueError("DTW constraints leave no valid alignment path")`.
  - Traceback từ `(n-1,m-1)` về `(0,0)`.
  - `point_costs` dọc path; `DTWCostSummary` gồm shape, finite_cells, min, max, terminal.
  - `distance = terminal / denominator`, `raw_distance = terminal`.
  - `provenance` gồm độ dài, window, max_step, dim, model, metadata.
  - `cost_matrix` chỉ trả khi `return_cost_matrix`.

## Phạm vi bài tập

Xây module `dtw`:

- `DTWConfig`, `DTWCostSummary`, `DTWResult`.
- `compute_dtw(query, reference, *, config=None)` với khoảng cách điểm Euclidean.
- Validation đầy đủ, tie-break, traceback, chuẩn hóa.
- Test với ví dụ tính tay và các trường hợp biên.

Không nằm trong phạm vi: nhiều metric hình học, GPU, batch, pruning nâng cao (FastDTW), học trọng số.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, tie-break, ví dụ số, lỗi.
- [GUIDE.md](GUIDE.md) — DP, traceback, kiểm thử, bẫy.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn dùng `space.distance` và hình học đa dạng; bài tập cố định Euclidean để tách thuật toán khỏi lớp không gian tiềm ẩn. Các trường `geometry`/`provenance` được giữ như metadata. Đây là đơn giản hóa có chủ đích, không phải hành vi đầy đủ của nguồn.
