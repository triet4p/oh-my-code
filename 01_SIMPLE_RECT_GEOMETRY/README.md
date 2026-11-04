# 01 — SimpleRect: hình học hộp chữ nhật cho layout tài liệu

## Mục tiêu

Tự viết một thư viện hình học nhỏ, bất biến, dùng để biểu diễn hộp chữ nhật trên một mặt phẳng tọa độ và trả lời ba câu hỏi: hai hộp có chồng nhau không, diện tích chồng là bao nhiêu, và hộp này có nằm trong hộp kia không. Đây là viên gạch đầu tiên cho các bài xử lý layout bảng tính (bài 17) và kiểm tra vùng giao diện.

## Giá trị học được

- Chuyển một công thức hình học đơn giản thành API có hợp đồng rõ ràng, thay vì một hàm “đúng với ví dụ đang có”.
- Phân biệt **giao hình học** với **quan hệ chứa**: cùng một phép nhân diện tích nhưng mẫu số quyết định ngữ nghĩa.
- Kiểm thử biên: cạnh chạm nhau, chứa khi trùng biên, tọa độ âm, hình suy biến, số thực không hữu hạn.
- Nhìn ra một cái bẫy thật trong nguồn: tên hàm `is_contain_by_area` không khớp với phép chia mà nó thực hiện.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Dễ** (bài mở đầu).
- Thời lượng gợi ý: 2–3 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12 trở lên, quản lý môi trường bằng `uv`.
- Không cần thư viện ngoài; chỉ dùng `dataclasses`, `math`, `pytest`.
- Không cần mạng, tài khoản hay dịch vụ ngoài.

## Nguồn gốc

- Nguồn: `triet4p/excel2md`, file `src/rect.py`.
- URL chính xác: <https://github.com/triet4p/excel2md/blob/main/src/rect.py>

Hành vi quan sát được trong nguồn:

- Lớp `SimpleRect` nhận bộ bốn tọa độ `(x1, y1, x2, y2)`, từ chối nếu không đủ bốn phần tử hoặc nếu `x2 <= x1` hay `y2 <= y1` bằng `ValueError`.
- `get_area()` trả `(x2 - x1) * (y2 - y1)`.
- `get_intersect_area()` lấy `max` của các cạnh trái/trên và `min` của các cạnh phải/dưới; nếu hiệu không dương thì trả `0.0`. Cạnh chạm nhau vì thế không tính là giao.
- `is_contain_by_area(other, overlap_threshold=0.7)` chia diện tích giao cho **diện tích của chính `self`** rồi so với ngưỡng. Vì mẫu số là `self`, hàm này thực chất đo “`self` bị `other` phủ bao nhiêu”, không phải “`self` chứa `other`”.
- `is_contain_by_coords(other, tolerance=0.0)` kiểm tra `self` nằm trong `other` bằng bốn so sánh cạnh, có nới dung sai.

## Phạm vi bài tập

Bạn sẽ xây một package `simple_rect` với:

- `Rect` bất biến, chỉ nhận số hữu hạn và tọa độ hợp lệ.
- Các phép toán có tên đúng nghĩa: `intersection_area`, `intersects`, `coverage_of`, `contains`, `is_inside`, `translate`.
- Quy ước rõ: giao là nửa mở (cạnh chạm không tạo diện tích), còn `contains`/`is_inside` bao gồm biên (cạnh trùng vẫn tính).
- Một bộ kiểm thử bảng (table-driven) phủ các trường hợp biên.

Không nằm trong phạm vi: đọc file Excel, dựng cây không gian (R-tree/interval tree), xử lý đa giác, tọa độ trang PDF.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng API, quy tắc kiểm tra, ví dụ và tiêu chí nghiệm thu.
- [GUIDE.md](GUIDE.md) — thiết kế từng bước, bẫy thường gặp, cách tự kiểm chứng.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập giữ nguyên phần hình học cốt lõi và **sửa cách đặt tên** để ngữ nghĩa không bị đảo. Không có ý định mô tả hành vi đã sửa đó như hành vi của nguồn: mọi khác biệt được nêu rõ trong [SPEC.md](SPEC.md#quan-hệ-với-nguồn).
