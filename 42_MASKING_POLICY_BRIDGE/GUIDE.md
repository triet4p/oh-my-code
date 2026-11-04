# GUIDE 42 — Cầu nối policy masking với tensor

## 1. Vì sao phải có "bridge"

Trong nguồn, một bên là mô hình (tensor có thiết bị, dtype, padding) và một bên là policy (chỉ quan tâm "patch nào đáng che"). Nếu để policy tự sinh mask lên tensor:

- policy phải biết `device` — trộn hai mối quan tâm;
- policy phải tự biết padding — dễ che vào vùng đệm;
- luật tổng số bị lặp ở nhiều nơi và trôi khỏi nhau.

Bridge là **cổng duy nhất**: policy trả về chỉ số; bridge đếm, kiểm tra, và biểu diễn lại. Bài tập này luyện đúng kiểu thiết kế đó.

## 2. Thiết kế theo lớp

```text
fixture JSON
   │
   ▼
BridgeConfig  ──►  bridge.apply_batched_masking
                        │  per row:
                        │   1. cắt valid region
                        │   2. n_patches = ceil(valid / patch_size)
                        │   3. total_mask = floor(ratio*n_patches + 0.5)
                        │   4. policy.plan_row(...)
                        │   5. validate indices + count
                        │   6. mở rộng patch→điểm, ghim pad = False
                        ▼
                    BridgeResult(masked, mask, per_row)
```

Hãy cài từ dưới lên: `FakeTensor` → `DefaultPolicy` → vòng lặp một hàng → cả batch.

## 3. Bước cài đặt

### Bước 1 — `FakeTensor`

Chỉ cần 5 thành viên trong SPEC. Vài điểm cần cẩn thận:

- `shape` suy từ dữ liệu, không lưu rời rạc rồi lệch.
- `masked_fill` trả **bản sao**; nếu bạn sửa tại chỗ, test "input không đổi" sẽ bắt được — hãy viết test đó trước.
- `new_like(data, dtype)` phải giữ `device`; đây là chỗ dễ đánh rơi thiết bị.
- `rows()` trả dữ liệu thuần; đừng trả tham chiếu tới list bên trong, nếu không policy có thể sửa batch.

### Bước 2 — Chuyển patch ↔ điểm

Đây là phần số học dễ sai nhất.

- `n_patches = ceil(valid / patch_size)`; patch cuối có thể ngắn.
- Patch `p` phủ các điểm `[p*patch_size, min((p+1)*patch_size, valid))`.
- Khi mở rộng ngược, dùng đúng biên trên `valid`; **không** dùng `shape[1]`, nếu không bạn che vào pad.
- Nếu `total_mask` patch được chọn nhưng patch cuối ngắn, tổng điểm bị che **không** bằng `total_mask * patch_size`. Đó là lý do `RowReport.total_mask` đếm **patch**, không đếm điểm — ghi rõ đơn vị trong output.

### Bước 3 — Kiểm tra policy trước khi gán

Ba kiểm tra, theo thứ tự, để thông điệp lỗi hữu ích:

1. Chỉ số ngoài `[0, n_patches)`.
2. Trùng chỉ số (dùng `len(set(...)) != len(...)`).
3. Tổng khác `total_mask`.

Chỉ sau khi cả ba qua mới dựng mask. Nếu bạn gán dần trong lúc kiểm tra, một lỗi giữa đường sẽ để lại trạng thái nửa vời — luôn "tính đủ rồi mới ghi".

### Bước 4 — Điền và trả

- Dựng mask dạng list `list[list[bool]]` kích thước đầy đủ, mặc định `False`.
- Đặt `True` theo chỉ số điểm đã mở rộng.
- `masked = batch.masked_fill(mask, fill_value)` — nhớ đây là bản sao.
- Trả `mask` qua `new_like(mask_data, "bool")` để dtype/device đúng.

### Bước 5 — Xử lý `seed`/`rng`

- Nếu cả hai: ném ngay, **trước** khi chạm policy. Test bằng bộ đếm.
- Nếu không có cái nào: dùng `config.default_seed`; vẫn không có ⇒ `MissingRandomness`.
- Bọc `rng` thành một hàm `next_u()`; nếu policy cần, truyền **cùng** đối tượng, không tạo mới trong vòng lặp hàng.

## 4. Cạm bẫy

