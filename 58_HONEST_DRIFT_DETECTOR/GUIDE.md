# GUIDE 58 — Phát hiện drift với kết luận trung thực

## 1. Ba nhãn, ba trách nhiệm

| Nhãn | Nghĩa | Không được dùng để |
|---|---|---|
| `supported` | Có tín hiệu vượt ngưỡng **và** đã qua ba cổng | Khẳng định nhân quả |
| `inconclusive` | Có/không chưa kết luận được, kèm lý do | Báo "không drift" |
| `unsupported` | Tiền đề không thoả (ít dữ liệu, mô hình suy biến) | Báo "không drift" |

Sai lầm phổ biến nhất là gộp `inconclusive` và `unsupported` thành "không drift". Bài tập tách ra vì lý do thực dụng: hành động tiếp theo khác nhau (thu thêm dữ liệu vs đổi mô hình).

## 2. Thứ tự cài đặt

```text
src/
├── density.py     # GaussianModel (fit, invert, log_likelihood), FixedGaussian
├── detect.py      # statistic, gates, outcome
├── rng.py         # LCG + fisher_yates_columns
└── __main__.py
```

### Bước 1 — Nghịch đảo có kiểm tra

Khử Gauss–Jordan trên `[cov | I]`; mỗi bước:

```text
tìm pivot lớn nhất trong cột (từ hàng hiện tại)
nếu |pivot| < 1e-12: raise SingularCovariance
hoán đổi hàng; chia hàng; khử các hàng khác
```

Đồng thời cộng `log|pivot|` để có `ln_det` — chính xác hơn `log(det)` và tránh tràn.

### Bước 2 — Log-likelihood

```text
ll(x) = -0.5 * (d*log(2π) + ln_det + q)
q = Σ_i Σ_j (x_i - mu_i) * inv[i][j] * (x_j - mu_j)
```

Kiểm tra bằng tay: `cov = I`, `mu = 0`, `x = [0,0]` ⇒ `ll = -0.5*(2*1.8378771 + 0 + 0) = -1.8378771`. Nếu bạn ra khác, kiểm tra hệ số `d`.

### Bước 3 — Thống kê và ngưỡng

Theo đúng SPEC 3. Điểm cần cẩn thận: `se` dùng **cùng** `var_ref` cho cả hai phía (`/n_calib + /n_test`), không dùng phương sai của test. Đây là lựa chọn có chủ đích: test có thể đã drift, dùng phương sai của nó làm ngưỡng sẽ che tín hiệu.

`var_ref = 0` (mọi `ll` bằng nhau) ⇒ `tau = 0`; khi đó G1 gần như luôn đúng. SPEC yêu cầu xử lý bằng cách ghi nhận, không đặc biệt hoá — nhưng hãy cảnh báo trong báo cáo nếu `tau == 0`.

### Bước 4 — Bốn cổng

Viết từng cổng thành hàm thuần nhận dữ liệu đã chuẩn bị:

```text
G1: gap > tau
G2: gap_no_shift <= tau     với gap_no_shift = mean(ll(calib[:h])) - mean(ll(calib[h:]))
G3: gap_shifted > tau       với calib_shifted = [[v + shift ...] for row in calib]
G4: gap_null < gap
```

`h = len(calib) // 2`; nếu lẻ, nửa đầu nhận phần dư.

### Bước 5 — Hoán vị cột

Với mỗi cột `j`, thu thập `n_test` giá trị, Fisher–Yates bằng LCG, ghi lại. Điều này phá ghép cặp giữa các cột nhưng giữ nguyên phân bố biên từng cột — đúng mục đích.

LCG: `state = (1664525*state + 1013904223) mod 2^32`; `pick(m) = floor(state/max * m)` sau khi cập nhật.

### Bước 6 — Kết luận

Kiểm tra tiền đề **trước** khi tính bất cứ thống kê nào; nếu không, báo cáo `unsupported` vẫn có thể chứa số vô nghĩa. Trả `statistic = None` khi unsupported.

## 3. Cạm bẫy

