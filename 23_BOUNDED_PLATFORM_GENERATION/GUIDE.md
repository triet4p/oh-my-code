# GUIDE 23 — Thiết kế bộ sinh platform

## 1. Kiến trúc

```
platform_gen/
├─ rng.py         # SplitMix64
├─ config.py      # dataclass + validate + digest
├─ generator.py   # generate_platform, initial_field, advance
├─ cli.py
└─ models.py
fixtures/
├─ config.json
├─ seeds.json
├─ cameras/seed-9.json
└─ expected/seed-9-initial.json
```

`generator.py` không đọc file, không in, không biết CLI. Đây là điều kiện để test tất định.

## 2. PRNG

```python
MASK = (1 << 64) - 1

class SplitMix64:
    def __init__(self, seed: int):
        self.state = seed & MASK

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def next_unit(self) -> float:
        return (self.next_u64() >> 11) / float(1 << 53)
```

Đây là **khung**, không phải lời giải đầy đủ. Lưu ý Python tự xử lý số lớn; nếu viết bằng ngôn ngữ khác, phải ép kiểu không dấu 64-bit sau mỗi phép nhân.

## 3. Cấu trúc dữ liệu

```python
@dataclass
class Platform:
    index: int
    x: float
    y: float
    w: float
    h: float
    dx: float
    box: str | None
    kind: str

@dataclass
class Field:
    platforms: list[Platform]
    next_index: int
    seed: int
    config: Config
    spawn_guard_hits: int = 0
```

Dùng `list` cho cửa sổ; nếu muốn O(1) loại đầu, dùng `collections.deque`. Nhưng output cần truy cập theo chỉ số, nên `deque` vẫn ổn với `list(field.platforms)`.

## 4. Thứ tự thực hiện

1. Validate config **một lần**; chuyển sang kiểu số thực.
2. Khởi tạo RNG.
3. Sinh nền.
4. Sinh 15 platform, cập nhật `last_x`.
5. Trả `Field`.

Khi `advance`:

1. Kiểm tra field không rỗng.
2. Lặp tối đa `config.window` lần:
   - lấy top;
   - nếu đã đủ xa → dừng;
   - sinh;
   - append;
   - cắt nếu vượt window.
3. Nếu chạm guard, tăng `spawn_guard_hits` và trả cảnh báo.

Không cắt cửa sổ **trước** khi append; nếu không, bạn có thể xóa top vừa dùng để tính `last_x`.

## 5. Bẫy thường gặp

- **Rút số theo điều kiện**: nếu chỉ rút `u_speed` khi platform di chuyển, dãy số lệch giữa các seed. Luôn rút đủ 5.
- **Clamp sai thứ tự**: clamp trước khi dùng `last_x` cho platform sau là đúng; nhưng phải cập nhật `last_x = x` **sau clamp**, không phải `x_raw`.
- **Biên hộp**: điều kiện là `y < height - 300`, không phải `<=`.
- **Cắt cửa sổ bằng `removeAt(0)` trên list lớn** không sao với 60, nhưng nếu mở rộng window thì dùng deque.
- **Dùng `top` sau khi cắt**: giữ tham chiếu tới platform cuối trước khi thay đổi danh sách.
- **So sánh float bằng `==` trong test**: dùng `math.isclose(..., abs_tol=1e-9)`.
- **Seed âm**: chuẩn hóa bằng `seed & MASK`; nếu không, hành vi khác nhau giữa ngôn ngữ.
- **`index` reset sau khi cắt**: không được; `next_index` nằm trong `Field`.

## 6. Gỡ lỗi

- In 5 số rút cho platform đầu; so với bảng ở SPEC.
- Kiểm tra `x` trước/sau clamp cho các seed có giá trị cực trị.
- Thêm test đếm số platform sau 100 lần advance; phải ≤ 60.
- Thêm test “cùng camera, gọi advance 2 lần” — lần hai không sinh gì.
- Kiểm tra `kind` của platform nền luôn `"ground"` và `index=-1`.
- Nếu output lệch ở chữ số cuối, kiểm tra thứ tự phép nhân chia và việc dùng `float` 64-bit.

## 7. Kiểm chứng độc lập

```bash
cd 23_BOUNDED_PLATFORM_GENERATION
python -m platform_gen --seed 9 --config fixtures/config.json --camera 0 --out out.json
python - <<'PY'
import json, math
d = json.load(open('out.json', encoding='utf-8'))
top = d['platforms'][-1]
assert top['y'] == -1260, top
assert all(20 <= p['x'] <= 230 for p in d['platforms'])
assert all(p['box'] is None for p in d['platforms'] if p['y'] >= 340)
print(d['initial'])
PY
```

Test:

```bash
python -m unittest discover -s tests -v
```

Nếu dùng JSON khác, đảm bảo khóa `config_digest` được tính trên cùng chuỗi canonical:

```python
json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

## 8. Gợi ý

- Viết test nhỏ cho `SplitMix64` trước: seed 0, 1, 2^64-1; so 3 giá trị đầu với một bảng bạn tự tính.
- Tách hàm `classify_box(y, u_box)` để test biên độc lập.
- Tách `window_append(field, p)` để test cắt cửa sổ mà không cần sinh.
- Đừng dùng `random.Random`; nó không đảm bảo cùng dãy giữa các phiên bản Python/ngôn ngữ.

## 9. Mở rộng

1. Thêm platform “nổ” làm hộp may biến mất sau một lần chạm.
2. Thêm seed từ chuỗi (hash 64-bit) để chia sẻ màn chơi bằng mã ngắn.
3. Thêm bản ghi/ replay camera để tái hiện màn.
4. Đo thời gian sinh 10.000 platform; tối ưu nếu cần.
5. Viết kiểm tra tính chất (property-based) cho clamp và cửa sổ.
