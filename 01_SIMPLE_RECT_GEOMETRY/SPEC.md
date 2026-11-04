# SPEC — SimpleRect

## Mục tiêu hành vi

Cho hai hộp chữ nhật trục song song, tính diện tích giao, kiểm tra giao, và xác định quan hệ chứa. Giao dùng quy ước nửa mở: cạnh chạm nhau không tạo diện tích. Quan hệ chứa dùng quy ước **bao gồm biên**: một hộp vẫn chứa hộp kia khi các cạnh trùng nhau hoặc hộp kia nằm sát biên.

## Kiểu dữ liệu

```python
@dataclass(frozen=True, slots=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
```

Mọi trường được chuẩn hóa thành `float` khi khởi tạo. `Rect` bất biến; mọi phép biến đổi trả về đối tượng mới.

## API bắt buộc

| Thành phần | Hợp đồng |
|---|---|
| `Rect(x1, y1, x2, y2)` | Kiểm tra và chuẩn hóa; ném `ValueError` nếu vi phạm. |
| `.area -> float` | `(x2 - x1) * (y2 - y1)`. |
| `.intersection_area(other) -> float` | Diện tích phần giao; `0.0` khi không chồng hoặc chỉ chạm biên. |
| `.intersects(other) -> bool` | `intersection_area(other) > 0.0`. |
| `.coverage_of(other) -> float` | `intersection_area(other) / other.area`, trong `[0.0, 1.0]`. |
| `.contains(other, *, tolerance=0.0) -> bool` | `other` nằm trọn trong `self`, **bao gồm biên**; nới mỗi cạnh `tolerance`. |
| `.is_inside(other, *, tolerance=0.0) -> bool` | `self` nằm trọn trong `other`, **bao gồm biên**; nới mỗi cạnh `tolerance`. |
| `.contains_by_area(other, *, threshold=0.7) -> bool` | `coverage_of(other) >= threshold`. |
| `.translate(dx, dy) -> Rect` | Dịch chuyển, giữ kích thước. |

Tất cả tham số `other` phải là `Rect`; nếu không, ném `TypeError`.

## Kiểm tra đầu vào

`__post_init__` **chỉ** kiểm tra tọa độ, theo thứ tự cố định:

1. Giá trị không phải `int`/`float` thật (bao gồm `bool`), hoặc là `float('nan')`, `inf`, `-inf` → `ValueError("coordinates must be finite numbers")`.
2. `x2 <= x1` hoặc `y2 <= y1` → `ValueError("invalid rectangle: x2 must be > x1 and y2 must be > y1")`.

Không chấp nhận chuỗi số (`"1"`) hay `Decimal`; người gọi phải tự chuyển đổi. Điều này giữ biên API hẹp và tránh so sánh kiểu ngầm.

### Kiểm tra tham số phương thức

`tolerance` và `threshold` **không** phải thuộc tính của `Rect`, nên không được kiểm tra trong `__post_init__`. Mỗi phương thức kiểm tra tham số của mình trước khi tính:

- `other`: phải là `Rect`; nếu không → `TypeError`.
- `contains` / `is_inside`: `tolerance` phải là `int`/`float` thật (không `bool`), hữu hạn (`math.isfinite`), và `>= 0`; vi phạm → `ValueError("tolerance must be a finite number >= 0")`.
- `contains_by_area`: `threshold` phải là `int`/`float` thật (không `bool`), hữu hạn, và `0.0 <= threshold <= 1.0`; vi phạm → `ValueError("threshold must be a finite number within [0, 1]")`. `NaN` và `inf` bị từ chối.

Thứ tự kiểm tra trong phương thức: kiểu `other` → `tolerance`/`threshold` → tính toán.

## Công thức và quy ước

Giao của `self` và `other`:

```text
ix1 = max(self.x1, other.x1)
iy1 = max(self.y1, other.y1)
ix2 = min(self.x2, other.x2)
iy2 = min(self.y2, other.y2)
area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
```

Quy ước nửa mở: một điểm biên không thuộc cả hai hộp theo cùng một phía, nên chiều rộng giao bằng `0` khi `ix2 == ix1`. Hệ quả: hai hộp chỉ chạm cạnh có `intersection_area == 0.0` và `intersects == False`.

`contains(other, tolerance=t)`:

```text
self.x1 - t <= other.x1
self.y1 - t <= other.y1
other.x2 <= self.x2 + t
other.y2 <= self.y2 + t
```

`is_inside` là `other.contains(self, tolerance=t)`.

`contains`/`is_inside` là quan hệ **bao gồm biên**: các bất đẳng thức `<=` ở trên cho phép cạnh trùng. Điều này độc lập với quy ước nửa mở của diện tích giao.

`coverage_of` dùng diện tích **của `other`** làm mẫu số. Vì `other.area > 0` theo kiểm tra khởi tạo, phép chia luôn xác định. Kết quả được kẹp vào `[0.0, 1.0]` để triệt sai số dấu phẩy động.

## Tính xác định

- Cùng đầu vào cho cùng kết quả trên mọi lần chạy và mọi thứ tự gọi.
- Không phụ thuộc thời gian, môi trường, hay trạng thái toàn cục.
- Mỗi tọa độ nguyên có `|x| <= 2**53` được biểu diễn chính xác trong `float64`, nhưng điều đó **không** bảo đảm diện tích hay giao chính xác: hiệu và tích trung gian có thể vượt `2**53` và bị làm tròn.
- Chỉ khi mọi hiệu và tích trung gian là số nguyên có `|giá trị| <= 2**53` thì kết quả mới biểu diễn chính xác. Ngoài phạm vi đó, không giả định đẳng thức tuyệt đối; kiểm thử dùng dung sai.
- Với số thực, so sánh bằng trong kiểm thử phải dùng dung sai `abs=1e-9`; API không tự làm tròn.