- **Fit trên toàn bộ reference rồi calibration trên chính nó**: ngưỡng bị "học thuộc", G2 luôn đúng. Phải tách fit/calib.
- **Fit trên test**: rò dữ liệu; test 8.5 của SPEC bắt bằng cách đổi test và so `tau`.
- **Dùng phương sai test trong `se`**: che drift.
- **`det` rồi `log`**: với `d` lớn, `det` tràn hoặc underflow. Dùng tổng log pivot.
- **Ngưỡng `>=` thay vì `>`**: ở biên, kết luận đổi. SPEC chọn `>` cho G1/G3 và `<=` cho G2.
- **Hoán vị cả ma trận thay vì từng cột**: phá cả biên, không còn là đối chứng cấu trúc.
- **Test có mọi dòng giống hệt nhau**: hoán vị từng cột là phép không đổi, nên `gap_null` **bằng** `gap` và G4 luôn false. Đừng "sửa" bằng cách nới `<` thành `<=`; hãy thiết kế mẫu có ít nhất hai kiểu dòng khác nhau (ví dụ `(3,0)` và `(0,3)`), nếu không bài toán không thể tách drift biên khỏi drift cấu trúc.
- **Bỏ qua `shift`**: G3 luôn true với shift lớn tuỳ ý; nhưng nếu shift = 0, G3 luôn false → mọi ca `inconclusive`. Ghi rõ.
- **`reasons` không sắp**: test so list; luôn theo G1..G4.
- **Trả `inconclusive` không kèm lý do**: vô dụng cho người vận hành.

## 4. Kiểm thử

| Test | Nội dung |
|---|---|
| `example_supported` | bảng SPEC 7, dung sai `1e-3` |
| `example_inconclusive` | 7.1, chỉ G4 false (dòng giống hệt ⇒ hoán vị no-op) |
| `example_unsupported` | 7.2, không có `statistic` |
| `permutation_noop` | test toàn dòng giống hệt ⇒ `gap_null == gap`, G4 false |
| `singular` | mọi dòng giống nhau, `λ = 0` |
| `no_fit_on_test` | đổi test ⇒ `mu_ref`/`tau` không đổi |
| `fit_rows` | bộ đếm xác nhận `n_fit` dòng đầu |
| `var_zero` | `tau == 0`, outcome vẫn hợp lệ |
| `reasons_order` | nhiều cổng false ⇒ thứ tự đúng |
| `determinism` | cùng seed ⇒ cùng output |
| `outcome_enum` | chỉ ba giá trị |

## 5. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src detect --fixture fixtures/case_supported.json | python -m json.tool
python -m src detect --fixture fixtures/case_inconclusive.json | python -c "import json,sys; d=json.load(sys.stdin); print(d['outcome'], d['reasons'])"
python -m src detect --fixture fixtures/case_unsupported.json | python -c "import json,sys; print(json.load(sys.stdin)['outcome'])"
```

Lệnh thứ ba phải cho `"outcome": "supported"` với các số khớp SPEC 7 (in 7 chữ số). Lệnh thứ tư in `inconclusive ['G4_structure_control']`. Lệnh thứ năm in `unsupported`.

Kiểm tra không fit trên test bằng một script:

```python
from src.detect import evaluate
a = evaluate(ref, test_a, cfg)
b = evaluate(ref, test_b, cfg)   # test_b khác hoàn toàn
assert a["statistic"]["tau"] == b["statistic"]["tau"]
```

Nếu `tau` đổi, bạn đã dùng test ở đâu đó trong calibration.

## 6. Gợi ý

- Viết `evaluate(reference, test, config) -> Report` là hàm thuần; CLI chỉ đọc/ghi.
- Viết `gates()` trả dict bool + list lý do, tách khỏi phần tính số.
- Với ví dụ tay, in `ll` từng dòng ra trước khi tính trung bình — dễ so với SPEC hơn.
- Nếu muốn thấy G3 nhạy thế nào, chạy `shift` = 0.5, 1.0, 3.0 trên cùng dữ liệu và ghi lại outcome.

## 7. Mở rộng

- **GMM nhiều thành phần**: cài EM với `K = 2`, so kết quả; thêm lý do `unsupported("em_not_converged")`.
- **Thống kê khác**: thay `gap` bằng MMD hoặc KS từng chiều; giữ nguyên bốn cổng — thấy cấu trúc pipeline độc lập với thống kê.
- **Bootstrap ngưỡng**: thay `3*se` bằng phân vị bootstrap trên calib; so tỉ lệ `supported` sai.
- **Streaming**: cửa sổ trượt, cảnh báo khi 3 cửa sổ liên tiếp `supported`.
- **Báo cáo có băm**: băm cấu hình + dữ liệu (trừ test) để tái lập; không băm test vì test có thể chứa dữ liệu nhạy cảm.
