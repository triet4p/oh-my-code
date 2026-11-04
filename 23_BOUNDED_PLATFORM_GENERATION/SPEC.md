# SPEC 23 — Bộ sinh platform tất định

## 1. Cấu hình

`config` là object JSON; mọi trường bắt buộc, không nhận giá trị âm:

```json
{
  "width": 360,
  "height": 640,
  "platform_width": 110,
  "platform_height": 18,
  "initial_count": 15,
  "window": 60,
  "spawn_interval": 120,
  "spawn_ahead": 800,
  "max_x_diff": 90,
  "move_chance": 0.25,
  "min_speed": 0.5,
  "max_speed": 1.5,
  "lucky_chance": 0.08,
  "unlucky_chance": 0.05
}
```

Ràng buộc: `platform_width + 130 <= width`; `0 <= move_chance <= 1`; `0 <= lucky_chance`, `0 <= unlucky_chance`, tổng ≤ 1; `min_speed <= max_speed`; `window >= initial_count + 1`.

## 2. PRNG bắt buộc — splitmix64

Trạng thái 64-bit không dấu, khởi tạo bằng `seed`.

```
state = (state + 0x9E3779B97F4A7C15) mod 2^64
z = state
z = ((z xor (z >> 30)) * 0xBF58476D1CE4E5B9) mod 2^64
z = ((z xor (z >> 27)) * 0x94D049BB133111EB) mod 2^64
z = z xor (z >> 31)
u = floor(z / 2^11) / 2^53          # 0 <= u < 1
```

Mỗi platform rút **đúng 5 số** theo thứ tự: `u_x`, `u_move`, `u_speed`, `u_sign`, `u_box`. Các số không dùng vẫn phải được rút để chuỗi ổn định.

## 3. Sinh một platform

Cho `y` và `last_x`:

1. `x_raw = last_x + (u_x - 0.5) * max_x_diff * 2`.
2. `x = min(max(x_raw, 20), width - 130)`.
3. `moving = u_move < move_chance`.
4. `speed = min_speed + u_speed * (max_speed - min_speed)`.
5. `dx = speed` nếu `u_sign >= 0.5`, ngược lại `-speed`; nếu `not moving` thì `dx = 0`.
6. Nếu `y < height - 300`:
   - `u_box < lucky_chance` → `box = "lucky"`;
   - ngược lại `u_box < lucky_chance + unlucky_chance` → `box = "unlucky"`;
   - còn lại `null`.
   Nếu `y >= height - 300` → `box = null`.
7. Trả object:

```json
{
  "index": 0,
  "x": 157.83,
  "y": 420,
  "w": 110,
  "h": 18,
  "dx": 0,
  "box": null,
  "kind": "generated"
}
```

`index` là số thứ tự sinh kể từ 0, không đổi khi cửa sổ cắt bớt.

## 4. Dàn ban đầu

1. Platform nền: `{index: -1, x: 0, y: height-50, w: width, h: 50, dx: 0, box: null, kind: "ground"}`.
2. `last_x = width/2 - platform_width/2`.
3. Với `i = 0..initial_count-1`:
   - `y = height - 220 - i * spawn_interval`;
   - sinh platform với `y`, `last_x`;
   - thêm vào cuối; `last_x = x` của platform vừa sinh.
4. Không áp dụng cửa sổ ở bước này (16 phần tử < 60).

## 5. `advance(field, camera_y)`

```
loop:
  top = field[-1]
  if top.y <= camera_y - spawn_ahead: break
  y = top.y - spawn_interval
  p = generate(y, top.x, next_index++)
  append(p)
  if len(field) > window: remove field[0]
  guard: tối đa window lần lặp mỗi lần gọi
```

- `top.x` dùng làm `last_x`, không phải platform cuối **còn nhìn thấy** sau khi cắt.
- Nếu `field` rỗng (không hợp lệ) → lỗi `EMPTY_FIELD`.
- Nếu chạm guard mà vẫn chưa đạt ngưỡng → trả `warning="SPAWN_GUARD"`, không lặp vô hạn.
- `camera_y` là số thực; phép so sánh dùng `<=` để biên xác định.

## 6. Output CLI

