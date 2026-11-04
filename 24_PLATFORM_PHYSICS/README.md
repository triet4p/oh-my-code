# 24 — Mô phỏng vật lý platform 60 Hz

## Mục tiêu

Cài đặt lại vòng lặp vật lý của một game platform leo dọc: tích phân vận tốc, ma sát, trọng lực, jump có điều kiện, va chạm platform có dung sai, platform di chuyển mang người chơi, hộp may/rủi, rocket và dung nham dâng. Mọi thứ chạy theo bước cố định 1/60 giây, không render, không phụ thuộc thời gian thực.

## Giá trị

- Vật lý game là bài toán **thứ tự cập nhật**; đổi thứ tự cho ra hành vi khác dù công thức giống.
- Học cách làm mô phỏng tất định để test: cùng input + cùng trạng thái đầu → cùng trace.
- Học các lỗi kinh điển: xuyên platform, kẹt platform di chuyển, nhảy khi đang bay, trạng thái `grounded` sai.
- Học cách tách mô hình thuần khỏi engine/render.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (chỉ thư viện chuẩn) |
| Độ khó | Trung bình–khó |
| Điều kiện | Số thực, va chạm AABB, khái niệm bước thời gian cố định |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/magma_obby`
- File nguồn:
  - <https://github.com/triet4p/magma_obby/blob/main/lib/game/components/player.dart>
  - <https://github.com/triet4p/magma_obby/blob/main/lib/game/magma_game.dart>
- Hành vi quan sát được:
  - `if (leftPressed) vx -= 0.25; else if (rightPressed) vx += 0.25; else vx *= Physics.friction;`
  - `vx = vx.clamp(-Physics.moveSpeed, Physics.moveSpeed); vy += Physics.gravity;`
  - `x += vx * (dt * 60); y += vy * (dt * 60);`
  - Va chạm rơi: `if (vy > 0 && x + width > platData.x && x < platData.x + platData.w && y + height >= platData.y && y + height <= platData.y + platData.h + (vy * dt * 60))` rồi `y = platData.y - height; vy = 0; isGrounded = true; if (platData.dx != 0) x += platData.dx;`
  - Hộp may/rủi dùng AABB 24×24 đặt tại `(plat.x + w/2 - 12, plat.y - 24)`; may kích hoạt `isRocketing` và `gameRef.pushLavaBack()`; rủi gọi `gameOver()`.
  - Rocket: `vy = -PlatformConfig.rocketSpeed; vx = 0; double moveStep = vy * (dt * 60); y += moveStep; rocketDistance -= moveStep.abs();` hết thì `vy = -5`.
  - Dung nham: `lavaLevel -= Physics.lavaSpeed * (dt * 60);` và `if (p.y + p.height > lavaLevel + 10 && !p.isRocketing) gameOver();`
  - Điểm: `((GameConstants.gameHeight - 120 - p.y) / 20).floor()`, chỉ tăng.

**Phần là thiết kế của bài:** hằng số cụ thể, clamp tốc độ rơi, đặt `grounded = false` ngay khi rocket bắt đầu, thứ tự cập nhật được đặc tả, input theo frame, output trace. Nguồn không reset `isGrounded` trong nhánh rocket; bài sửa để tránh nhảy giữa không trung sau khi rocket kết thúc.

## Hành vi bài tập yêu cầu

- Bước thời gian cố định `dt = 1/60`, hệ số `frame = dt*60 = 1`.
- Input theo từng frame: `left`, `right`, `jump`; nhảy chỉ khi `grounded` và không rocket.
- Clamp `vy` ở `max_fall_speed` để không xuyên platform mỏng.
- Va chạm chỉ khi đang rơi (`vy > 0`), có dung sai theo quãng đường frame hiện tại.
- Platform di chuyển mang người chơi sau khi đáp.
- Hộp may kích hoạt rocket và đẩy dung nham lùi; hộp rủi kết thúc game ngay.
- Dung nham dâng mỗi frame; chạm khi đáy người chơi vượt mực + 10 và không rocket.
- `game_over` đóng băng trạng thái; các frame sau giữ nguyên.

## Phạm vi

Trong phạm vi: mô hình vật lý, va chạm, hộp, rocket, dung nham, điểm, trace JSON, CLI.

Ngoài phạm vi: render, camera, joystick, âm thanh, sinh platform (bài 23), lưu game, mạng.

## Fixture offline

`fixtures/scenarios/*.json` chứa 8 kịch bản nhỏ (nền phẳng, nhảy, platform di chuyển, hộp may, hộp rủi, dung nham, rơi nhanh, va chạm biên). Không asset, không random, không thời gian thực. `fixtures/expected/` chứa trạng thái cuối và một số frame mốc.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, thứ tự cập nhật, trace và ví dụ số.
- [GUIDE.md](GUIDE.md) — thiết kế, bẫy và kiểm chứng.
