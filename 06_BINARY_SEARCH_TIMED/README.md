# 06 — Binary search có đo thời gian build và search

## Mục tiêu

Tự viết một lớp tìm kiếm nhị phân trên mảng chưa sắp xếp: lần gọi đầu xây chỉ mục đã sắp kèm vị trí gốc, các lần sau tái sử dụng chỉ mục; kết quả trả về vị trí trong mảng ban đầu. Đo riêng thời gian build và thời gian search, và đếm số phép so sánh để kiểm chứng thuật toán mà không phụ thuộc đồng hồ.

## Giá trị học được

- Tách “chuẩn bị dữ liệu” khỏi “truy vấn”: chi phí một lần so với chi phí mỗi lần.
- Sắp xếp cặp `(giá trị, vị trí gốc)` thay vì sắp xếp mảng và mất vị trí.
- Tìm kiếm nhị phân trả vị trí gốc, không phải vị trí trong mảng đã sắp.
- Xử lý trùng lặp bằng một chính sách xác định (vị trí gốc nhỏ nhất).
- Đo thời gian bằng `steady_clock`; không dùng thời gian để khẳng định đúng/sai.

## Ngôn ngữ và độ khó

- Ngôn ngữ: C++17.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 3–4 giờ.

## Điều kiện tiên quyết và runtime

- Trình biên dịch C++17 (MSVC, clang, hoặc g++).
- Không cần CMake; một lệnh `g++`/`cl` là đủ.
- Không cần thư viện ngoài.

## Nguồn gốc

- Nguồn: `triet4p/SearchAppQt`, file `BinarySearcher.cpp`.
- URL chính xác: <https://github.com/triet4p/SearchAppQt/blob/main/BinarySearcher.cpp>

Hành vi quan sát được trong nguồn:

- `BinarySearcher` kế thừa `NeedSortedSearcher`; `search(int value)` tạo `TimeCounter`, gọi `startBuild()`, và nếu `!isSorted` thì `buildSortedIndexArr()`, rồi `endBuild()`.
- Sau đó `startSearch()`, dùng `left = 0`, `right = sortedIndexArr.size() - 1`, vòng `while (left <= right)`, `mid = left + (right - left) / 2`.
- So sánh `sortedIndexArr[mid].first == value`; nếu bằng, trả `sortedIndexArr[mid].second` (vị trí gốc) và ghi thời gian; nếu nhỏ hơn thì `left = mid + 1`, ngược lại `right = mid - 1`.
- Không tìm thấy trả `-1`.
- Nguồn có hai constructor: mặc định và nhận `vector<int>`.

## Phạm vi bài tập

Xây một thư viện nhỏ `binary_searcher`:

- Nạp mảng bất kỳ (có thể chưa sắp xếp).
- `build_index()` công khai, idempotent.
- `search(value)` trả `std::optional<std::size_t>` là vị trí gốc.
- `SearchStats` gồm thời gian build, thời gian search, số phép so sánh.
- Chính sách trùng: trả vị trí gốc nhỏ nhất.
- Test không dựa vào thời gian.

Không nằm trong phạm vi: giao diện Qt, trực quan hóa, tìm kiếm trên dữ liệu thay đổi liên tục, cấu trúc cân bằng.

## Liên kết

- [SPEC.md](SPEC.md) — API, chính sách trùng, ví dụ, tiêu chí.
- [GUIDE.md](GUIDE.md) — cách xây chỉ mục, đếm so sánh, test.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn trả `int` với `-1` và để lộ `TimeCounter` trong lớp; bài tập đổi sang `std::optional<std::size_t>`, thêm chính sách trùng tường minh và đếm so sánh. Các thay đổi này là thiết kế của bài tập. Nguồn cũng không thể hiện rõ `isSorted` được đặt ở đâu; bài tập định nghĩa `build_index()` là API công khai.
