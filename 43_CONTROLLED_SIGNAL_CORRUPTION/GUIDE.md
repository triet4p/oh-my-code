# GUIDE 43 — Biến dạng tín hiệu có kiểm soát

## 1. Đọc nguồn đúng cách

Ba thứ trong nguồn là **hợp đồng**, không phải chi tiết ngẫu nhiên:

1. Con số biên của từng cơ chế — chép chính xác, đừng "làm tròn cho đẹp".
2. Việc tách `NUISANCES` khỏi cơ chế biến dạng — nhiễu không được tạo tín hiệu bất thường.
3. `RESERVED_FAMILIES` — hai họ bị loại khỏi module sinh, nên chúng phải **không thể** xuất hiện qua API của bạn.

Câu *"nothing here reads generator family code"* là một ràng buộc kiến trúc: bộ biến dạng không được biết vì sao dữ liệu bị lỗi. Hệ quả thực dụng: API không có tham số `family`, và nếu fixture có khóa đó thì phải bị từ chối (`UnknownParameter`).

## 2. Thiết kế

### 2.1 Một bảng, không phải năm khối if

```text
PARAM_SPEC = {
  "level_drift": {"offset": Bound(-3.0, 3.0)},
  "relative_gain_drift": {"gain": Bound(-0.15, 0.15)},
  "timing_shift": {"steps": Bound(-4, 4, integer=True)},
  "transient": {"amplitude": Bound(-4.0, 4.0),
                 "width": Bound(1, None, dynamic="quarter")},
  "persistent_degradation": {"shift": Bound(-2.0, 2.0),
                              "var_scale": Bound(-0.5, 0.5)},
}
```

Bảng này phục vụ ba việc cùng lúc: kiểm tra thiếu/thừa tham số, kẹp, và sinh nhật ký. Nếu bạn viết rời, ba nơi sẽ trôi khỏi nhau sau lần sửa thứ hai.

### 2.2 Đối tượng kết quả

- `MechanismResult(channel, values, span, requested, applied, clamped)`.
- `audit` là `list[MechanismResult]` — chính là đầu ra JSON.

Giữ `requested` là **bản sao** dict trước khi kẹp; nếu bạn kẹp tại chỗ rồi mới ghi, "trước" và "sau" sẽ giống nhau và nhật ký vô dụng.

### 2.3 Bất biến về bất biến (immutability)

Đừng sửa `channels` đầu vào. Sao chép sâu ngay đầu hàm, làm việc trên bản sao. Test "input không đổi" phải chạy cho cả trường hợp có ngoại lệ giữa đường: nếu bạn sửa dần rồi mới phát hiện op sau sai, fixture gốc đã hỏng.

## 3. Thứ tự cài đặt

### Bước 1 — Chuẩn hoá kênh

Sắp tên kênh theo từ điển một lần, dùng danh sách này cho mọi vòng lặp (kể cả `nuisance_noise`). Nhờ vậy thứ tự tiêu thụ PRNG không phụ thuộc thứ tự khóa JSON.

### Bước 2 — Kiểm tra toàn bộ, chưa thực thi

Duyệt `ops` và `nuisances`, kiểm tra: mechanism tồn tại, không thuộc reserved, đủ tham số, không thừa, kiểu đúng. Chỉ khi tất cả hợp lệ mới bắt đầu áp. Đây là "preflight" — cùng nguyên tắc với installer kiểm tra payload trước khi copy.

Nếu bạn thực thi ngay khi gặp, op thứ ba sai sẽ để lại hai op đã áp; kết quả không được trả nhưng fixture nội bộ đã đổi.

### Bước 3 — Kẹp

Một hàm `clamp(value, lo, hi) -> (applied, was_clamped)`. Với `timing_shift`, kiểm tra `isinstance(value, int)` **trước** khi kẹp (đừng để `3.7` bị kẹp thành `3`).

Với `width`, biên trên phụ thuộc `L`: `ceil(0.25 * L)`. Cẩn thận `L=1` ⇒ biên trên `1`; `L=5` ⇒ `ceil(1.25) = 2`.

### Bước 4 — Năm cơ chế

Viết mỗi cơ chế thành hàm thuần `f(values, params) -> (new_values, span)`. Chú ý:

- `timing_shift` phải tạo mảng **mới**, không dịch tại chỗ (dịch tại chỗ theo hướng tăng sẽ ghi đè dữ liệu chưa đọc).
- `transient` cắt `hi = min(lo + width, L)`; `center` âm hoặc `>= L` phải được xử lý theo luật: kẹp `center` vào `[0, L-1]` và ghi vào `applied`.
- `persistent_degradation` áp cho `t >= start`; nếu `start >= L` thì `span` rỗng và **không** đổi gì — vẫn ghi record.
- Chia cho 0 không xuất hiện ở đây, nhưng `1 + var_scale` có thể bằng `0.5`; đừng nhầm với phép "chuẩn hoá".

### Bước 5 — Nhiễu

Nhiễu **không** nhận `labels`. Nếu chữ ký hàm của bạn có `labels`, bạn đã tạo đường rò. Chỉ `nuisance_noise` gọi PRNG; hai nhiễu còn lại là phép nhân/cộng thuần.

