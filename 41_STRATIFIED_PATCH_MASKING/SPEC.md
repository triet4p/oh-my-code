# SPEC 41 — Che patch theo tầng quan trọng

Mọi con số trong tài liệu này là hợp đồng. Nếu cài đặt của bạn khác ở một dòng, hãy sửa cài đặt hoặc đề xuất sửa SPEC — đừng "ước lượng gần đúng".

## 1. Đầu vào

### 1.1 Fixture JSON

```json
{
  "values": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
  "patch_size": 1,
  "mask_ratio": 0.5,
  "seed": 12345,
  "block_len": 2,
  "component_weights": {"random": 0.5, "info": 0.3, "block": 0.2}
}
```

| Khóa | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `values` | mảng số thực hữu hạn | có | — | Chuỗi tín hiệu, độ dài `L >= 1` |
| `patch_size` | số nguyên `>= 1` | có | — | Số điểm mỗi patch; `L` phải chia hết cho nó |
| `mask_ratio` | số thực trong `[0, 1]` | có | — | Tỉ lệ patch bị che |
| `seed` | số nguyên `0 <= seed < 2^32` | không | `0` | Seed của PRNG |
| `block_len` | số nguyên `>= 1` | không | `2` | Độ dài run liên tiếp cho thành phần block |
| `component_weights` | object ba khóa dương | không | `0.5 / 0.3 / 0.2` | Tỉ trọng chia ngân sách |

### 1.2 Thống kê mỗi patch

Với patch `p` gồm các giá trị `x[0..k-1]` (`k = patch_size`):

- `std = sqrt(mean((x_i - mean(x))^2))` — độ lệch chuẩn quần thể (chia cho `k`, **không** chia `k-1`).
- `range = max(x) - min(x)`.
- `deriv = |x[k-1] - x[0]| / (k - 1)` nếu `k > 1`, ngược lại `deriv = 0`.
- `score = (std + 1e-8) * (range + 1e-8) * (1.0 + deriv)`.

`deriv` dùng hiệu hai đầu patch chia khoảng — đây là `[DESIGN]` nhằm giữ công thức ba nhân tử của nguồn nhưng xác định rõ trên patch nhiều điểm.

### 1.3 Tầng (strata)

Sắp `score` tăng dần, tính ba ngưỡng bằng **nội suy tuyến tính** (định nghĩa type 7):

```text
p(q) với q in {25, 50, 75}:
  pos = (n - 1) * q / 100
  lo  = floor(pos); frac = pos - lo
  p(q) = s[lo] + frac * (s[lo + 1] - s[lo])     # s đã sắp tăng
```

Gán nhãn theo `score` của từng patch:

- `stable` nếu `score < p25`
- `transition` nếu `p25 <= score < p50`
- `dynamic` nếu `p50 <= score < p75`
- `extreme` nếu `score >= p75`

## 2. Đầu ra

Một object JSON, khóa sắp theo thứ tự từ điển khi in:

```json
{
  "component_counts": {"block": 1, "info": 1, "random": 2},
  "mask": [1, 3, 5, 6],
  "mask_by_component": {"block": [1, 3], "info": [6], "random": [5]},
  "num_patches": 8,
  "seed": 12345,
  "strata": {"dynamic": [4, 5], "extreme": [6, 7], "stable": [0, 1], "transition": [2, 3]},
  "stats": [
    {"deriv": 0.0, "range": 0.0, "score": 1e-16, "std": 0.0}
  ],
  "total_mask": 4
}
```

Quy ước:

- `mask` là hợp ba tập con, **đã sắp tăng**, không trùng.
- `mask_by_component` là phân hoạch của `mask`; ba tập rời nhau.
- `stats` dài đúng `num_patches`, cùng thứ tự với patch trong `values`.
- `component_counts` cộng lại đúng `total_mask`.

## 3. Kiểm tra hợp lệ

Mỗi lỗi dưới đây phải ném một ngoại lệ **có tên riêng** (đừng dùng `ValueError` trần cho tất cả) và thông điệp nêu rõ khóa sai:

| Điều kiện | Ngoại lệ gợi ý |
|---|---|
| `values` rỗng | `EmptySeries` |
| `len(values) % patch_size != 0` | `LengthNotDivisible` |
| `patch_size < 1` | `InvalidPatchSize` |
| `mask_ratio` ngoài `[0, 1]` hoặc không hữu hạn | `InvalidMaskRatio` |
| `seed` ngoài `[0, 2^32)` | `InvalidSeed` |
| khóa lạ trong `component_weights` | `UnknownComponent` |
| trọng số `<= 0` hoặc tổng lệch `1.0` quá `1e-9` | `InvalidWeights` |
| `block_len < 1` | `InvalidBlockLength` |

`NaN`/`Infinity` trong `values` (JSON cho phép qua `NaN`, `Infinity` của Python) phải bị từ chối với `NonFiniteValue`.

## 4. Tính tất định

- Cùng fixture, cùng seed → cùng output **byte-identical** (sau khi sắp khóa JSON).
- Thứ tự xử lý: tính stats theo thứ tự patch → tính ngưỡng → gán tầng → phân bổ ngân sách → chọn block → chọn info → chọn random → sắp `mask`.
- Mọi hoà điểm (score bằng nhau) phá bằng chỉ số patch tăng dần.
- PRNG: `[DESIGN]` dùng LCG 32-bit để tất định và dễ port:

