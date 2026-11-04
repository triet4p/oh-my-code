# 58 — Phát hiện drift với kết luận trung thực

## Mục tiêu

Cài một bộ phát hiện drift trả về **ba kết luận** — `supported`, `inconclusive`, `unsupported` — thay vì nhị phân "có/không", kèm ba cổng kiểm soát: ngưỡng khai báo trước, đối chứng không đổi, và đối chứng năng lực.

1. Fit mô hình mật độ **chỉ trên phần fit** của tập tham chiếu.
2. Thống kê khai báo trước: hiệu trung bình log-likelihood giữa tham chiếu và mẫu.
3. Ngưỡng `tau` từ phương sai của log-likelihood trên phần calibration (chỉ dữ liệu tham chiếu).
4. Ba cổng: quan sát vượt ngưỡng; đối chứng không đổi **không** vượt; ca dịch chuyển nhân tạo **có** vượt; cộng kiểm tra hoán vị cột.
5. `unsupported` khi tiền đề không thoả (quá ít dòng, hiệp phương sai suy biến, ngưỡng không hữu hạn).

## Giá trị

- Đây là bài học về **tính trung thực của kết luận thống kê**: báo "có drift" khi bộ dò không đủ năng lực là sai; báo "không drift" khi dữ liệu không đủ là sai theo hướng khác. Ba nhãn buộc bạn phân biệt.
- Đối chứng hoán vị cột dạy một điểm tinh tế: drift biên (marginal) khác drift cấu trúc (joint). Hoán vị phá cấu trúc nhưng giữ biên.
- Test khẳng định mô hình **không** được fit trên dữ liệu kiểm tra; đây là bất biến chống rò dữ liệu.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`math`, `statistics`, `hashlib`) |
| Độ khó | Khó |
| Điều kiện | Gaussian nhiều chiều, log-likelihood, nghịch đảo ma trận, kiểm định cơ bản |
| Runtime | Không mạng, không GPU, không `numpy`/`scipy`/`sklearn` |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/latent-anything` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/latent-anything/blob/main/src/latent_anything/_density_drift_detection.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Hợp đồng ba giá trị `supported / inconclusive / unsupported`.
  - Nguyên tắc: *"calibration on held-out reference rows only, a predeclared drift statistic clearing its threshold, the no-shift negative control staying below threshold"*.
  - Tái dùng một bộ ước lượng duy nhất `GaussianMixtureDensity (GMMConfig)`; ghi chú *"No parallel estimator exists"*.
  - Null hoán vị: hoán đổi **từng cột độc lập** để phá cấu trúc joint.
  - `evaluate_detection` fit/calibrate **một lần** cho mỗi lần gọi executor.
- Giới hạn bằng chứng: đọc 60 dòng đầu; không quan sát được ngưỡng cụ thể, số thành phần GMM, hay cách tính "no-shift".

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: ba nhãn; calibration chỉ trên dữ liệu tham chiếu giữ lại; thống kê khai báo trước; đối chứng không đổi phải dưới ngưỡng; hoán vị cột độc lập; chỉ một bộ ước lượng; fit một lần.

Phần **do bài tập định nghĩa**:

- Bộ ước lượng: **Gaussian đơn với hiệp phương sai đầy đủ** + regularization `1e-6` (thay GMM để cài được không cần EM). Ghi rõ khác nguồn.
- Công thức thống kê, ngưỡng `3 * se`, cách chia fit/calibration.
- Cổng năng lực (dịch chuyển nhân tạo) — nguồn chỉ nói "predeclared"; bài tập biến thành điều kiện bắt buộc.
- Cổng hoán vị: `gap_null < gap_observed`.
- Định dạng fixture/output, tên lý do `unsupported`.

Nguồn **không** bao gồm: GMM/EM, PyTorch, hay dữ liệu latent thật.

## Phạm vi

Trong phạm vi:

- `d ≤ 4`, `n_ref ≤ 500`, `n_test ≤ 500`.
- Một mô hình mật độ; một thống kê; ba cổng.
- CLI đọc fixture, in báo cáo JSON.

Ngoài phạm vi:

- Không GMM nhiều thành phần, không kernel density.
- Không kiểm định phi tham số; không hiệu chỉnh đa kiểm định.
- Không theo dõi drift theo thời gian (streaming).

## Cảnh báo production

- Một Gaussian đơn giả định phân bố unimodal; dữ liệu thật thường đa mô hình. Kết quả `unsupported` ở đây có thể chỉ là "mô hình không phù hợp", không phải "không có drift".
- Ngưỡng `3 * se` là xấp xỉ chuẩn, không phải p-value chính xác; với `n` nhỏ, sai số lớn.
- Cổng năng lực dùng dịch chuyển nhân tạo nên phụ thuộc độ lớn dịch chuyển; chọn `shift` quá nhỏ khiến mọi ca thành `inconclusive`.
- Không báo "supported" cho dữ liệu một chiều khi chưa kiểm tra: hoán vị cột không thay đổi gì, nên cổng 4 tự động thoả — ghi rõ hành vi.

## Fixture offline

- `fixtures/case_supported.json` — `reference = [[0,0],[1,0],[-1,0]]`, `test = [[3,0],[0,3],[3,0]]`, `model` cố định, `seed = 7`; kỳ vọng `supported` (SPEC 7).
- `fixtures/case_inconclusive.json` — cùng tham chiếu, `test = [[0,3],[0,3],[0,3]]`; hoán vị cột là phép không đổi nên G4 false ⇒ `inconclusive` (SPEC 7.1).
- `fixtures/case_unsupported.json` — `reference` 2 dòng, `min_reference_rows = 20` ⇒ `unsupported` (SPEC 7.2).
- `fixtures/model_fixed.json` — tham số mô hình cố định `mean [0,0]`, `cov [[1,0.8],[0.8,4]]` để test đường ống không cần fit.
- Không có URL ngoài; mọi phép ngẫu nhiên dùng LCG có seed.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, ba cổng, ví dụ số đầy đủ, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế pipeline, bẫy rò dữ liệu, cách kiểm chứng.
