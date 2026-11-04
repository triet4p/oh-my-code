# SPEC 24 — Vật lý platform tất định

## 1. Cấu hình và trạng thái

```json
{
  "width": 360,
  "height": 640,
  "player_width": 30,
  "player_height": 50,
  "gravity": 0.6,
  "jump_force": -13.0,
  "move_speed": 7.0,
  "friction": 0.85,
  "max_fall_speed": 18.0,
  "rocket_speed": 14.0,
  "rocket_distance": 200.0,
  "rocket_end_vy": -5.0,
  "lava_speed": 0.5,
  "lava_margin": 10.0,
  "lava_pushback": 80.0,
  "score_base": 520,
  "score_divisor": 20
}
```

Ràng buộc: `0 < friction < 1`; `gravity > 0`; `jump_force < 0`; `max_fall_speed > 0`; `move_speed > 0`; `score_divisor > 0`.

Trạng thái:

```json
{
  "x": 165, "y": 490, "vx": 0, "vy": 0,
  "grounded": false, "is_rocketing": false, "rocket_distance": 0,
  "lava_level": 840, "score": 0, "status": "playing"
}
```

## 2. Thứ tự cập nhật một frame (bắt buộc)

Cho input `{left, right, jump}` của frame hiện tại. `left` và `right` đồng thời `true` → lỗi `INVALID_INPUT` trước khi mô phỏng.

1. Nếu `status != "playing"`: ghi trace trạng thái đóng băng và sang frame sau.
2. Nếu `is_rocketing`:
   1. `grounded = false`; `vx = 0`; `vy = -rocket_speed`.
   2. `y += vy`; `rocket_distance -= abs(vy)`.
   3. Nếu `rocket_distance <= 0`: `is_rocketing = false`; `rocket_distance = 0`; `vy = rocket_end_vy`.
3. Ngược lại:
   1. `grounded = false`.
   2. Nếu `left`: `vx -= 0.25`; ngược lại nếu `right`: `vx += 0.25`; ngược lại `vx *= friction`.
   3. `vx = clamp(vx, -move_speed, move_speed)`.
   4. `vy = min(vy + gravity, max_fall_speed)`.
   5. `x += vx`; `y += vy`.
   6. `x = clamp(x, 0, width - player_width)`.
   7. Nếu `vy > 0`, duyệt platform **theo thứ tự mảng**, platform đầu tiên thỏa:
      - `x + player_width > p.x`
      - `x < p.x + p.w`
      - `y + player_height >= p.y`
      - `y + player_height <= p.y + p.h + vy`
      thì đặt `y = p.y - player_height`, `vy = 0`, `grounded = true`, và nếu `p.dx != 0` thì `x += p.dx` rồi clamp lại.
4. Nếu không rocket và `status == "playing"`, kiểm tra hộp của **tất cả** platform:
   - hộp vuông 24, `bx = p.x + p.w/2 - 12`, `by = p.y - 24`;
   - chồng khi `x < bx+24 && x+player_width > bx && y < by+24 && y+player_height > by`.
   - `lucky` chưa thu: đánh dấu đã thu, `is_rocketing = true`, `rocket_distance = rocket_distance_cfg`, `grounded = false`, `lava_level += lava_pushback`.
   - `unlucky` chưa thu: đánh dấu đã thu, `status = "game_over"`, lý do `"unlucky"`.
5. `lava_level -= lava_speed`.
6. Nếu `y + player_height > lava_level + lava_margin` và không rocket: `status = "game_over"`, lý do `"lava"`.
7. `current = floor((score_base - y) / score_divisor)`; nếu `current > score` thì `score = current`.

Không thêm trọng lực trong frame rocket. Không kiểm tra va chạm platform trong frame rocket.

## 3. Nhảy

- Input `jump` được xử lý **cuối frame**, sau va chạm và hộp.
- Điều kiện: `jump == true`, `grounded == true`, `is_rocketing == false`, `status == "playing"`.
- Tác dụng: `vy = jump_force`, `grounded = false`. `y` không đổi trong frame đó.
- Bấm nhảy khi đang rơi hoặc đang rocket bị bỏ qua, không tiêu hao gì.

## 4. Input và scenario

```json
{
  "name": "jump-after-landing",
  "frames": 90,
  "start": { "x": 165, "y": 490, "vx": 0, "vy": 0, "lava_level": 840 },
  "platforms": [
    { "x": 0, "y": 590, "w": 360, "h": 50, "dx": 0, "lucky": false, "unlucky": false }
  ],
  "inputs": [ { "frame": 18, "jump": true } ]
}
```

- `frames` 1…100000.
- `frame` 0-based, phải `< frames`, không trùng sau khi gộp.
- Trường thiếu trong input = `false`.
- Platform `w,h > 0`; `dx` hữu hạn; `lucky` và `unlucky` không đồng thời `true` trên cùng platform → lỗi `INVALID_PLATFORM`.

## 5. Output

`--out` ghi:

```json
{
  "schema_version": 1,
  "scenario": "jump-after-landing",
  "config_digest": "sha256:…",
  "final": { "frame": 89, "x": 165, "y": 540, "vx": 0, "vy": 0,
             "grounded": true, "is_rocketing": false, "lava_level": 795.0,
             "score": 5, "status": "playing" },
  "events": [ { "frame": 18, "type": "jump" } ],
  "trace_sha256": "…"
}
```

