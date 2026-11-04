# GUIDE 41 — Che patch theo tầng quan trọng

Hướng dẫn này **không** chứa lời giải hoàn chỉnh. Nó mô tả cách nghĩ, cấu trúc dữ liệu, thứ tự cài đặt và các điểm dễ sai để bạn tự viết code.

## 1. Bóc tách bài toán

Nguồn gốc là một module sinh mask cho pretraining trên tín hiệu tổng hợp. Ba ý có thể tách ra làm bài tập độc lập:

| Ý trong nguồn | Việc bạn phải làm |
|---|---|
| `M = M_random ∪ M_info ∪ M_block` | Ba tập con rời, hợp đúng ngân sách |
| `(std + 1e-8) * (rng + 1e-8) * (1.0 + deriv)` | Thống kê theo patch |
| `np.percentile(vs, [25,50,75])` | Bốn tầng, định nghĩa percentile rõ ràng |

Phần khó không nằm ở công thức mà ở **ba ràng buộc đồng thời**: tổng đúng, rời nhau, và tất định.

## 2. Thiết kế dữ liệu

Gợi ý các kiểu (đặt tên của bạn, miễn giữ ngữ nghĩa):

- `PatchStats`: `std, range, deriv, score` — dùng `dataclass(frozen=True)` để tránh sửa nhầm.
- `PlanConfig`: `patch_size, mask_ratio, seed, block_len, weights: dict[str, float]`.
- `PlanResult`: `num_patches, total_mask, strata: dict[str, list[int]], stats: list[PatchStats], counts: dict[str, int], mask_by_component: dict[str, list[int]]`.

Hai quyết định quan trọng, hãy ghi lý do vào README của bạn:

1. `stats` chứa `float` — in ra bằng `json.dumps` mặc định có thể khác nhau giữa máy. Nếu muốn golden ổn định, làm tròn khi in (ví dụ 12 chữ số) và ghi rõ.
2. Bạn có chuẩn hoá đầu vào (sắp patch) không? Không nên: thứ tự patch chính là thông tin thời gian.

## 3. Các bước cài đặt

### Bước 1 — Kiểm tra hợp lệ trước khi tính

Kiểm tra **tất cả** điều kiện trong một lượt và ném lỗi đầu tiên theo thứ tự khai báo; đừng để lỗi chia cho 0 xảy ra trước lỗi tham số.

- `patch_size` trước, rồi `len(values) % patch_size`, rồi `mask_ratio`, rồi `seed`, rồi weights.
- Kiểm tra hữu hạn cho từng phần tử `values` — `math.isfinite`.

### Bước 2 — Cắt patch và tính thống kê

Cắt bằng `values[i*patch_size:(i+1)*patch_size]`. Với mỗi patch:

- Trung bình quần thể rồi phương sai quần thể; chú ý **không** dùng `statistics.stdev` (chia `n-1`).
- `deriv` cho `patch_size == 1` phải bằng `0`, không phải `|x - x|/0`.
- `range` là tên dễ đè lên builtin; đặt `span` hoặc `amp`.

### Bước 3 — Ngưỡng tứ phân vị

Đừng gọi `statistics.quantiles` (nó dùng phương pháp khác và trả về các điểm cắt). Tự viết:

- Sắp bản sao `score` tăng dần.
- Với mỗi `q`, `pos = (n-1)*q/100`, nội suy giữa hai phần tử kề.
- Kiểm tra bằng tay: `n=8`, `q=25` ⇒ `pos = 1.75` ⇒ `s[1] + 0.75*(s[2]-s[1])`. Với `s = 0..7` cho `1.75`. Nếu code của bạn trả `1.0` hoặc `2.0`, bạn đang dùng nearest-rank.

### Bước 4 — Gán tầng đúng biên

Ba phép so sánh có **hai dấu `<` và hai dấu `>=`**; đảo một dấu là mất tính phân hoạch. Test riêng trường hợp `score == p25` phải rơi vào `transition`, `score == p75` phải rơi vào `extreme`.

### Bước 5 — Ngân sách

