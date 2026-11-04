# 41 — Che patch theo tầng quan trọng

## Mục tiêu

Lập kế hoạch che (mask) ba thành phần với **tổng số vị trí cố định**: cắt chuỗi thành patch, chấm điểm quan trọng, chia bốn tầng bằng tứ phân vị, rồi chọn đúng `M` vị trí từ ba thành phần `random`, `info`, `block` — không huấn luyện mô hình, chỉ sinh mask.

1. Cắt chuỗi số thực một chiều thành patch rời nhau và tính thống kê từng patch.
2. Chấm điểm quan trọng và chia patch thành `stable / transition / dynamic / extreme`.
3. Phân bổ ngân sách `M` cho ba thành phần bằng phương pháp phần dư lớn nhất.
4. Xuất mask đã sắp xếp kèm báo cáo phân bổ — đủ để bài 42 dùng lại làm policy.

## Giá trị

- Đây là bài toán **ngân sách rời rạc**: ba tỉ lệ phần trăm không tự cộng thành một số nguyên. Bạn phải làm tròn, chia phần dư, và chứng minh tổng khớp tuyệt đối — kỹ năng dùng lại ở quota, sampling, phân bổ tài nguyên.
- Tách **chính sách** (chọn gì) khỏi **thực thi** (gán mask lên tensor) là tiền đề trực tiếp của bài 42.
- Phân tầng theo tứ phân vị buộc bạn đối mặt với định nghĩa percentile, hoà điểm, và trường hợp suy biến — nơi phần lớn cài đặt "gần đúng" sai lệch.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Trung bình |
| Điều kiện | Tứ phân vị, làm tròn và chia phần dư, RNG có seed, `set`/`dict` |
| Runtime | Không mạng, không GPU, không package ngoài |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/anomaly-representation-learning` (nhánh `master`)
- File nguồn: <https://github.com/triet4p/anomaly-representation-learning/blob/master/src/synth/masking.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Docstring mô tả cơ chế: *"Three-component masking with fixed total mask ratio: M = M_random ∪ M_info ∪ M_block"*.
  - `compute_all_patch_stats` trả về đại lượng dạng `(std + 1e-8) * (rng + 1e-8) * (1.0 + deriv)` — ba nhân tử: độ lệch chuẩn, biên độ, đạo hàm tuyệt đối.
  - `_stratify_patches` chia patch thành `stable / transition / dynamic / extreme` theo `np.percentile(vs, [25, 50, 75])`.
- Giới hạn bằng chứng: nguồn được đọc ở mức file và các đoạn nêu trên; không có số dòng vì trình đọc trả văn bản thuần. Không có hành vi huấn luyện/đánh giá nào được quan sát trong phạm vi này.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: ba thành phần mask, tổng tỉ lệ cố định, công thức thống kê ba nhân tử, bốn tầng theo tứ phân vị.

Phần **do bài tập định nghĩa** (đừng gán cho nguồn):

- Cách quy đổi `mask_ratio` thành số nguyên và luật chia phần dư giữa ba thành phần.
- Định nghĩa `deriv` trên patch nhiều điểm (hiệu hai đầu chia khoảng).
- Quy tắc chọn block liên tiếp, cách xử lý khi block vượt biên.
- Percentile nội suy tuyến tính (type 7) và quy tắc hoà điểm theo chỉ số.
- PRNG LCG 32-bit để tất định và port được sang ngôn ngữ khác.
- Định dạng fixture/CLI, tên ngoại lệ, cấu trúc output JSON.

Nguồn **không** bao gồm: huấn luyện, encoder, dataset thật, đánh giá anomaly. Bài này dừng ở planner.

## Phạm vi

Trong phạm vi:

- Hàm thuần `plan(values, config) -> PlanResult` chạy trong bộ nhớ.
- Một CLI đọc fixture JSON và in JSON; kiểm thử bằng `unittest`.

Ngoài phạm vi:

- Không dùng `torch`, `numpy`, `scikit-learn`; không đọc ảnh; không patch 2 chiều.
- Không song song, không luồng, không checkpoint.
- Không đánh giá chất lượng mask bằng mô hình — chỉ kiểm tra bất biến cấu trúc.

## Cảnh báo production

- Trong nguồn, masking là một bước của pretraining; planner ở đây không chứng minh mask "tốt".
- `np.percentile` mặc định **nội suy tuyến tính**; port sang ngôn ngữ khác mà dùng nearest-rank sẽ lệch tầng ở đúng các fixture biên — SPEC ghim định nghĩa để tránh.
- Hằng `1e-8` là chống chia 0, không phải tham số cần bảo toàn khi đổi thang đo dữ liệu.
- Mask theo *patch* chứ không theo *điểm*: đừng suy ra "tỉ lệ điểm bị che" bằng `mask_ratio` khi `patch_size > 1`.

## Fixture offline

- `fixtures/basic.json` — tám giá trị tăng dần để kiểm tra phân tầng bằng tay.
- `fixtures/degenerate.json` — toàn giá trị bằng nhau, kiểm tra nhánh suy biến.
- Không có URL ngoài, không tải dữ liệu, không phụ thuộc thời gian hệ thống.

## Liên kết

- [SPEC.md](SPEC.md) — đầu vào/ra, kiểm tra hợp lệ, tính tất định, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế từng bước, cạm bẫy, cách tự kiểm chứng, gợi ý và mở rộng.
