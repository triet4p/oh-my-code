# SPEC 43 — Biến dạng tín hiệu có kiểm soát

## 1. Đầu vào

### 1.1 Fixture

```json
{
  "seed": 4242,
  "channels": {
    "temp": [1.0, 2.0, 3.0, 4.0],
    "press": [10.0, 20.0, 30.0, 40.0]
  },
  "labels": {"temp": [0, 0, 1, 1], "press": [0, 0, 0, 0]},
  "ops": [
    {"mechanism": "level_drift", "channel": "temp", "offset": 2.5},
    {"mechanism": "transient", "channel": "press", "amplitude": 2.0, "center": 1, "width": 3}
  ],
  "nuisances": [
    {"mechanism": "nuisance_gain", "channel": "temp", "gain": 1.5}
  ]
}
```

| Khóa | Kiểu | Ghi chú |
|---|---|---|
| `seed` | int `0 <= seed < 2^32` | Bắt buộc |
| `channels` | object `tên -> list[float]` | Mọi kênh cùng độ dài `L`, `L >= 1` |
| `labels` | object `tên -> list[int]` | Cùng độ dài; giá trị `0` hoặc `1` |
| `ops` | danh sách thao tác biến dạng | Áp theo đúng thứ tự khai báo |
| `nuisances` | danh sách nhiễu nền | Áp **sau** mọi `ops` |

### 1.2 Bảng biên (bắt buộc khớp nguồn)

| Cơ chế | Tham số | Biên |
|---|---|---|
| `level_drift` | `offset` | `|offset| <= 3.0` |
| `relative_gain_drift` | `gain` | `|gain| <= 0.15` |
| `timing_shift` | `steps` (số nguyên) | `|steps| <= 4` |
| `transient` | `amplitude`, `width` | `|amplitude| <= 4.0`; `1 <= width <= ceil(0.25 * L)` |
| `persistent_degradation` | `shift`, `var_scale` | `|shift| <= 2.0`; `|var_scale| <= 0.5` |

Ba nhiễu (biên do bài tập định nghĩa, `[DESIGN]`):

| Nhiễu | Tham số | Biên |
|---|---|---|
| `nuisance_gain` | `gain` | `0.5 <= gain <= 2.0` |
| `nuisance_offset` | `offset` | `|offset| <= 3.0` |
| `nuisance_noise` | `amplitude` | `0.0 <= amplitude <= 0.1` |

## 2. Ngữ nghĩa từng cơ chế

Ký hiệu: `x` là mảng kênh độ dài `L`, `mean(x)` là trung bình toàn kênh.

### 2.1 `level_drift`

```text
x'[t] = x[t] + offset          với |offset| kẹp về 3.0
```

### 2.2 `relative_gain_drift`

```text
x'[t] = x[t] * (1 + gain)      với |gain| kẹp về 0.15
```

### 2.3 `timing_shift`

`steps > 0` (dịch phải): `x'[t] = x[t - steps]` nếu `t >= steps`, ngược lại `x'[0]` (bơm giá trị đầu).
`steps < 0` (dịch trái, `s = -steps`): `x'[t] = x[t + s]` nếu `t + s < L`, ngược lại `x[L-1]`.
`steps = 0`: không đổi. `steps` phải là số nguyên; giá trị không nguyên ⇒ `InvalidParameter`.

### 2.4 `transient`

Thêm `amplitude` vào các mẫu trong cửa sổ `[center, center + width)` đã cắt theo `L`.

```text
lo = min(center, L - 1); hi = min(lo + width, L)
x'[t] = x[t] + amplitude       với lo <= t < hi
```

`width` kẹp về `[1, ceil(0.25 * L)]`; `amplitude` kẹp về `[-4.0, 4.0]`.

### 2.5 `persistent_degradation`

Từ chỉ số `start` (mặc định `0`) đến hết:

```text
x'[t] = shift + x[t] * (1 + var_scale)     với t >= start
```

`shift` kẹp `[-2.0, 2.0]`; `var_scale` kẹp `[-0.5, 0.5]`.

### 2.6 Nhiễu

