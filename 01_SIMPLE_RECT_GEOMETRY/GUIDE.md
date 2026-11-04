# GUIDE — SimpleRect

Hướng dẫn này mô tả cách tự xây dựng bài 01. Nó không cung cấp lời giải hoàn chỉnh; các đoạn gợi ý chỉ ra quyết định thiết kế và chỗ cần tự viết.

## Bước 0 — Dựng môi trường

```bash
mkdir 01_SIMPLE_RECT_GEOMETRY/work
cd 01_SIMPLE_RECT_GEOMETRY/work
uv init . -p 3.12 --lib
uv add --dev pytest
```

Tạo `src/simple_rect/__init__.py` và `tests/`. Kiểm tra nhanh:

```bash
uv run python -c "import simple_rect, sys; print(simple_rect.__file__, sys.version)"
```

## Bước 1 — Chọn biểu diễn

Dùng `@dataclass(frozen=True, slots=True)` với bốn trường `float`. Bất biến quan trọng hơn kế thừa: hình chữ nhật là giá trị, không phải thực thể có danh tính.

Trước khi viết logic, tự trả lời:

- Tọa độ lưu theo góc trên-trái và dưới-phải, hay trái/dưới và phải/trên? Nguồn dùng `x1,y1` là góc trên-trái trong hệ tọa độ màn hình (y tăng xuống). Bài tập không phụ thuộc hướng y, nhưng phải nhất quán.
- Có chuẩn hóa `int` sang `float` không? Nên có, để `Rect(0,0,10,10) == Rect(0.0,0.0,10.0,10.0)`.
- Có cho phép `-0.0` không? Có; nó bằng `0.0` trong so sánh.

## Bước 2 — Kiểm tra khởi tạo

Viết một helper `_finite_number(value) -> float`:

- Từ chối `bool` trước khi kiểm tra `int`/`float`, vì `True` là `1`.
- Chấp nhận `int` và `float`, chuyển sang `float`.
- Từ chối mọi thứ khác bằng `ValueError`.
- Dùng `math.isfinite`.

Sau đó kiểm tra thứ tự cạnh. Gợi ý: đặt tất cả thông điệp lỗi thành hằng số, để test so khớp chính xác mà không lặp chuỗi.

Một cái bẫy: nếu bạn kiểm tra `x2 <= x1` trước khi kiểm tra kiểu, `Rect("a", 0, 1, 1)` sẽ ném `TypeError` thay vì `ValueError`; hợp đồng yêu cầu `ValueError` cho mọi đầu vào không hợp lệ. Hãy chuẩn hóa và kiểm tra kiểu trước.

## Bước 3 — Giao và diện tích

Cài đặt giao bằng bốn phép `max`/`min`. Đừng dùng `abs` hay sắp xếp lại các cạnh; cách đó che mất lỗi nhập liệu và làm mất quy ước nửa mở.

Tự kiểm tra các bất biến sau bằng tay trước khi viết test:

- Giao có tính đối xứng: `A.intersection_area(B) == B.intersection_area(A)`.
- Giao không vượt quá diện tích nhỏ hơn: `<= min(A.area, B.area)`.
- Giao bằng 0 khi và chỉ khi một trong bốn điều kiện rời nhau đúng: `A.x2 <= B.x1`, `B.x2 <= A.x1`, `A.y2 <= B.y1`, `B.y2 <= A.y1`.

Nếu một trong các bất biến sai, vẽ hai hộp ra giấy với tọa độ cụ thể trước khi sửa code.

## Bước 4 — Tách “phủ” khỏi “chứa”

Đây là phần quan trọng nhất về thiết kế.

- `coverage_of(other)` trả `intersection_area(other) / other.area`. Đây là câu hỏi “bao nhiêu phần trăm của `other` nằm trong `self`”.
- `contains(other)` là câu hỏi hình học thuần túy, không dùng diện tích.
- `contains_by_area(other, threshold)` chỉ là tiện ích: `coverage_of(other) >= threshold`.

Tại sao không dùng diện tích cho `contains`? Vì một hộp lớn chứa hộp nhỏ luôn có coverage 1.0 theo nghĩa “phần của hộp nhỏ”, nhưng nếu chia sai mẫu số sẽ ra 0.36. Tên hàm phải nói rõ mẫu số là ai.

`contains` là quan hệ **bao gồm biên**: cạnh trùng vẫn thỏa `<=`. Ví dụ `A=(0,0,10,10)` chứa `D=(0,0,5,5)`. Đừng áp quy ước nửa mở của diện tích giao cho `contains`; giao và chứa là hai hợp đồng riêng.

Gợi ý kiểm thử: chọn `A=(0,0,10,10)`, `B=(2,2,8,8)`, `C=(0,0,5,10)`. Tính tay:

- `A.coverage_of(C) = 50/50 = 1.0`.
- `C.coverage_of(A) = 50/100 = 0.5`.
- `A.contains(C) = True`, `C.contains(A) = False`.

## Bước 5 — Dung sai

