# GUIDE 24 — Thiết kế vòng lặp vật lý

## 1. Cấu trúc

```
physics/
├─ config.py      # dataclass, validate, digest
├─ state.py       # PlayerState, Platform, StepResult
├─ step.py        # step(state, platforms, input, cfg)
├─ scenario.py    # đọc/validate JSON
├─ cli.py
└─ trace.py
fixtures/scenarios/
```

`step` là hàm thuần: không đọc file, không in, không biết frame. Hàm này là nơi duy nhất chứa vật lý.

## 2. Dữ liệu

```python
@dataclass
class Player:
    x: float; y: float; vx: float; vy: float
    grounded: bool = False
    is_rocketing: bool = False
    rocket_distance: float = 0.0
    lava_level: float = 840.0
    score: int = 0
    status: str = "playing"
```

`Platform` nên có `lucky_collected`/`unlucky_collected` **bên ngoài** dữ liệu fixture, hoặc clone fixture trước khi chạy; nếu không, chạy lại cùng object sẽ khác.

## 3. Các bước then chốt

### 3.1. Tích phân

Source dùng `dt * 60`; với `dt=1/60`, hệ số bằng 1. Bài cố định hệ số này. Nếu muốn hỗ trợ `dt` khác, phải đổi đồng thời gravity, jump, friction và tolerance; đừng trộn.

### 3.2. Va chạm

Điều kiện dưới là **dung sai quét một frame**:

```
y + h <= p.y + p.h + vy
```

Nếu bỏ `+ vy`, người chơi rơi nhanh sẽ xuyên qua platform mỏng. Nếu dùng `vy` sau khi đã cộng gravity, tolerance lớn hơn một chút; đó là chủ ý.

Luôn kiểm tra `vy > 0`: nếu không, đầu người chơi chạm mặt dưới platform sẽ bị “đáp” lên trên.

### 3.3. Platform di chuyển

Sau khi đặt `y = p.y - h`, cộng `p.dx` vào `x`. Nếu platform đi sang phải, người chơi đi cùng. Nhớ clamp lại `x` sau khi cộng; nếu không, người chơi có thể lọt ra ngoài màn hình.

### 3.4. Hộp

Hộp nằm **phía trên** platform, không phải tâm platform. Với platform cao 50, hộp ở `y-24`; người chơi đứng trên platform sẽ chồng hộp ngay. Đây là lý do kịch bản hộp may kích hoạt frame 0.

Thứ tự hộp sau va chạm quan trọng: nếu kiểm tra hộp trước khi đáp, người chơi có thể bỏ lỡ hộp khi rơi xuyên qua vùng hộp trong cùng frame.

### 3.5. Rocket

Đặt `grounded=false` ngay khi kích hoạt. Trong mỗi frame rocket:

- `vy = -rocket_speed` (ghi đè, không cộng gravity);
- `y += vy`;
- giảm `rocket_distance` theo `abs(vy)`.

Khi distance ≤ 0, đặt `vy = rocket_end_vy`; frame sau mới cộng gravity. Điều này tạo cảm giác “hết nhiên liệu” thay vì rơi đột ngột.

### 3.6. Dung nham

Giảm **sau** khi xử lý hộp để hộp may đẩy lùi có hiệu lực ngay frame đó. Kiểm tra chạm sau khi giảm. Dùng `>` chứ không `>=` để biên rõ ràng.

## 4. Bẫy thường gặp

- **Cập nhật `vy` rồi mới kiểm tra `vy > 0`**: đúng, vì cần vận tốc mới.
- **Đặt `grounded=false` trước va chạm**: đúng, nhưng phải đặt lại `true` khi đáp. Nếu quên, nhảy không bao giờ hoạt động.
- **Kiểm tra va chạm sau khi đã xử lý input nhảy**: có thể đáp rồi nhảy ngay trong cùng frame; bài cố ý cho phép (nhảy cuối frame).
- **Dùng `while` cho va chạm**: không cần; mỗi frame tối đa một lần đáp.
- **Cộng `dx` trước khi clamp**: có thể ra ngoài; clamp sau.
- **Quên reset `rocket_distance`**: lần rocket sau dùng giá trị cũ.
- **Game over vẫn chạy vật lý**: phải đóng băng hoàn toàn, kể cả lava và score.
- **Cộng dồn điểm âm**: score chỉ tăng; `max(score, current)`.
- **So sánh float tuyệt đối**: fixture nên có dung sai; trace SHA yêu cầu cùng phép tính, không làm tròn tùy tiện.

## 5. Gỡ lỗi

- Vẽ trace ra CSV, mở bằng bảng tính; kiểm tra `y` đơn điệu khi rơi.
- Thêm assert tạm: `if state.vy > cfg.max_fall_speed: raise`.
- Kiểm tra frame đáp: `y+h == p.y` đúng đến 1e-9.
- Thử platform `y=400,h=18` và rơi từ `y=-10000`; xác nhận vẫn đáp nhờ clamp.
- Thử rocket rồi nhảy ngay frame kết thúc; phải bị bỏ qua vì `grounded=false`.
- Kiểm tra lava tại frame 519/520 của kịch bản nền.

## 6. Kiểm chứng độc lập

```bash
cd 24_PLATFORM_PHYSICS
python -m physics --scenario fixtures/scenarios/jump-after-landing.json \
  --trace /tmp/trace.jsonl --out /tmp/final.json
python - <<'PY'
import json
f=json.load(open('/tmp/final.json'))
assert f['final']['y']==540 and f['final']['grounded'] is True
assert f['final']['score']==5
print(f['final'])
PY
```

Chạy lại và so SHA:

```bash
python -m physics --scenario fixtures/scenarios/lava.json --out /tmp/a.json
python -m physics --scenario fixtures/scenarios/lava.json --out /tmp/b.json
cmp /tmp/a.json /tmp/b.json
```

Test:

```bash
python -m unittest discover -s tests -v
```

## 7. Gợi ý

- Viết `step` trước, CLI sau.
- Tách `apply_horizontal`, `apply_vertical`, `resolve_landing`, `resolve_boxes`, `apply_lava` thành hàm nhỏ; test từng hàm.
- Dùng `math.isclose(abs_tol=1e-9)` cho assert.
- Khi trace lệch, in cả `vy` trước/sau gravity và `y` trước/sau dời.
- Đừng tối ưu trước; 100.000 frame vẫn nhanh.

## 8. Mở rộng

1. Thêm double jump có đếm.
2. Thêm platform băng (friction khác) hoặc platform rơi.
3. Thêm coyote time và buffer nhảy.
4. Thêm replay nén từ trace.
5. So sánh bước cố định với bước biến thiên; viết test cho tunneling.