- **`ceil` với số nguyên**: `(valid + patch_size - 1) // patch_size`; dùng `math.ceil(valid / patch_size)` với float có thể sai ở giá trị lớn.
- **Che vào pad**: test dùng `valid < L` và policy "tham lam" chọn patch cuối; nếu mask có `True` ở `j >= valid`, bạn đã lộ lỗi.
- **Thiết bị bị đánh rơi**: `mask.device` phải bằng `batch.device`; `new_like` là chỗ duy nhất được tạo tensor.
- **Sửa input**: `masked_fill` trả bản sao, nhưng nếu `FakeTensor.rows()` trả tham chiếu, policy có thể len lỏi sửa. Test sâu trước/sau.
- **Một policy cho cả batch vs mỗi hàng**: nguồn gọi theo hàng. Nếu bạn gộp, `RowReport` sẽ mất khả năng chỉ ra hàng lỗi.
- **`floor(x + 0.5)`** khác `round(x)` của Python (banker's rounding) — dùng đúng công thức SPEC.

## 5. Debug có hệ thống

Khi một fixture cho kết quả lạ, in theo thứ tự sau (đừng đoán):

1. `valid_lengths`, `n_patches`, `total_mask` từng hàng — nếu sai ở đây thì lỗi ở Bước 2.
2. `policy_output.patch_indices` — nếu sai số lượng, lỗi ở policy/DefaultPolicy.
3. Chỉ số điểm sau khi mở rộng — nếu vượt `valid`, lỗi biên.
4. Vị trí `True` trong mask — so với bước 3.

Một mẹo: viết `explain_row(...)` trả một chuỗi nhiều dòng cho mỗi hàng rồi so snapshot. Debug bằng snapshot rẻ hơn debug bằng breakpoint khi số hàng lớn.

## 6. Kiểm thử

| Test | Cách khẳng định |
|---|---|
| Ví dụ 7.1 | So nguyên mask và `masked` |
| Pad | Với `valid < L`, assert mọi `mask[r][valid:] == False` |
| Không sửa input | `deepcopy` trước, so sau |
| Thiết bị | `mask.device == batch.device` với `device="cuda:0"` trên FakeTensor |
| Seed kép | Ngoại lệ + đếm policy = 0 |
| Policy sai | Ba loại lỗi, mỗi loại một test |
| Tất định | Hai lần gọi, so từng bit |
| Fuzz | 50 batch ngẫu nhiên nhỏ, assert bất biến |

## 7. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src fixtures/padded_batch.json | python -m json.tool
```

So `mask` in ra với mục 7.1 của SPEC. Kiểm tra nhanh bất biến bằng một lệnh:

```bash
python -c "import json,subprocess; d=json.loads(subprocess.check_output(['python','-m','src','fixtures/padded_batch.json'])); print([r['total_mask'] for r in d['per_row']], [sum(row) for row in d['mask']])"
```

Hai danh sách phải bằng nhau.

Nếu bạn cài adapter `torch` (tùy chọn):

```bash
python -c "import torch; from src.torch_adapter import TorchTensor; print(TorchTensor(torch.zeros(2,4)).device)"
```

Chỉ chạy khi `torch` đã có sẵn trong môi trường; đừng thêm nó thành phụ thuộc bắt buộc.

## 8. Gợi ý

- Viết hàm `patch_span(p, valid, patch_size) -> (lo, hi)` và dùng nó ở **cả hai** chiều (tính thống kê và mở rộng mask). Một nguồn sự thật cho biên.
- Viết `validate_policy_output(...)` tách riêng để test không cần dựng cả batch.
- Đặt `RowReport` ngay từ đầu; nó biến bug "hàng thứ mấy" thành câu trả lời hiển nhiên.
- Nếu muốn hỗ trợ `(B, L, F)`, xử lý mask ở 2 chiều đầu rồi broadcast — đừng viết logic riêng cho từng rank.

## 9. Mở rộng

- **Adapter `torch` thật**: chỉ ánh xạ 5 thành viên; thêm test `mask.to(batch.device)`.
- **Policy từ bài 41**: adapter chuyển `PlanResult.patch_indices` sang `PolicyOutput`; kiểm tra tổng khớp.
- **Nhóm batch không đều**: thay list `valid_lengths` bằng tensor độ dài, thêm test với hàng dài 1 điểm.
- **Mask theo kênh**: giữ patch index nhưng trả thêm tập kênh; bridge phải phát mask `(B, L, F)` với luật pad ở hai chiều đầu.
- **Đo lường**: đếm số lần policy được gọi và tổng điểm bị che, xuất vào `RowReport` để so các policy khác nhau.