### Bước 6 — Băm manifest

```text
payload = {"channels": result_channels, "audit": audit}
blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
manifest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

Đừng đưa `seed` vào payload nếu bạn muốn hai seed khác nhau cho cùng dữ liệu ra cùng manifest — hoặc đưa vào nếu muốn ngược lại. Ghi quyết định vào README của bạn; SPEC hiện yêu cầu **không** đưa `seed`.

## 4. Cạm bẫy

- **Kẹp làm mất dấu**: `offset = -5.0` kẹp thành `-3.0`, không phải `3.0`. Dùng `max(lo, min(hi, v))`.
- **Sửa list tại chỗ khi dịch thời gian**: `x[2] = x[0]` rồi `x[3] = x[1]` sẽ lan giá trị. Luôn dựng mảng mới.
- **`ceil(0.25*L)` với L lẻ**: `L=5` → `1.25` → `2`. Nếu bạn dùng `int(0.25*L)` sẽ ra `1` và test biên sẽ bắt.
- **PRNG tiêu thụ ngoài ý muốn**: `random.random()` trong một nhánh debug cũng làm lệch toàn bộ chuỗi sau. Tách `rng` thành tham số tường minh.
- **Nhật ký đặt sau khi kẹp**: luôn lưu bản gốc trước.
- **`span` của op toàn kênh**: `[0, L)` không phải `[0, L]`.
- **Float trong JSON**: `5.25` in ổn, nhưng phép nhân chuỗi có thể cho `0.30000000000000004`. Với manifest, điều này là **tốt** (phát hiện khác biệt thật); với so sánh test, dùng `math.isclose`.

## 5. Kiểm thử

| Nhóm | Nội dung |
|---|---|
| Cơ chế | Năm ví dụ 7.1–7.5 của SPEC, so mảng chính xác |
| Kẹp | Mỗi tham số một test vượt biên; khẳng định `requested != applied` và `clamped` |
| Reserved | Hai họ, mỗi họ một test; khẳng định fixture không đổi |
| Nhãn | Có/không nhiễu đều giữ `labels` |
| PRNG | Thêm op không dùng RNG phía trước; kiểm tra phần nhiễu của các kênh sau (theo thứ tự từ điển) không đổi |
| Thứ tự | `[A, B]` khác `[B, A]` với A = shift, B = gain |
| Manifest | Hai lần chạy giống; đổi một tham số thì khác |
| Preflight | Op thứ ba sai ⇒ fixture gốc vẫn nguyên |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src fixtures/clean_multi_channel.json | python -m json.tool
```

Kiểm tra nhanh bất biến "nhãn không đổi":

```bash
python -c "import json,subprocess,pathlib; src=json.load(open('fixtures/clean_multi_channel.json')); out=json.loads(subprocess.check_output(['python','-m','src','fixtures/clean_multi_channel.json'])); print(src['labels']==out['labels'])"
```

Phải in `True`. Kiểm tra hai lần chạy cho cùng manifest:

```bash
python -m src fixtures/clean_multi_channel.json | python -c "import json,sys; print(json.load(sys.stdin)['manifest_sha256'])" > h1.txt
python -m src fixtures/clean_multi_channel.json | python -c "import json,sys; print(json.load(sys.stdin)['manifest_sha256'])" > h2.txt
python -c "print(open('h1.txt').read()==open('h2.txt').read())"
```

Và fixture reserved phải thất bại:

```bash
python -m src fixtures/reserved_attempt.json; echo "exit=$?"
```

Kỳ vọng `exit=2` và thông điệp nêu `ReservedFamily`.

## 7. Gợi ý

- Viết `Bound` như một dataclass nhỏ với `clamp(v) -> (v2, clamped)`; mọi cơ chế dùng chung, test một lần.
- Viết `apply_op(channel, op, L)` trả `(values, span, applied, clamped)`; đừng để mỗi cơ chế tự ghi audit.
- Dùng snapshot test cho toàn bộ output JSON của một fixture nhỏ; nó bắt được cả thay đổi thứ tự khóa.
- Nếu phân vân về `center` ngoài biên, hãy tự chọn luật, ghi vào README, và test đúng luật đó — SPEC chỉ ràng buộc `span` phải nằm trong `[0, L)`.

## 8. Mở rộng

- **Nhiều kênh tương quan**: thêm cơ chế chỉ áp lên một kênh nhưng ảnh hưởng kênh khác — nhưng nhớ: đó là họ gần với `cross_channel_inconsistency`, nên hãy giữ nó **ngoài** tập huấn luyện hoặc đặt tên khác và ghi rõ.
- **Chế độ "strict"**: thay vì kẹp, ném `ParamOutOfRange`; so sánh hai chế độ trên cùng fixture.
- **Báo cáo sức khoẻ**: tỉ lệ `clamped` theo cơ chế, cảnh báo nếu > 20%.
- **Manifest streaming**: băm theo từng kênh để không phải giữ toàn bộ trong bộ nhớ.
- **Tái dùng cho bài 58**: dùng chính bộ biến dạng này để tạo tập "có drift thật" cho detector, và giữ hai họ reserved làm đối chứng phân bố lạ.
