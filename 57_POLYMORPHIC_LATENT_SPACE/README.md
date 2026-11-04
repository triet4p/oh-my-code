# 57 — Không gian latent đa hình học

## Mục tiêu

Một lớp `LatentSpace` duy nhất phục vụ **tám hình học** khác nhau, mỗi hình học có hàm `validate / distance / interpolate` tập trung riêng — không có cây kế thừa, chỉ có bảng tra.

1. Tám tên: `euclidean`, `unit_norm`, `gaussian_set`, `gaussian_3d`, `discrete_code`, `anisotropic`, `so3`, `se3`.
2. Kiểm tra hình dạng và ràng buộc riêng: chuẩn hoá đơn vị, ma trận trực giao, ma trận xác định dương, mã rời rạc.
3. Khoảng cách đúng ngữ nghĩa từng hình học (Mahalanobis, góc quay, Hamming, khoảng cách Gauss).
4. Nội suy đúng ngữ nghĩa: tuyến tính, slerp trên mặt cầu, slerp trên SO(3), Hamming-snap.
5. Tên lạ ⇒ lỗi kèm danh sách tám tên đã sắp.

## Giá trị

- Đây là bài tập về **dispatch bằng dữ liệu**: một dict ánh xạ tên → ba hàm, thay vì tám lớp con. Bạn thấy rõ khi nào kế thừa là thừa.
- Mỗi hình học có ràng buộc toán học riêng; kiểm tra chúng (trực giao, xác định dương) là kỹ năng dùng lại ở mọi hệ embedding hình học.
- Nội suy là nơi dễ "gần đúng": lerp hai ma trận quay không cho ma trận quay. Bài tập buộc bạn dùng slerp và kiểm tra kết quả vẫn nằm trong không gian.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`math`) |
| Độ khó | Khó |
| Điều kiện | Đại số tuyến tính cơ bản, ma trận quay, phân rã Cholesky, số phức/quaternion |
| Runtime | Không mạng, không GPU, không `numpy`/`torch` |
| Thời lượng gợi ý | 12–14 giờ |

## Nguồn gốc

- Repo: `triet4p/latent-anything` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/latent-anything/blob/main/src/latent_anything/latent_space.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `_GEOMETRIES = frozenset({"euclidean", "unit_norm", "gaussian_set", "gaussian_3d", "discrete_code", "anisotropic", "so3", "se3"})`.
  - `_build_gaussian_layout` dùng `_GAUSSIAN_PARAM_NAMES = ("position", "scale", "opacity", "color")`.
  - Import các hàm chuyên biệt: `mahalanobis_distance, whiten_point, unwhiten_point, covariance_interpolate, discrete_distance, gaussian_distance`, cùng `SE3, SO3`.
  - Nhận định thiết kế: *"The geometry-specific cases use focused algorithms, not a speculative geometry hierarchy."*
- Giới hạn bằng chứng: đọc 90 dòng đầu; không quan sát được công thức cụ thể của `gaussian_distance`, `discrete_distance`, hay cách `SO3/SE3` được biểu diễn.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: đúng tám tên hình học; bốn tên tham số Gauss (`position`, `scale`, `opacity`, `color`); sự tồn tại của các phép Mahalanobis/whiten/covariance-interpolate/discrete/gaussian; định hướng "hàm chuyên biệt, không cây kế thừa".

Phần **do bài tập định nghĩa**:

- Biểu diễn điểm dạng JSON (list số) cho từng hình học.
- Công thức khoảng cách cụ thể (đặc biệt: `gaussian_set` so theo thứ tự, không ghép cặp tối ưu).
- Quy tắc nội suy và xử lý trường hợp đối cực.
- Ngưỡng dung sai kiểm tra trực giao/chuẩn hoá/xác định dương.
- Bộ lỗi, registry, định dạng fixture/CLI.

Nguồn **không** bao gồm: PyTorch, UMAP, lưu trữ, hay pipeline huấn luyện.

## Phạm vi

Trong phạm vi:

- Điểm có số chiều nhỏ (≤ 16), ma trận ≤ 3×3.
- Tám hình học, mỗi cái ba hàm; registry; CLI kiểm tra và tính khoảng cách.
- Test số học cho từng hình học + test lỗi.

Ngoài phạm vi:

- Không `numpy`, `torch`, `scipy`; không GPU.
- Không ghép cặp tối ưu cho `gaussian_set` (đó là mở rộng).
- Không học biểu diễn, không giảm chiều.

## Cảnh báo production

- `gaussian_set` so theo thứ tự là quyết định của bài tập, không phải của splatting thật: đảo thứ tự hai Gauss làm khoảng cách thay đổi. Đừng dùng để đánh giá chất lượng tái tạo.
- Slerp trên SO(3) qua quaternion có nhánh đối cực; nếu chọn dấu sai, quỹ đạo quay "đi đường dài". Bài tập yêu cầu phát hiện và chọn dấu ngắn.
- Dung sai trực giao `1e-6` phù hợp với `float`; với dữ liệu nhiễu từ học sâu, cần chiếu lại về SO(3) trước khi dùng.
- Mahalanobis với ma trận gần suy biến sẽ bùng nổ số; kiểm tra `cond` trước khi tính (bài tập chỉ kiểm tra xác định dương).

## Fixture offline

- `fixtures/points_<geometry>.json` — cặp điểm hợp lệ cho từng hình học.
- `fixtures/invalid_<geometry>.json` — điểm vi phạm ràng buộc.
- `fixtures/expected_distances.json` — bảng khoảng cách kỳ vọng (SPEC mục 6).
- Không có URL ngoài; không dữ liệu thật.

## Liên kết

- [SPEC.md](SPEC.md) — biểu diễn, công thức, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế registry, slerp, kiểm tra ma trận, cách kiểm chứng.
