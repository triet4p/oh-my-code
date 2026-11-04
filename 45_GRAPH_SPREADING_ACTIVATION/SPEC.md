# SPEC 45 — Lan truyền kích hoạt trên đồ thị có kiểu cạnh

## 1. Định dạng fixture

File văn bản UTF-8, mỗi dòng một lệnh, trường cách nhau bởi khoảng trắng. Dòng bắt đầu bằng `#` là chú thích, dòng trống bị bỏ qua.

```text
# chain.txt
param delta 0.8
param a_max 2.0
param epsilon 0.01
param max_steps 10
param max_fires 1

seed a 1.0

edge a b 1.0 AoCausal
edge b c 1.0 Semantic
```

| Lệnh | Tham số | Ghi chú |
|---|---|---|
| `param` | `tên giá_trị` | Bốn tên hợp lệ: `delta`, `a_max`, `epsilon`, `max_steps`, `max_fires` |
| `seed` | `nút giá_trị` | Nút được tạo nếu chưa có; `giá_trị >= 0` |
| `edge` | `từ đến trọng_số loại` | `trọng_số >= 0`; `loại` thuộc bảng 2.1 |

Tham số thiếu dùng mặc định của nguồn: `delta = 0.8`, `a_max = 2.0`, `epsilon = 0.01`, `max_steps = 10`, `max_fires = 3`.

`max_steps` và `max_fires` là số nguyên. `delta`, `a_max`, `epsilon` là số thực hữu hạn.

Cạnh có thể trùng cặp `(từ, đến)` — chúng là hai cạnh riêng và cộng dồn độc lập.

## 2. Thuật toán

### 2.1 Hệ số theo loại cạnh

| Loại | `mu` |
|---|---|
| `AoCausal` | 2.0 |
| `Entity` | 1.5 |
| `Transition` | 1.8 |
| `Semantic` | 0.8 |

Loại khác ⇒ `UnknownEdgeKind` (mã thoát `2`).

### 2.2 Trạng thái

- `A: Vec<f64>` — kích hoạt hiện tại, khởi tạo `0.0`, rồi gán giá trị `seed`.
- `fires: Vec<u32>` — số lần đã phát của mỗi nút, khởi tạo `0`.
- `refractory: HashSet<usize>` — các nút đã phát ở bước **trước**.
- `steps_run: u32`.

### 2.3 Một bước

```text
buf[v] = 0.0 cho mọi v
fired_this_step = {}

với u trong danh sách nút theo thứ tự từ điển:
    nếu A[u] >= epsilon
       và fires[u] < max_fires
       và u không thuộc refractory:
        fired_this_step thêm u
        fires[u] += 1
        với mỗi cạnh (u -> v, w, kind) theo thứ tự khai báo trong fixture:
            buf[v] += A[u] * w * mu(kind) * delta

với mọi v: A[v] = min(A[v] + buf[v], a_max)
refractory = fired_this_step
steps_run += 1
```

Ba điểm bắt buộc:

1. **Đọc `A[u]` tại đầu bước**, không đọc giá trị vừa cập nhật trong cùng bước — đây là lan truyền đồng bộ.
2. **Cộng dồn vào `buf` rồi mới kẹp**; không kẹp sau từng cạnh. Kết quả nhờ vậy không phụ thuộc thứ tự cạnh.
3. `refractory` được **thay thế**, không cộng dồn: nút phát ở bước `t` chỉ bị chặn ở `t+1`.

### 2.4 Điều kiện dừng

Lặp tối đa `max_steps` bước. Sau mỗi bước, dừng khi **đồng thời** hai điều kiện:

1. `fired_this_step` rỗng, **và**
2. không còn nút nào *có thể* phát về sau: không tồn tại `v` thoả `A[v] >= epsilon` và `fires[v] < max_fires`.

Điều kiện 2 là bắt buộc vì trơ chỉ chặn **một** bước: nút đang trơ vẫn có thể phát ở bước sau, nên không được dừng chỉ vì bước hiện tại rỗng. `steps_run` đếm cả bước rỗng cuối cùng.

Hệ quả: chuỗi ở 5.1 dừng ở bước 4 (bước 4 rỗng và mọi hạn ngạch đã dùng); ví dụ 5.3 **tiếp tục** qua bước 2 (rỗng nhưng `a` còn hạn ngạch) và dừng ở bước 4.

Nếu `max_steps = 0`, không chạy bước nào, `steps_run = 0`, `A` chỉ gồm giá trị seed.

## 3. Đầu ra

In ra stdout, mỗi nút một dòng, ba cột cách nhau bởi TAB:

```text
<node>\t<activation>\t<fired>
```

- Thứ tự: `activation` giảm dần; hoà thì `node` tăng dần theo so sánh chuỗi byte.
- `activation` in bằng `{:.6}` (ví dụ `1.600000`).
- Sau các dòng nút, in một dòng tổng kết: `steps\t<steps_run>`.
- Không in header, không in log ra stdout.

Ví dụ với `fixtures/chain.txt` (mục 5.1):

```text
a	1.000000	1
b	1.600000	1
c	1.024000	1
steps	4
```

## 4. Kiểm tra hợp lệ