`contains` với `tolerance` phải nới **cả bốn cạnh** của `self`:

```text
self.x1 - t <= other.x1
self.y1 - t <= other.y1
other.x2 <= self.x2 + t
other.y2 <= self.y2 + t
```

Không dùng `math.isclose` cho từng cặp cạnh, vì `isclose` so sánh tương đối và sẽ cho kết quả khác nhau ở tọa độ lớn. Dung sai ở đây là khoảng cách tuyệt đối, có đơn vị của hệ tọa độ.

`is_inside(other, tolerance)` nên gọi `other.contains(self, tolerance=tolerance)` để chỉ có một nguồn sự thật.

Kiểm tra `tolerance` **tại phương thức**, không trong `__post_init__`: phải là số thật (không `bool`), hữu hạn, `>= 0`. Tương tự, `contains_by_area` kiểm tra `threshold` là số thật hữu hạn trong `[0, 1]`; `NaN`/`inf` bị từ chối trước khi so sánh.

## Bước 6 — Dịch chuyển

`translate` trả `Rect(self.x1 + dx, self.y1 + dy, self.x2 + dx, self.y2 + dy)`. Kiểm tra `dx`, `dy` hữu hạn; nếu không, lỗi từ constructor là đủ. Không cần kiểm tra tràn số: `float` bão hòa thành `inf`, và constructor sẽ từ chối.

## Bước 7 — Bộ test bảng

Tổ chức test thành ba nhóm:

1. **Hình học**: bảng `(rect_a, rect_b, area, intersects)`.
2. **Quan hệ**: bảng `(outer, inner, contains, coverage)`.
3. **Lỗi**: bảng `(args, message_fragment)`.

Gợi ý dùng `pytest.mark.parametrize`. Với số thực, dùng `pytest.approx(..., abs=1e-9)`.

Thêm các ca biên bắt buộc:

- `A=(0,0,10,10)`, `D=(0,0,5,5)`: `A.contains(D) is True`, `D.contains(A) is False`.
- `A.contains(B, tolerance=-1)`, `tolerance=float("inf")`, `threshold=float("nan")` đều ném `ValueError`.
- Hai hộp rời nhau chỉ chạm cạnh: giao `0.0`, `intersects False`.
- Một hộp nằm trong hộp kia và chạm biên: `contains` vẫn `True` (quy ước bao gồm biên); đây không phải trường hợp giao bằng 0 vì hộp bên trong có diện tích dương.

Thêm test bất biến (property-style) không cần `hypothesis`:

- Với một tập cố định 20 hộp sinh từ seed, kiểm tra giao đối xứng và không vượt diện tích nhỏ.
- Kiểm tra `translate` bảo toàn diện tích.

## Bước 8 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from simple_rect import Rect
A = Rect(0, 0, 10, 10)
B = Rect(2, 2, 8, 8)
C = Rect(8, 8, 12, 12)
D = Rect(0, 0, 5, 5)
print(A.area, B.area, A.intersection_area(C))
print(A.contains(B), B.contains(A))
print(A.contains(D), D.contains(A))
print(round(A.coverage_of(B), 6), round(B.coverage_of(A), 6))
PY
```

Kết quả mong đợi:

```text
100.0 36.0 4.0
True False
True False
1.0 0.36
```

Nếu `A.intersection_area(C)` ra `36.0`, bạn đã quên `min` cạnh phải/dưới. Nếu `A.contains(B)` ra `False`, bạn đang dùng coverage thay vì so sánh cạnh.

## Bước 9 — Gỡ vướng

| Triệu chứng | Kiểm tra đầu tiên |
|---|---|
| Giao luôn bằng 0 | Bạn có đang dùng `max` cho cạnh trái/trên và `min` cho phải/dưới? |
| Giao âm | Thiếu `max(0, ...)` ở một chiều. |
| `coverage_of` > 1 | Sai mẫu số hoặc chưa kẹp. |
| Test số thực fail lẻ tẻ | Thiếu dung sai; đừng so `==` với số thực. |
| `Rect` vẫn sửa được | Thiếu `frozen=True`. |
| `ValueError` không đúng thông điệp | Kiểm tra thứ tự validate. |

## Bước 10 — Mở rộng

- Thêm `union(other)` trả hộp bao nhỏ nhất.
- Thêm `split_at(x)` / `split_at_y(y)` trả hai hộp, dùng lại ở bài 17.
- Thêm kiểm tra “gần như trùng” với dung sai tương đối.
- Nếu muốn đi xa: cài đặt interval tree để tìm mọi hộp giao với một truy vấn trong `O(log n + k)`.

## Tự đánh giá

Bạn hiểu bài khi trả lời được, không cần nhìn code:

1. Vì sao `intersection_area` dùng `max(0, ...)` ở từng chiều thay vì một `if`?
2. Vì sao `contains_by_area` không thể thay thế `contains`?
3. Dung sai `0.5` trên hộp `(0,0,10,10)` thay đổi kết quả của những cặp nào?
4. Tại sao từ chối `bool` lại quan trọng trong Python?