## Trường hợp biên

| Trường hợp | Kết quả bắt buộc |
|---|---|
| Hai hộp rời nhau | `intersection_area == 0.0`, `intersects == False` |
| Chạm cạnh dọc: `A=(0,0,10,10)`, `B=(10,0,20,10)` | `0.0`, `False` |
| Chạm đúng một điểm góc | `0.0`, `False` |
| Một hộp nằm trọn trong hộp kia | `coverage_of` của hộp nhỏ tính theo hộp lớn; `contains` đúng chiều |
| Hộp nằm sát biên trong hộp kia: `A=(0,0,10,10)`, `D=(0,0,5,5)` | `A.contains(D) == True`, `D.contains(A) == False` |
| Hai hộp trùng khít | `contains` cả hai chiều, `coverage_of == 1.0` |
| `other` lớn hơn `self` | `coverage_of(other)` nhỏ; `self.contains(other) == False` |
| Tọa độ âm | Hợp lệ nếu `x2 > x1`, `y2 > y1` |
| Hộp suy biến (chiều rộng hoặc cao bằng 0) | `ValueError` |
| `tolerance` dương | Nới cả bốn cạnh; có thể làm hai hộp “chứa” nhau dù hở |
| `tolerance` âm / NaN / inf | `ValueError` |
| `threshold` NaN / inf / ngoài `[0,1]` | `ValueError` |

## Ví dụ cụ thể

Cho `A = Rect(0, 0, 10, 10)`, `B = Rect(2, 2, 8, 8)`, `C = Rect(8, 8, 12, 12)`.

| Biểu thức | Kết quả | Giải thích |
|---|---|---|
| `A.area` | `100.0` | `10 × 10` |
| `B.area` | `36.0` | `6 × 6` |
| `A.intersection_area(B)` | `36.0` | `B` nằm trọn trong `A` |
| `A.coverage_of(B)` | `1.0` | `36 / 36` |
| `B.coverage_of(A)` | `0.36` | `36 / 100` |
| `A.contains(B)` | `True` | `B` nằm trong `A` |
| `B.contains(A)` | `False` | `A` không nằm trong `B` |
| `A.contains_by_area(B)` | `True` | `1.0 >= 0.7` |
| `B.contains_by_area(A)` | `False` | `0.36 < 0.7` |
| `A.intersection_area(C)` | `4.0` | vùng `[8,10] × [8,10]` |
| `A.intersects(C)` | `True` | diện tích dương |
| `A.contains(C)` | `False` | `C` vượt biên |
| `A.translate(5, -2)` | `Rect(5, -2, 15, 8)` | giữ nguyên kích thước |

Ví dụ then chốt cho bài học về mẫu số: nếu gọi API nguồn với `self=A`, `other=B`, `is_contain_by_area` trả `False` dù `B` nằm trong `A`, vì `36/100 < 0.7`. Với `self=B`, `other=A`, nó trả `True` dù `B` không chứa `A`. Bài tập định nghĩa lại thành `coverage_of` + `contains_by_area` để tên và phép toán khớp nhau.

## Tiêu chí nghiệm thu quan sát được

1. Toàn bộ bảng ví dụ trên chạy đúng khi viết thành test.
2. `pytest -q` xanh, không có test bị skip.
3. Có ít nhất một test khẳng định cạnh chạm nhau cho kết quả `0.0`.
4. Có test khẳng định `A.contains(B) != B.contains(A)` cho cặp lồng nhau.
5. Có test khẳng định `coverage_of` đối xứng về diện tích giao nhưng không đối xứng về tỉ lệ: `A.coverage_of(B) != B.coverage_of(A)`.
6. Có test cho `ValueError` với `Rect(0, 0, 0, 1)`, `Rect(float("nan"), 0, 1, 1)`, `A.contains(B, tolerance=-1)`, `A.contains(B, tolerance=float("inf"))`, và `A.contains_by_area(B, threshold=float("nan"))`.
7. `Rect` không có thuộc tính nào ghi được sau khởi tạo (`FrozenInstanceError`).
8. Có test khẳng định `A=(0,0,10,10)` chứa `D=(0,0,5,5)` (chạm biên) nhưng `D` không chứa `A`.

## Quan hệ với nguồn

Giữ nguyên: công thức giao, quy ước cạnh chạm cho **giao** (nửa mở), kiểm tra `x2 > x1`/`y2 > y1`, và ý tưởng `is_contain_by_coords` với dung sai (chứa bao gồm biên).

Thay đổi có chủ đích: tách `coverage_of` khỏi `contains`; đổi mẫu số sang diện tích của hộp được đo; thêm kiểm tra số hữu hạn, `bool`, dung sai và ngưỡng; đặt tên `is_inside` cho quan hệ ngược. Không tuyên bố những điểm này là hành vi của nguồn.

## Non-goals

- Hình học phi trục (đa giác, đường tròn, phép quay).
- Tối ưu tìm kiếm không gian trên hàng triệu hộp.
- Đọc hoặc suy luận layout từ file Excel — đó là bài 17.
- Biểu diễn hình chữ nhật bằng pixel nguyên với quy ước nửa mở khác (ví dụ cạnh phải không bao gồm).
