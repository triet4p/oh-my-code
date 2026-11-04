# 23 — Sinh dàn platform có giới hạn bộ nhớ

## Mục tiêu

Tự viết bộ sinh dàn platform cho game leo dọc, dùng bộ sinh số giả ngẫu nhiên **tự cài đặt, có seed**, tuân thủ clamp biên, xác suất platform di chuyển/hộp may rủi, sinh trước theo camera và giữ cửa sổ tối đa 60 platform.

## Giá trị

- Tách **sinh dữ liệu** khỏi engine game và renderer; cùng seed cho cùng dàn, kiểm thử được.
- Luyện kỹ thuật cửa sổ trượt (sliding window) để bộ nhớ không tăng vô hạn.
- Luyện cách biến “ngẫu nhiên” thành hợp đồng xác định: thứ tự rút số, phép biến đổi, biên.
- Hiểu vì sao dùng `Random()` của ngôn ngữ không đủ để tái lập giữa các phiên bản/máy.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (chỉ thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Số học 64-bit, kiến thức cơ bản về PRNG và test tất định |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/magma_obby`
- File nguồn: <https://github.com/triet4p/magma_obby/blob/main/lib/game/magma_game.dart>
- Hành vi quan sát được:
  - `_spawnInitialPlatforms()` thêm platform nền `(x: 0, y: gameHeight - 50, w: gameWidth, h: 50)`, đặt `nextY = gameHeight - 220`, `lastX = gameWidth / 2 - 55`, rồi lặp 15 lần và `nextY -= PlatformConfig.spawnInterval`.
  - `_createPlatformData(y, lastX)`:
    - `x = lastX + (Random().nextDouble() - 0.5) * PlatformConfig.maxXDiff * 2`;
    - `x = max(20, min(GameConstants.gameWidth - 130, x))`;
    - `isMoving = Random().nextDouble() < PlatformConfig.moveChance`;
    - nếu di chuyển: `dx = minSpeed + rand * (maxSpeed - minSpeed)` và đảo dấu theo `nextBool()`;
    - hộp may/rủi chỉ xét khi `y < gameHeight - 300`, xác suất `luckyBoxChance` rồi `unluckyBoxChance`.
  - `_addPlatform`: thêm vào `platforms`; `if (platforms.length > 60) { final old = platforms.removeAt(0); old.removeFromParent(); }`.
  - Trong `update`: nếu `topPlat.y > camera.viewfinder.position.y - 800` thì sinh platform mới tại `topPlat.y - spawnInterval`, dùng `topPlat.data.x` làm `lastX`.

**Phần là thiết kế của bài:** bộ PRNG splitmix64, thứ tự rút số cố định, output JSON, API `initial_field`/`advance`, ngưỡng spawn tham số hóa, và các bất biến kiểm thử. Nguồn dùng `dart:math Random()` không seed nên không tái lập; bài thay bằng PRNG tự viết.

## Hành vi bài tập yêu cầu

- `initial_field(seed, config)` trả nền + 15 platform, đúng thứ tự.
- `advance(field, camera_y, config)` sinh thêm cho đến khi platform trên cùng đủ gần ngưỡng `camera_y - spawn_ahead`, hoặc chạm trần 60.
- Mỗi platform giữ `x` trong `[20, width-130]`; `dx` trong `[-max_speed,-min_speed] ∪ {0} ∪ [min_speed,max_speed]`.
- Hộp may/rủi chỉ xuất hiện khi `y < height-300`.
- Danh sách luôn giữ **platform mới nhất**; khi vượt 60, loại platform cũ nhất ở đầu.
- Cùng seed + cùng chuỗi `camera_y` → cùng dàn và cùng số lần sinh.

## Phạm vi

Trong phạm vi: PRNG, sinh platform, cửa sổ 60, spawn-ahead, mô hình dữ liệu, CLI in JSON.

Ngoài phạm vi: render, va chạm, vật lý người chơi (bài 24), dung nham, joystick, âm thanh, lưu game.

## Fixture offline

- `fixtures/seeds.json`: các seed 1, 9, 12345 và config.
- `fixtures/expected/seed-9-initial.json`: 16 platform vàng.
- `fixtures/cameras/seed-9.json`: chuỗi `camera_y` để test spawn.
- Không có asset hình ảnh, không gọi mạng; số liệu tổng hợp, không chứa dữ liệu người dùng.

## Liên kết

- [SPEC.md](SPEC.md) — công thức PRNG, hằng số, output, ví dụ seed 9.
- [GUIDE.md](GUIDE.md) — thiết kế cửa sổ, bẫy và kiểm chứng.
