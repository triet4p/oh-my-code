# 43 — Biến dạng tín hiệu có kiểm soát

## Mục tiêu

Sinh dữ liệu hỏng **có kiểm soát**: năm cơ chế biến dạng với biên số cứng, ba nhiễu nền không đổi nhãn, hai họ **để dành** bị từ chối tuyệt đối, và nhật ký xin/được duyệt cho từng thao tác.

1. Cài năm cơ chế biến dạng trên tín hiệu nhiều kênh, mỗi cơ chế có biên tham số lấy từ nguồn.
2. Kẹp tham số vượt biên thay vì bỏ qua, và ghi cả giá trị xin lẫn giá trị áp dụng.
3. Áp ba nhiễu nền sau biến dạng mà **không** thay đổi nhãn.
4. Từ chối hai họ `wrong_transition` / `cross_channel_inconsistency` bằng ngoại lệ có tên.
5. Băm SHA-256 manifest để chứng minh tính tất định.

## Giá trị

- Đây là bài học về **tính trung thực của dữ liệu tổng hợp**: biên tham số, nhật ký, và "họ để dành" là ba cơ chế khác nhau để không tự lừa mình.
- Kẹp thay vì ném lỗi là quyết định thiết kế có hệ quả: dữ liệu vẫn dùng được nhưng phải chứng minh được **đã kẹp**. Nhật ký là bằng chứng.
- Ràng buộc "không đọc mã sinh dữ liệu gốc" buộc API của bạn không có tham số `family` — một bài tập nhỏ về ranh giới module.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Trung bình–Khó |
| Điều kiện | Số thực, RNG có seed, `hashlib`, thiết kế API "không rò ground truth" |
| Runtime | Không mạng, không GPU |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/anomaly-representation-learning` (nhánh `master`)
- File nguồn: <https://github.com/triet4p/anomaly-representation-learning/blob/master/src/representation/corruptions.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `BOUNDS` khai báo biên từng cơ chế: `level_drift max_abs_offset 3.0`; `relative_gain_drift max_rel_gain 0.15`; `timing_shift max_shift_steps 4.0`; `transient max_abs_spike 4.0 / max_width_frac 0.25`; `persistent_degradation max_abs_shift 2.0 / max_var_scale 0.5`.
  - `NUISANCES = ("nuisance_gain", "nuisance_offset", "nuisance_noise")`.
  - `RESERVED_FAMILIES = ("wrong_transition", "cross_channel_inconsistency")` kèm ghi chú: *"this module implements NO swap/contradiction … corruption, and nothing here reads generator family code"*.
- Giới hạn bằng chứng: các giá trị biên và tên họ là quan sát trực tiếp; ngữ nghĩa số học chi tiết của từng cơ chế không được nêu trong đoạn đã đọc.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: tên năm cơ chế và đúng các con số biên; tên ba nhiễu; hai họ để dành; nguyên tắc module không đọc mã sinh dữ liệu.

Phần **do bài tập định nghĩa**:

- Ngữ nghĩa số học từng cơ chế: dịch phải bơm giá trị đầu, cửa sổ transient `[center, center+width)`, công thức `shift + x*(1+var_scale)`.
- Biên của ba nhiễu (`gain` 0.5–2.0, `offset` ±3.0, `amplitude` 0–0.1).
- Thứ tự áp dụng: `ops` theo khai báo, rồi `nuisances`.
- Định dạng `audit`, `span`, manifest, tên ngoại lệ.
- Quy ước `timing_shift` chỉ nhận số nguyên dù biên khai báo là `4.0`.

Nguồn **không** bao gồm: sinh tín hiệu sạch, sinh nhãn, đánh giá mô hình.

## Phạm vi

Trong phạm vi:

- Hàm thuần `corrupt(channels, ops, *, seed) -> CorruptionResult`.
- Năm cơ chế, ba nhiễu, kẹp biên, nhật ký, manifest; CLI đọc fixture JSON.

Ngoài phạm vi:

- Không sinh dữ liệu gốc; không huấn luyện, không đánh giá, không trực quan hoá.
- Không chuỗi thời gian không đều, không dữ liệu nhiều file.
- Không mô phỏng hai họ để dành dưới bất kỳ dạng nào.

## Cảnh báo production

- Kẹp âm thầm có thể che lỗi cấu hình: nếu 90% thao tác bị kẹp, dữ liệu "hợp lệ" nhưng không như bạn tưởng. Theo dõi tỉ lệ `clamped` như chỉ số sức khoẻ.
- `max_shift_steps` là `4.0` (float) nhưng dịch thời gian là số nguyên mẫu; phải từ chối `3.7`, đừng để nó bị kẹp thành `3`.
- Nhãn là **đầu vào**, không phải đầu ra. Suy nhãn từ cơ chế biến dạng là rò ground truth.
- Băm manifest chỉ chứng minh tất định, **không** chứng minh dữ liệu tốt.

## Fixture offline

- `fixtures/clean_multi_channel.json` — hai kênh, một `level_drift`, một `transient`, một `nuisance_gain`.
- `fixtures/reserved_attempt.json` — cố tình dùng `wrong_transition`.
- `fixtures/clamp_cases.json` — mọi tham số vượt biên để kiểm tra `applied != requested`.
- Không có URL ngoài; mọi kết quả sinh từ fixture cục bộ.

## Liên kết

- [SPEC.md](SPEC.md) — ngữ nghĩa từng cơ chế, bảng biên, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế bảng biên, kẹp, nhật ký, cách kiểm chứng.
