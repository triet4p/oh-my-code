# SPEC 42 — Cầu nối policy masking với tensor

## 1. Mô hình dữ liệu

### 1.1 `TensorLike` (tối thiểu)

Bài tập không phụ thuộc `torch`. Định nghĩa một protocol đủ để bridge làm việc:

| Thành viên | Kiểu | Ý nghĩa |
|---|---|---|
| `shape` | `tuple[int, ...]` | `(B, L)` hoặc `(B, L, F)` |
| `dtype` | `str` | `"float32"`, `"int64"`, … |
| `device` | `str` | `"cpu"`, `"cuda:0"`, … |
| `rows()` | `list[list]` | Duyệt theo hàng, trả về list thuần |
| `new_like(data, dtype)` | `TensorLike` | Tạo tensor mới cùng shape/device, kiểu cho trước |
| `masked_fill(mask, value)` | `TensorLike` | Trả **bản sao** đã điền `value` tại các vị trí `mask` |

`FakeTensor` trong `src/tensorlike.py` cài đúng các thành viên này trên list Python. Nếu bạn viết adapter `torch`, nó chỉ cần ánh xạ 5 thành viên trên.

### 1.2 `MaskPolicy`

```text
plan_row(row_values: list[float], n_patches: int, config: BridgeConfig) -> PolicyOutput
```

`PolicyOutput` gồm:

- `patch_indices: list[int]` — chỉ số patch cần che, trong `[0, n_patches)`;
- `expected_total: int` — tổng số **điểm** mà policy tuyên bố sẽ che (dùng để đối chiếu);
- `meta: dict[str, str]` — nhãn chẩn đoán, không bắt buộc.

Policy **không** được biết về padding, thiết bị, hay độ dài gốc của hàng — đó là việc của bridge. Đây là ràng buộc thiết kế quan trọng: nếu policy cần biết, hãy truyền qua `row_values` đã cắt đúng phần hợp lệ.

### 1.3 `BridgeConfig`

| Khóa | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|
| `patch_size` | `int >= 1` | bắt buộc | Số điểm mỗi patch |
| `mask_ratio` | `float` trong `[0,1]` | bắt buộc | Tỉ lệ patch bị che mỗi hàng |
| `valid_lengths` | `list[int]` dài `B` | bắt buộc | Số điểm hợp lệ mỗi hàng, `0 < v <= L` |
| `fill_value` | số thực | `0.0` | Giá trị điền vào vị trí bị che |
| `default_seed` | `int` hoặc `None` | `None` | Seed dự phòng khi không truyền `seed`/`rng` |

## 2. Chữ ký và đầu ra

```text
apply_batched_masking(batch, config, *, seed=None, rng=None, policy=None)
    -> BridgeResult
```

`BridgeResult`:

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `masked` | `TensorLike` | Bản sao của batch, vị trí bị che đã điền `fill_value` |
| `mask` | `TensorLike` | Tensor `bool` cùng shape với `batch` |
| `per_row` | `list[RowReport]` | `RowReport(row, valid, n_patches, total_mask, policy_meta)` |

Bất biến bắt buộc:

- `mask.shape == batch.shape`, `mask.dtype == "bool"`, `mask.device == batch.device`.
- `masked.device == batch.device`, `masked.dtype == batch.dtype`.
- `batch` **không bị sửa** (so sánh trước/sau phải giống hệt).
- Với hàng `r`: mọi `j >= valid_lengths[r]` có `mask[r][j] == False`.
- Với hàng `r`: `sum(mask[r]) == total_mask[r]` với `total_mask[r] = floor(mask_ratio * n_patches[r] + 0.5)`, và `n_patches[r] = ceil(valid_lengths[r] / patch_size)`.

## 3. Luật "tổng số cố định" nằm ở bridge

Luật này **không** được giao cho policy. Bridge làm ba việc:

1. Tính `n_patches` và `total_mask` từ `valid_lengths` + `config`.
2. Gọi policy đúng **một lần** cho mỗi hàng.
3. Đối chiếu: `len(set(policy_output.patch_indices))` phải bằng `total_mask`; nếu khác, ném `PolicyCountMismatch(row, expected, got)`.

Bridge **không** tự sửa, không cắt bớt, không thêm cho đủ. Lý do: sửa âm thầm làm mất tín hiệu rằng policy sai — đúng loại lỗi mà nguồn cố ý giữ luật ở tầng này.

## 4. Kiểm tra hợp lệ

| Điều kiện | Ngoại lệ |
|---|---|
| `seed` và `rng` cùng được truyền | `BothSeedAndRng` — ném **trước** khi gọi policy |
| không có `seed`, không có `rng`, `default_seed is None` | `MissingRandomness` |
| `rng` không có `.next_u()` | `InvalidRandomSource` |
| `len(valid_lengths) != B` | `LengthMismatch` |
| `valid_lengths[r] <= 0` | `EmptyRow` |
| `valid_lengths[r] > L` | `RowExceedsWidth` |
| `patch_size < 1` | `InvalidPatchSize` |
| `mask_ratio` ngoài `[0,1]` | `InvalidMaskRatio` |
| policy trả chỉ số ngoài `[0, n_patches)` | `PolicyIndexOutOfRange` |
| policy trả chỉ số trùng | `PolicyDuplicateIndex` |
| policy trả sai tổng | `PolicyCountMismatch` |
| `policy is None` | dùng `DefaultPolicy` (mô tả ở mục 6) |