| Điều kiện | Lỗi |
|---|---|
| Dòng không bắt đầu bằng lệnh hợp lệ | `MalformedLine(n)` |
| `param` lạ tên | `UnknownParam` |
| `max_steps`/`max_fires` âm hoặc không nguyên | `InvalidParam` |
| `delta`/`a_max`/`epsilon` âm, không hữu hạn | `InvalidParam` |
| `a_max <= 0` | `InvalidParam` |
| `seed` âm | `InvalidSeed` |
| `edge` thiếu trường hoặc trọng số âm | `MalformedEdge` |
| loại cạnh lạ | `UnknownEdgeKind` |
| đồ thị không có nút nào | `EmptyGraph` |
| nút đích của `edge` chưa từng xuất hiện | hợp lệ — tự tạo nút với `A = 0` |

`epsilon = 0` hợp lệ về mặt kiểu nhưng khiến mọi nút có `A >= 0` phát liên tục cho tới khi hết hạn ngạch; SPEC cho phép, test phải khẳng định nó dừng nhờ hạn ngạch chứ không treo.

## 5. Ví dụ cụ thể

### 5.1 Chuỗi, hạn ngạch 1

`fixtures/chain.txt` như mục 1 (`max_fires = 1`, `max_steps = 10`):

| Bước | Nút phát | Tính | Sau bước |
|---|---|---|---|
| 1 | `a` | `b += 1.0 * 1.0 * 2.0 * 0.8 = 1.6` | `A = {a:1.0, b:1.6, c:0}` |
| 2 | `b` | `c += 1.6 * 1.0 * 0.8 * 0.8 = 1.024` | `A = {a:1.0, b:1.6, c:1.024}` |
| 3 | `c` | không có cạnh ra | không đổi |
| 4 | — | không nút nào phát (mọi hạn ngạch đã dùng) | dừng |

Kết quả đúng như khối output ở mục 3.

### 5.2 Bão hoà

Ba cạnh song song `a -> b`, mỗi cạnh `w = 1.0`, `AoCausal`; `delta = 0.8`, `a_max = 2.0`, seed `a = 1.0`:

- `buf[b] = 3 * (1.0 * 1.0 * 2.0 * 0.8) = 4.8`
- `A[b] = min(0 + 4.8, 2.0) = 2.0`

Nếu ai đó kẹp sau từng cạnh, kết quả vẫn `2.0`; nhưng nếu sau này thêm cạnh trọng số âm, hai cách sẽ khác. SPEC chọn cộng-dồn-rồi-kẹp.

### 5.3 Hạn ngạch và trơ

Node `a` là seed `1.0`, **không có cạnh ra**, `max_fires = 2`, `max_steps = 10`, `epsilon = 0.01`:

| Bước | Phát? | Lý do |
|---|---|---|
| 1 | có | `fires[a] = 1`; vào `refractory` |
| 2 | không | `a` thuộc `refractory` |
| 3 | có | hết trơ, `fires[a] = 2` |
| 4 | không | hết hạn ngạch |

`steps_run = 4`, dòng kết quả `a	1.000000	2`.

### 5.4 Chu trình

`a -> b` và `b -> a`, mỗi cạnh `w = 1.0`, `Semantic`, `delta = 0.8`, `a_max = 2.0`, `max_fires = 3`:

- Bước 1: `a` phát ⇒ `b = 0.64`.
- Bước 2: `b` phát ⇒ `a = 1.0 + 0.64*0.8*0.8 = 1.4096`.
- Bước 3: `a` phát lại (không trơ) ⇒ `b = 0.64 + 1.4096*0.64 = 1.542144`.
- Bước 4: `b` phát ⇒ `a = min(1.4096 + 1.542144*0.64, 2.0) = 2.0` (chạm trần).
- Bước 5: `a` phát lần 3 ⇒ `b = min(1.542144 + 2.0*0.64, 2.0) = 2.0`.
- Bước 6: `b` phát lần 3 ⇒ không cạnh nào còn hiệu lực vì `a` đã hết hạn ngạch? Không — `a` nhận thêm nhưng không phát nữa; `A[a]` vẫn `2.0`.
- Bước 7: không nút nào phát ⇒ dừng.

`steps_run = 7`.

### 5.5 Chạm `max_steps`

Cùng 5.4 nhưng `max_steps = 3`: chạy đúng 3 bước, `steps_run = 3`, `A = {a:1.4096, b:1.542144}`. Không được chạy tiếp để "ổn định".

## 6. Tiêu chí chấp nhận

1. `cargo test` xanh, gồm tối thiểu bốn test số học ứng với 5.1–5.4.
2. `cargo run --quiet -- fixtures/chain.txt` in đúng khối ở mục 3 (so từng byte).
3. `a_max` không bao giờ bị vượt trong bất kỳ fixture nào (kiểm tra bằng vòng lặp trên toàn bộ đầu ra).
4. `fires[v] <= max_fires` với mọi nút.
5. Không nút nào phát ở hai bước liên tiếp (kiểm tra bằng log bước, hoặc suy ra từ 5.3).
6. Đổi thứ tự khai báo **cạnh** không đổi kết quả số học (chỉ đổi thứ tự cộng dồn nội bộ); đổi thứ tự **nút** trong file không đổi output đã sắp xếp.
7. Fixture lỗi trả mã thoát `2` và thông điệp nêu dòng/nút sai.
8. Chạy hai lần cho output giống hệt.

## 7. Non-goals

- Không async, không đa luồng, không khoá.
- Không lưu/truy vấn đồ thị ngoài tiến trình.
- Không tối ưu cho đồ thị lớn; `O(max_steps * E)` là chấp nhận được.
- Không mô phỏng sinh học thần kinh; đây là mô hình kỹ thuật.