```text
state = seed
next_u():  state = (1664525 * state + 1013904223) mod 2^32 ; return state / 2^32
pick(m):   return floor(next_u() * m)          # 0 <= kết quả < m
```

Nếu bạn dùng `random.Random(seed)` của Python, output vẫn tất định trong một phiên bản Python nhưng **không** khớp golden của LCG. Chọn một trong hai và ghi rõ trong README của bạn.

## 5. Ngân sách và phân bổ

```text
N = num_patches
M = floor(mask_ratio * N + 0.5)          # half-up, kẹp về [0, N]
raw_c = M * weight[c]   với c in (random, info, block)
base_c = floor(raw_c)
dư_c  = raw_c - base_c
thiếu = M - sum(base_c)
```

Phân `thiếu` đơn vị cho các thành phần có `dư` lớn nhất; hoà thì ưu tiên theo thứ tự `random, info, block`. Đây là **phương pháp phần dư lớn nhất**; nó bảo đảm `sum(counts) == M` với mọi `M` và mọi bộ trọng số hợp lệ.

## 6. Chọn vị trí

Ba thành phần phải **rời nhau** và hợp đúng `M` phần tử.

1. **Block**: chọn các run liên tiếp dài `block_len` (run cuối được cắt ngắn nếu vượt `N`). Ứng viên là mọi `start` trong `[0, N-1]`, ưu tiên `score` cao hơn, hoà thì `start` nhỏ hơn. Bỏ qua run chạm vị trí đã chọn. Dừng khi đủ `count[block]`.
2. **Info**: chỉ lấy từ patch thuộc `dynamic` hoặc `extreme`, ưu tiên `score` cao, hoà theo chỉ số; bỏ vị trí đã chọn. Nếu cạn, lấy thêm từ `transition` rồi `stable` — ghi cờ `overflow_used: true` (thêm khóa này vào output khi xảy ra).
3. **Random**: lấy từ pool còn lại, dùng PRNG, theo cơ chế **swap-remove** trên mảng pool đã sắp tăng để kết quả không phụ thuộc thứ tự chọn.

Nếu `M == 0`, cả ba tập rỗng và `mask` rỗng. Nếu `M == N`, `mask` là `range(N)`.

## 7. Ví dụ cụ thể

### 7.1 Phân tầng (kiểm tra bằng tay)

`values = [0,1,2,3,4,5,6,7]`, `patch_size = 1` ⇒ `score` xấp xỉ `[0,1,2,3,4,5,6,7]` (nhân tử `1e-8` làm score lệch cực nhỏ nhưng **thứ tự không đổi**).

- `p25 = 1.75`, `p50 = 3.5`, `p75 = 5.25`.
- `stable = [0,1]`, `transition = [2,3]`, `dynamic = [4,5]`, `extreme = [6,7]`.

### 7.2 Phân bổ

`N = 8`, `mask_ratio = 0.5` ⇒ `M = 4`. Trọng số mặc định:

- `raw = (2.0, 1.2, 0.8)`; `base = (2, 1, 0)`; `dư = (0.0, 0.2, 0.8)`; `thiếu = 1`.
- Phần dư lớn nhất thuộc `block` ⇒ `counts = {random: 2, info: 1, block: 1}`.

`N = 8`, `mask_ratio = 0.25` ⇒ `M = 2`; `raw = (1.0, 0.6, 0.4)`; `base = (1,0,0)`; `thiếu = 1`; dư lớn nhất thuộc `info` ⇒ `(1, 1, 0)`.

### 7.3 Suy biến

`values = [5,5,5,5]`, `patch_size = 1` ⇒ mọi `score` bằng nhau ⇒ `p25 = p50 = p75 = score`.

- `stable` rỗng (vì `score < p25` sai), `transition` rỗng, `dynamic` rỗng, `extreme = [0,1,2,3]`.
- Đây là hành vi **đúng theo luật**, không phải lỗi; test phải khẳng định nó.

### 7.4 Tỉ lệ biên

`mask_ratio = 0.0` ⇒ `total_mask = 0`, `mask = []`, mọi `component_counts = 0`.
`mask_ratio = 1.0` ⇒ `total_mask = N`, `mask = [0..N-1]`.

## 8. Tiêu chí chấp nhận quan sát được

1. Với mọi fixture hợp lệ: `len(mask) == total_mask` và `total_mask == floor(ratio*N + 0.5)`.
2. `mask == sorted(set(mask))`; ba tập con rời nhau và hợp đúng `mask`.
3. `strata` là phân hoạch của `range(N)`: mỗi chỉ số xuất hiện đúng một lần.
4. Chạy hai lần cùng fixture cho ra chuỗi JSON giống hệt; đổi `seed` (khi `counts.random > 0`) cho ra `mask` khác với xác suất rất cao — test chỉ khẳng định trường hợp cụ thể bạn đã ghi trong fixture.
5. Mỗi lỗi ở mục 3 ném đúng tên ngoại lệ và CLI trả mã thoát `2`.
6. Fixture ở 7.1–7.4 cho ra đúng các giá trị đã ghi.
7. `python -m src fixtures/basic.json` in JSON hợp lệ, không có log lẫn vào stdout.

## 9. Non-goals

- Không cài đặt mô hình, loss, optimizer, hay vòng huấn luyện.
- Không hỗ trợ patch 2 chiều hoặc nhiều kênh.
- Không đảm bảo "chất lượng" mask theo nghĩa học máy; chỉ đảm bảo cấu trúc.
- Không xử lý song song hoặc dữ liệu lớn hơn bộ nhớ.