`--trace trace.jsonl` (tùy chọn) ghi mỗi frame một dòng:

```json
{"frame":0,"x":165.0,"y":490.6,"vx":0.0,"vy":0.6,"grounded":false,"is_rocketing":false,"rocket_distance":0.0,"lava_level":839.5,"score":1,"status":"playing"}
```

`trace_sha256` là SHA-256 của toàn bộ file trace theo đúng thứ tự byte; nếu không ghi trace, tính trên chuỗi JSONL dựng trong bộ nhớ.

## 6. Ví dụ cụ thể

### 6.1. Rơi và đáp (20 frame, không input)

- Frame 0: `y=490.6`, `vy=0.6`, `grounded=false`, `lava=839.5`, `score=1`.
- Frame 12: lần đầu `y=540`, `vy=0`, `grounded=true`, `lava=833.5`.
- Frame 19: `y=540`, `lava=830.0`, `score=1`.

### 6.2. Nhảy sau khi đáp (90 frame, jump frame 18)

- Frame 18: `y=540`, `vy=-13.0` (nhảy được áp dụng cuối frame), `grounded=false`, `lava=830.5`.
- Frame 40: `y=405.8`, `vy=0.2`, `score=5`.
- Frame 59: `y=523.6`, `vy=11.6`.
- Frame 89: `y=540`, `vy=0`, `grounded=true`, `lava=795.0`, `score=5`.

### 6.3. Platform di chuyển (30 frame, `dx=1.5`, giữ phải từ frame 5)

- Frame 0: đáp tại `y=350`, `x` từ 120 thành 121.5 do platform mang.
- Frame 29: `x=166.638004`, `y=350`, `vx=0.005058`, `grounded=true`.
- Không có sự kiện game over.

### 6.4. Hộp may (40 frame)

Platform nền `y=590`, hộp may tại `y=566`; người chơi bắt đầu `y=540` chồng hộp ngay frame 0.

- Frame 0: `is_rocketing=true`, `grounded=false`, `lava=919.5` (840 + 80 − 0.5).
- Frame 1: `y=526`, `vy=-14`, còn rocket.
- Frame 14: `y=344`, `rocket_distance=4`.
- Frame 15: `y=330`, rocket kết thúc, `vy=-5`, `score=9`.
- Frame 39: `y=390`, `vy=9.4`, `lava=900.0`, `score=10`.

### 6.5. Hộp rủi (3 frame)

- Frame 0: chồng hộp rủi → `status="game_over"`; trace vẫn ghi `y=540`, `score=0`.
- Frame 1-2: trạng thái đóng băng, không giảm dung nham.

### 6.6. Dung nham (650 frame, không input)

- Frame 519: `lava=580.0`, `status="playing"`.
- Frame 520: `lava=579.5`, đáy `590 > 589.5` → `status="game_over"`, lý do `"lava"`.

## 7. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | `left` và `right` cùng frame | `INVALID_INPUT`, exit 2 |
| 2 | Nhảy khi đang rơi | bỏ qua, không sự kiện |
| 3 | Nhảy khi rocket | bỏ qua |
| 4 | Nhảy đúng frame đáp | được phép; `vy=-13` cuối frame |
| 5 | `vy` vượt `max_fall_speed` | bị clamp trước khi dời vị trí |
| 6 | Rơi từ `y=-10000` | không xuyên platform nhờ clamp; đáp đúng |
| 7 | Platform `dx` đẩy ra biên | `x` clamp sau khi mang |
| 8 | Hai platform chồng nhau | platform đầu trong mảng thắng |
| 9 | Hộp may và rủi cùng platform | lỗi cấu hình |
| 10 | Hộp đã thu | không kích hoạt lần hai |
| 11 | Rocket hết distance | frame kế tiếp mới áp dụng trọng lực |
| 12 | Lava chạm đúng biên `>` | `590 > 590` sai → chưa chết; phải `>` thực sự |
| 13 | `frames=0` | lỗi tham số |
| 14 | Input frame âm hoặc ≥ frames | `INVALID_INPUT_FRAME` |
| 15 | Game over rồi có input nhảy | bỏ qua hoàn toàn |

## 8. Tiêu chí chấp nhận

- [ ] Sáu ví dụ ở mục 6 khớp đến 1e-6 với fixture.
- [ ] `grounded` luôn `false` trong mọi frame rocket.
- [ ] Không có frame nào `y` tăng quá `max_fall_speed` khi đang rơi.
- [ ] Platform di chuyển mang người chơi đúng `dx` mỗi frame khi đứng.
- [ ] Hộp may đẩy lava thêm đúng 80 trước khi trừ 0.5 của frame.
- [ ] Game over đóng băng hoàn toàn, kể cả lava.
- [ ] Trace cùng scenario chạy hai lần giống hệt byte.
- [ ] Không dùng `time`, `random`, hay `dt` biến thiên.

## 9. Non-goals

- Không render, không camera, không joystick.
- Không sinh platform động trong lúc mô phỏng; dàn platform là đầu vào.
- Không hỗ trợ nhiều người chơi, lưu game, replay ngoài trace.
- Không mô phỏng ma sát không khí phức tạp hay va chạm nghiêng.