```text
nuisance_gain:    x'[t] = x[t] * gain
nuisance_offset:  x'[t] = x[t] + offset
nuisance_noise:   x'[t] = x[t] + u, u ~ Uniform(-amplitude, +amplitude)
```

`nuisance_noise` tiêu thụ PRNG theo thứ tự `t` tăng dần, kênh theo thứ tự từ điển.

## 3. Thứ tự áp dụng

```text
1. kiểm tra toàn bộ fixture (không sửa gì)
2. với từng op trong "ops", theo thứ tự khai báo:
     - kiểm tra mechanism, tham số
     - kẹp tham số
     - áp lên bản sao kênh
     - ghi AuditRecord
3. với từng nuisance theo thứ tự khai báo: như trên
4. băm manifest
```

Không được sắp lại `ops` — thứ tự là một phần ngữ nghĩa (dịch thời gian rồi gain khác gain rồi dịch thời gian).

## 4. Đầu ra

Với fixture ở mục 1.1:

- `temp`: `[1,2,3,4] + 2.5 = [3.5,4.5,5.5,6.5]`, rồi `nuisance_gain 1.5` ⇒ `[5.25, 6.75, 8.25, 9.75]`.
- `press`: transient tại `[1, 3)` với `amplitude 2.0` ⇒ `[10.0, 22.0, 32.0, 40.0]`.

```json
{
  "channels": {
    "press": [10.0, 22.0, 32.0, 40.0],
    "temp": [5.25, 6.75, 8.25, 9.75]
  },
  "labels": {"press": [0, 0, 0, 0], "temp": [0, 0, 1, 1]},
  "audit": [
    {
      "mechanism": "level_drift",
      "channel": "temp",
      "requested": {"offset": 2.5},
      "applied": {"offset": 2.5},
      "clamped": false,
      "span": [0, 4]
    },
    {
      "mechanism": "transient",
      "channel": "press",
      "requested": {"amplitude": 2.0, "center": 1, "width": 3},
      "applied": {"amplitude": 2.0, "center": 1, "width": 2},
      "clamped": true,
      "span": [1, 3]
    },
    {
      "mechanism": "nuisance_gain",
      "channel": "temp",
      "requested": {"gain": 1.5},
      "applied": {"gain": 1.5},
      "clamped": false,
      "span": [0, 4]
    }
  ],
  "manifest_sha256": "…64 ký tự hex…"
}
```