`M = floor(ratio*N + 0.5)` — cẩn thận với số float như `0.285 * 7 = 1.9949999...`: đây chính là lý do dùng `+0.5` rồi `floor` thay vì `round()` (Python dùng banker's rounding).

Sau đó áp dụng phần dư lớn nhất. Cài đặt gợi ý: tính `base` và `dư`, sắp các thành phần theo `(-dư, thứ tự cố định)`, cộng 1 cho `thiếu` thành phần đầu.

### Bước 6 — Ba bộ chọn

Thứ tự **block → info → random** là bắt buộc vì mỗi bước thu hẹp pool của bước sau.

- Block: duyệt `start` theo `(-score[start], start)`; một run hợp lệ khi **mọi** vị trí trong `[start, min(start+block_len, N))` chưa bị chọn. Nếu run dài hơn phần còn thiếu của ngân sách block, cắt bớt — nhưng phải ghi vào báo cáo là đã cắt, nếu không test đếm sẽ lệch.
- Info: lọc theo nhãn tầng trước, rồi sắp theo `(-score, index)`. Khi chuyển sang tầng dự phòng, đánh cờ `overflow_used`.
- Random: để tất định và không phụ thuộc `set` (thứ tự không xác định), giữ pool là **list đã sắp** và dùng swap-remove: chọn `k = pick(len(pool))`, lấy `pool[k]`, thay `pool[k] = pool[-1]`, `pop()`.

### Bước 7 — Lắp output

Sắp `mask`, dựng `mask_by_component`, và **tự kiểm tra** ngay trước khi trả: tổng, rời nhau, phủ đúng. Ba dòng assert này rẻ hơn nhiều so với việc debug một fixture lệch 1 phần tử.

## 4. Cạm bẫy

- **Chia `k-1` thay vì `k`** cho std: sai số nhỏ nhưng làm lệch thứ hạng ở patch gần bằng nhau.
- **`set` không có thứ tự**: dùng `set` để kiểm tra rời nhau thì tốt, để sinh output thì không.
- **Percentile trên `score` chưa sắp**: nội suy yêu cầu mảng đã sắp.
- **Hoà điểm**: nếu chỉ sắp theo `score`, thứ tự phụ thuộc thuật toán sắp (ổn định hay không). Luôn thêm khóa phụ là chỉ số.
- **Trọng số tổng không bằng 1**: chấp nhận sai số `1e-9`, nhưng sau đó chuẩn hoá lại trước khi nhân `M`, nếu không `sum(base)` có thể vượt `M`.
- **`mask_ratio * N` là float**: đừng so sánh `==` với 0.5.

## 5. Kiểm thử

Tối thiểu các nhóm sau (đặt trong `tests/test_masking.py`):

| Nhóm | Điều cần khẳng định |
|---|---|
| Phân tầng | Ví dụ 7.1 cho đúng 4 bucket; biên `== p25` vào `transition` |
| Suy biến | Ví dụ 7.3: toàn bộ vào `extreme` |
| Ngân sách | Ví dụ 7.2 cho `(2,1,1)` và `(1,1,0)`; `M` đúng với 20 cặp `(ratio, N)` |
| Bất biến | Sinh 200 fixture giả ngẫu nhiên, assert 3 bất biến ở mục 8 của SPEC |
| Lỗi | Mỗi ngoại lệ một test, khẳng định cả **tên** lẫn khóa bị nêu |
| Tất định | Gọi hai lần, so `json.dumps(..., sort_keys=True)` |

## 6. Kiểm chứng độc lập

Từ thư mục bài:

```bash
python --version                # phải >= 3.12
python -m unittest discover -s tests -v
python -m src fixtures/basic.json > out.json
python -c "import json,sys; d=json.load(open('out.json')); print(d['total_mask'], len(d['mask']), sum(d['component_counts'].values()))"
```

Ba số in ra phải bằng nhau. Kiểm tra chéo bằng tay:

```bash
python -c "import json; d=json.load(open('out.json')); print(d['strata'])"
```

Đối chiếu với mục 7.1 của SPEC khi dùng fixture `basic.json`.

Nếu bạn muốn kiểm tra tính tất định ở mức byte:

```bash
python -m src fixtures/basic.json > a.json && python -m src fixtures/basic.json > b.json
python -c "print(open('a.json','rb').read() == open('b.json','rb').read())"
```

## 7. Gợi ý (không phải lời giải)

- Viết `percentile(sorted_vals, q)` **trước** và test nó riêng; mọi lỗi tầng sau đó sẽ dễ khoanh vùng.
- Viết `allocate(total, weights)` như một hàm thuần, không phụ thuộc patch — nó là bài toán con độc lập rất dễ test.
- Ba bộ chọn nên nhận cùng một "taken" set và trả về list; đừng để chúng tự sửa state của nhau.
- Nếu thấy mình đang viết `if` lồng quá 3 cấp trong bộ chọn block, hãy tách hàm `runs(start, length, taken)`.

## 8. Mở rộng

- **Mask 2 chiều**: patch theo lưới `H×W`, block là hình chữ nhật; giữ nguyên ba thành phần.
- **Curriculum**: nhiều mức `mask_ratio` tăng dần, kiểm tra mask lồng nhau (`M(0.3) ⊂ M(0.6)`).
- **So sánh baseline**: mask thuần ngẫu nhiên cùng `M`; so phân bố tầng bị che để thấy "info" có thiên lệch.
- **Chính sách theo tầng**: đặt quota tối thiểu cho `extreme` thay vì để bộ chọn tự do.
- **Tái sử dụng**: xuất `PlanResult` thành một policy object cho bài 42.