```bash
python -m platform_gen --seed 9 --config fixtures/config.json --camera 0,-200,-400 --out field.json
```

```json
{
  "schema_version": 1,
  "seed": 9,
  "config_digest": "sha256:…",
  "initial": { "count": 16, "top_y": -1260 },
  "steps": [
    { "camera_y": 0, "spawned": 0, "total": 16, "dropped": 0 },
    { "camera_y": -200, "spawned": 0, "total": 16, "dropped": 0 }
  ],
  "platforms": [ … ],
  "next_index": 15
}
```

`config_digest` là SHA-256 của JSON canonical (khóa sắp xếp, không khoảng trắng thừa).

## 7. Ví dụ cụ thể — seed 9

Config mặc định. 5 platform đầu tiên (sau nền):

| index | y | x | dx | box |
|---|---:|---:|---:|---|
| 0 | 420 | 157.83 | 0 | null |
| 1 | 300 | 88.45 | 0 | null |
| 2 | 180 | 104.61 | -1.49 | null |
| 3 | 60 | 174.05 | 0 | null |
| 4 | -60 | 222.04 | -0.97 | null |

Các giá trị được làm tròn 2 chữ số thập phân để đọc; test so sánh với dung sai `1e-9` trên giá trị chưa làm tròn.

Các mốc đáng chú ý:

- index 6, `y=-300`, `x=195.31`, `dx=0.56`, `box="unlucky"`.
- index 9, `y=-660`, `x=230` (đã clamp trần), `dx=-0.61`, `box="lucky"`.
- index 5, 9, 11 có `x=230` do clamp, chứng minh biên trên hoạt động.

Với `camera_y=0`, `top.y=-1260 <= -800` nên `advance` không sinh thêm. Với `camera_y=-600`, ngưỡng là `-1400`; top `-1260 > -1400` nên sinh tại `y=-1380`, rồi top `-1380 > -1400` sinh tiếp `-1500`; dừng khi top `<= -1400`.

## 8. Bất biến và trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Cùng seed chạy 2 lần | mảng giống hệt |
| 2 | `seed=0` | hợp lệ; trạng thái bắt đầu 0 |
| 3 | `seed=2^64-1` | vẫn tính đúng modulo |
| 4 | `u_x` cực trị | `x` bị clamp, không tràn |
| 5 | `move_chance=0` | mọi `dx=0` |
| 6 | `move_chance=1` | mọi `dx != 0` |
| 7 | `lucky_chance=0` | không có hộp may |
| 8 | `lucky+unlucky=1` | mọi platform dưới ngưỡng có đúng một hộp |
| 9 | `y = height-300` | **không** xét hộp (điều kiện `<`) |
| 10 | `y = height-301` | có xét hộp |
| 11 | 45 platform sinh thêm | cửa sổ 60, nền bị loại đầu tiên |
| 12 | `advance` với camera rất thấp | sinh tối đa `window` lần rồi cảnh báo |
| 13 | `window < initial_count` | lỗi cấu hình |
| 14 | `platform_width+130 > width` | lỗi cấu hình |

## 9. Tiêu chí chấp nhận

- [ ] 16 platform ban đầu của seed 9 khớp bảng fixture (sai khác < `1e-9`).
- [ ] Mỗi platform có đúng 5 lần rút; đổi một hằng số PRNG làm thay đổi toàn bộ dãy.
- [ ] Không platform nào vi phạm clamp hoặc miền `dx`.
- [ ] Sau 100 lần sinh, độ dài không bao giờ vượt 60.
- [ ] Phần tử bị loại luôn là phần tử đầu; platform mới luôn ở cuối.
- [ ] `advance` không lặp vô hạn với camera phi thực tế.
- [ ] Output có `config_digest` ổn định giữa các lần chạy.
- [ ] Test không dùng `random`, `time`, hay phụ thuộc thứ tự dict.

## 10. Non-goals

- Không cần render, sprite, camera thật, hay vòng lặp game.
- Không cần vật lý người chơi, va chạm, dung nham.
- Không cần lưu/khôi phục game.
- Không cần hỗ trợ nhiều loại platform ngoài nền và platform sinh.