- `labels` **giữ nguyên** so với đầu vào, kể cả khi có nuisance.
- `audit` dài đúng `len(ops) + len(nuisances)` và cùng thứ tự thực thi.
- `span` là `[lo, hi)` chỉ số bị ảnh hưởng; với op toàn kênh là `[0, L)`.
- `manifest_sha256 = sha256(canonical_json({"channels": ..., "audit": ...}))`, trong đó `canonical_json` dùng `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, và float in bằng `repr` (mặc định của `json`).

## 5. Kiểm tra hợp lệ

| Điều kiện | Ngoại lệ |
|---|---|
| `channels` rỗng hoặc có kênh rỗng | `EmptyChannel` |
| độ dài các kênh khác nhau | `ChannelLengthMismatch` |
| `labels` thiếu kênh hoặc sai độ dài | `LabelMismatch` |
| nhãn không thuộc `{0,1}` | `InvalidLabel` |
| `mechanism` không thuộc 5 cơ chế + 3 nhiễu | `UnknownMechanism` |
| `mechanism` thuộc `RESERVED_FAMILIES` | `ReservedFamily` |
| thiếu tham số bắt buộc | `MissingParameter` |
| tham số không phải số hữu hạn | `InvalidParameter` |
| tham số lạ (ví dụ `family`) | `UnknownParameter` |
| `timing_shift.steps` không nguyên | `InvalidParameter` |
| `seed` ngoài miền | `InvalidSeed` |

`ReservedFamily` phải nêu tên họ và lý do ngắn: đây là tập giữ riêng, không sinh trong tập huấn luyện.

## 6. Tính tất định

- Cùng fixture, cùng seed ⇒ cùng `channels` và cùng `audit` (đến từng bit float).
- Chỉ `nuisance_noise` tiêu thụ PRNG. PRNG: `[DESIGN]` LCG 32-bit

```text
state = seed
next_u(): state = (1664525*state + 1013904223) mod 2^32 ; return state / 2^32
```

- Thao tác không dùng PRNG phải **không** tiêu thụ số ngẫu nhiên — nếu không, thêm một `level_drift` sẽ làm thay đổi toàn bộ nhiễu phía sau. Test điều này.

## 7. Ví dụ cụ thể

### 7.1 Level drift và kẹp

`x = [1, 2, 3]`, `offset = 2.5` ⇒ `[3.5, 4.5, 5.5]`, `clamped = false`.
`offset = -5.0` ⇒ kẹp `-3.0` ⇒ `[-2.0, -1.0, 0.0]`, `clamped = true`, `requested.offset = -5.0`, `applied.offset = -3.0`.

### 7.2 Relative gain

`x = [10, 20, 30]`, `gain = 0.10` ⇒ `[11.0, 22.0, 33.0]`.
`gain = 0.5` ⇒ kẹp `0.15` ⇒ `[11.5, 23.0, 34.5]`.

### 7.3 Timing shift

`x = [1, 2, 3, 4, 5]`:

- `steps = 2` ⇒ `[1, 1, 1, 2, 3]`.
- `steps = -3` ⇒ `[4, 5, 5, 5, 5]`.
- `steps = 7` ⇒ kẹp `4` ⇒ `[1, 1, 1, 1, 1]`.

### 7.4 Transient

`x = [0,0,0,0,0,0,0,0]` (L=8), `amplitude = 2.5`, `center = 2`, `width = 3`.
`ceil(0.25*8) = 2` ⇒ `width` kẹp về `2` ⇒ `[0,0,2.5,2.5,0,0,0,0]`, `clamped = true`, `span = [2, 4)`.

### 7.5 Persistent degradation

`x = [2, 4, 6, 8]`, `start = 2`, `shift = 1.0`, `var_scale = -0.5`:

- `t = 2`: `1 + 6*0.5 = 4.0`
- `t = 3`: `1 + 8*0.5 = 5.0`

⇒ `[2, 4, 4.0, 5.0]`.

### 7.6 Nuisance không đổi nhãn

Fixture có `labels.temp = [0,0,1,1]`; sau `nuisance_gain` với `gain = 2.0`, `channels.temp = [2,4,6,8]` nhưng `labels.temp` vẫn `[0,0,1,1]`.

### 7.7 Họ để dành

`{"mechanism": "wrong_transition", ...}` ⇒ `ReservedFamily`, và **không** có kênh nào bị sửa (kiểm tra bằng so sánh sâu).

## 8. Tiêu chí chấp nhận quan sát được

1. Năm ví dụ 7.1–7.5 cho đúng mảng như ghi, kể cả cờ `clamped` và `span`.
2. Mọi giá trị áp dụng thoả bảng biên ở mục 1.2 — kiểm tra bằng vòng lặp trên 500 fixture sinh ngẫu nhiên.
3. Hai họ để dành luôn ném `ReservedFamily`; fixture gốc không bị sửa.
4. `labels` đầu ra bằng `labels` đầu vào trong mọi trường hợp (kể cả có nhiễu).
5. Thêm một op không dùng PRNG vào trước `nuisance_noise` **không** làm đổi phần nhiễu đã sinh cho cùng phần còn lại — hoặc nếu đổi, đó là hành vi có chủ đích và phải ghi trong README của bạn.
6. `manifest_sha256` giống nhau qua hai lần chạy; đổi bất kỳ tham số nào ⇒ khác.
7. `audit` cùng độ dài và thứ tự với `ops + nuisances`.
8. CLI trả mã thoát `2` khi fixture không hợp lệ, `0` khi thành công.

## 9. Non-goals

- Không sinh tín hiệu sạch, không sinh nhãn, không đánh giá mô hình.
- Không mô phỏng họ `wrong_transition` / `cross_channel_inconsistency` dưới bất kỳ dạng nào.
- Không hỗ trợ dữ liệu nhiều file, chuỗi không đều, hay giá trị phức.