## 5. Tính tất định

- Thứ tự: kiểm tra tham số → kiểm tra `seed`/`rng` → lặp hàng theo thứ tự tăng → gọi policy → kiểm tra → gán mask → trả.
- PRNG dùng chung một đối tượng cho cả batch, tiêu thụ tuần tự theo hàng. Nếu policy tự tạo RNG riêng từ `seed`, kết quả hàng sau sẽ **không** phụ thuộc hàng trước — chọn một mô hình và ghi rõ.
- `[DESIGN]` PRNG chuẩn của bài:

```text
state = seed (32-bit)
next_u(): state = (1664525*state + 1013904223) mod 2^32; return state / 2^32
```

- Cùng batch + cùng seed ⇒ `mask` giống hệt từng bit.
- Đổi `seed` ⇒ mask khác, trừ khi `total_mask == 0` hoặc `total_mask == n_patches` cho mọi hàng.

## 6. `DefaultPolicy`

Để bài tự chạy được mà không phụ thuộc bài 41:

- Với mỗi hàng, tính `score` cho từng patch theo công thức bài 41 (std, range, deriv) trên `row_values` đã cắt.
- Chọn `total_mask` patch có `score` cao nhất; hoà theo chỉ số tăng dần.
- Trả `expected_total = total_mask`.

Đây là policy **có triển khai mẫu trong SPEC** vì nó không phải trọng tâm bài 42; phần bạn tự viết là bridge. Nếu đã làm bài 41, hãy cắm `PlanResult` của nó vào qua adapter mỏng.

## 7. Ví dụ cụ thể

### 7.1 Batch có padding

```json
{
  "data": [[1,2,3,4], [5,6,7,0]],
  "config": {"patch_size": 2, "mask_ratio": 0.5, "valid_lengths": [4,3], "fill_value": -1}
}
```

- Hàng 0: `valid=4`, `n_patches = ceil(4/2) = 2`, `total_mask = floor(0.5*2+0.5) = 1`.
- Hàng 1: `valid=3`, `n_patches = ceil(3/2) = 2`, `total_mask = 1`.
- Vị trí `j=3` của hàng 1 là pad ⇒ `mask[1][3] == False` **bất kể** policy chọn gì.
- Với `DefaultPolicy`: hàng 0 patch 0 = `[1,2]`, patch 1 = `[3,4]`; std bằng nhau ⇒ hoà ⇒ chọn patch 0 ⇒ mask hàng 0 = `[T,T,F,F]`.
- Hàng 1: patch 0 = `[5,6]`, patch 1 = `[7]` (partial). `std(patch0) = 0.5`, `std(patch1) = 0` ⇒ chọn patch 0 ⇒ mask hàng 1 = `[true, true, false, false]` (phần tử cuối là pad, luôn `False`).

Kết quả mask kỳ vọng:

```text
[[true, true, false, false],
 [true, true, false, false]]
```

`masked` với `fill_value = -1`:

```text
[[-1, -1, 3, 4],
 [-1, -1, 7, 0]]
```

### 7.2 Lỗi ngẫu nhiên kép

`apply_batched_masking(batch, cfg, seed=1, rng=object())` ⇒ `BothSeedAndRng`, và bộ đếm gọi policy vẫn bằng `0`.

### 7.3 Policy trả thiếu

Policy trả `patch_indices = []` nhưng `total_mask = 1` ⇒ `PolicyCountMismatch(row=0, expected=1, got=0)`; `masked` không được trả về (không có kết quả một nửa).

### 7.4 Tỉ lệ biên

`mask_ratio = 0` ⇒ `mask` toàn `False`, `masked` bằng bản sao `batch`.
`mask_ratio = 1` ⇒ mọi vị trí hợp lệ `True`, vị trí pad vẫn `False`.

## 8. Tiêu chí chấp nhận quan sát được

1. Ví dụ 7.1 cho đúng hai mask và `masked` như trên.
2. `mask.dtype == "bool"`, `mask.device == batch.device`, `masked.dtype == batch.dtype`.
3. `batch` không đổi sau lời gọi (so sánh sâu trước/sau).
4. Với 50 fixture sinh ngẫu nhiên: bất biến padding và tổng số luôn đúng.
5. `seed` + `rng` cùng lúc ⇒ lỗi trước mọi tác dụng phụ (đếm policy = 0).
6. Policy trả trùng chỉ số hoặc sai tổng ⇒ đúng ngoại lệ, không có kết quả một nửa.
7. Hai lần gọi cùng tham số cho mask giống hệt.
8. `python -m src fixtures/padded_batch.json` in JSON với `mask` và `per_row` khớp ví dụ.

## 9. Non-goals

- Không autograd, không hỗ trợ tensor thưa hay nhiều thiết bị trong một batch.
- Không tối ưu hiệu năng; đây là bài về hợp đồng và biên giới, không phải throughput.
- Không cài đặt encoder hay loss.
