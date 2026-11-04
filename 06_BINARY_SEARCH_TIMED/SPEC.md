# SPEC — Binary searcher có chỉ mục và đo thời gian

## Mục tiêu hành vi

Nhận một dãy số nguyên bất kỳ. Lần tìm kiếm đầu tiên (hoặc lần gọi `build_index`) xây một chỉ mục đã sắp xếp gồm `(giá trị, vị trí gốc)`. Mỗi truy vấn trả vị trí gốc của phần tử bằng giá trị tìm kiếm, theo chính sách xác định khi có trùng lặp. Thời gian build và search được đo riêng, và số lần dò midpoint được đếm.

## API

```cpp
#include <cstddef>
#include <optional>
#include <vector>

struct SearchStats {
    std::size_t comparisons = 0;   // số midpoint đã dò trong lần search này
    double build_seconds = 0.0;    // 0 nếu lần này không build
    double search_seconds = 0.0;   // thời gian của lần search này
    bool rebuilt = false;          // true nếu lần này đã build chỉ mục
};

class BinarySearcher {
public:
    explicit BinarySearcher(std::vector<int> values);

    void build_index();  // idempotent; không làm gì nếu đã build
    std::optional<std::size_t> search(int value, SearchStats* stats = nullptr);
    bool is_built() const noexcept;
    std::size_t size() const noexcept;

private:
    std::vector<int> values_;
    // cấu trúc chỉ mục do bạn chọn
    bool built_ = false;
};
```

Không cần constructor mặc định; nếu muốn, nó tương đương vector rỗng.

## Chỉ mục

Chỉ mục là dãy các cặp `(value, original_index)` được sắp theo:

1. `value` tăng dần.
2. `original_index` tăng dần khi `value` bằng nhau.

Sắp xếp phải **ổn định theo khóa phụ**. Nếu chỉ sắp theo `value`, thứ tự các bản trùng phụ thuộc thuật toán sort và chính sách “vị trí gốc nhỏ nhất” có thể sai.

Tìm kiếm dùng tìm kiếm nhị phân tìm **biên dưới** (phần tử đầu tiên có `value >= target`), rồi kiểm tra `value == target`. Nếu không bằng, trả `std::nullopt`.

## Chính sách trùng lặp

Với nhiều phần tử cùng giá trị, trả **vị trí gốc nhỏ nhất**. Ví dụ `values = {5, 1, 3, 3, 9}`, `search(3)` trả `2` (không phải `3`).

## Thời gian

- `build_index()` đo bằng `std::chrono::steady_clock`, gán vào `SearchStats::build_seconds` của lần search gọi nó. Nếu `search` tự build lười, lần đó có `rebuilt = true`.
- Nếu chỉ mục đã có, `build_seconds == 0.0` và `rebuilt == false`.
- `search_seconds` đo toàn bộ thân `search`, bao gồm cả lần build lười (nếu có). Người đọc muốn tách thì trừ `build_seconds`.
- Không đảm bảo độ phân giải; trên máy nhanh, giá trị có thể là `0.0`. Test không được khẳng định `> 0`.
- `comparisons` là số lần đọc khóa tại midpoint, không phải số phép so sánh CPU. Vòng lặp chuẩn dò một midpoint mỗi lần lặp.

## Ví dụ

`values = {5, 1, 3, 3, 9, 7}`.

Chỉ mục:

| Vị trí chỉ mục | value | original_index |
|---:|---:|---:|
| 0 | 1 | 1 |
| 1 | 3 | 2 |
| 2 | 3 | 3 |
| 3 | 5 | 0 |
| 4 | 7 | 5 |
| 5 | 9 | 4 |

| Truy vấn | Kết quả | `comparisons` | Ghi chú |
|---|---:|---:|---|
| `search(3)` | `2` | 1 | midpoint đầu tiên là index 2 |
| `search(5)` | `0` | 2 | dò index 2 rồi 3 |
| `search(1)` | `1` | 2 | dò index 2 rồi 0 |
| `search(4)` | `nullopt` | 3 | biên dưới là index 3 (value 5) |
| `search(0)` | `nullopt` | 3 | biên dưới là index 0 (value 1) |
| `search(10)` | `nullopt` | 3 | biên dưới là cuối dãy |
| `values` rỗng, `search(1)` | `nullopt` | 0 | không có midpoint |

Sau lần `search` đầu, gọi `search` lần hai: `rebuilt == false`, `build_seconds == 0.0`.

## Kiểm tra và lỗi

- Constructor nhận bản sao của vector; thay đổi vector bên ngoài sau đó không ảnh hưởng.
- `search` trên mảng rỗng trả `std::nullopt`, không ném.
- Không có đầu vào không hợp lệ ở mức kiểu: mọi `int` đều hợp lệ, kể cả `INT_MIN`/`INT_MAX`.
- `stats` có thể là `nullptr`; khi đó không ghi gì.
- `build_index` gọi nhiều lần không xây lại; `is_built()` phản ánh trạng thái.

## Tính xác định

- Cùng `values` và cùng truy vấn → cùng vị trí trả về, cùng `comparisons`, bất kể thời gian.
- Không dùng `std::sort` không ổn định nếu comparator chỉ so `value`; comparator phải so cả `original_index`.
- Không phụ thuộc thứ tự đánh giá của biểu thức.
- Kết quả không phụ thuộc số lần gọi trước đó, ngoại trừ `rebuilt`/`build_seconds` của lần đầu.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Mảng rỗng | `size()==0`; search trả `nullopt`, comparisons 0 |
| Một phần tử, tìm thấy | vị trí 0 |
| Một phần tử, không thấy | `nullopt`, comparisons 1 |
| Tất cả bằng nhau, tìm thấy | vị trí 0 (nhỏ nhất) |
| Tất cả bằng nhau, không thấy | `nullopt`, comparisons `ceil(log2(n+1))` theo vòng lặp |
| Trùng ở đầu/cuối | vẫn trả vị trí gốc nhỏ nhất |
| `INT_MIN`, `INT_MAX` | tìm đúng; không tràn `mid` |
| Mảng đã sắp xếp | vẫn đúng |
| Mảng sắp xếp giảm | vẫn đúng |
| Gọi `build_index` hai lần | lần hai không đổi chỉ mục |
| Search trước, search sau | lần sau không build lại |

## Tiêu chí nghiệm thu

1. Bảng ví dụ trên chạy đúng, bao gồm `comparisons`.
2. Có test khẳng định `search(3) == 2` với mảng có hai số 3.
3. Có test khẳng định lần search thứ hai có `rebuilt == false` và `build_seconds == 0.0`.
4. Có test mảng rỗng và mảng một phần tử.
5. Có test `INT_MIN`, `INT_MAX`.
6. Test không khẳng định bất kỳ giá trị thời gian nào ngoài `>= 0`.
7. Biên dịch không warning với `-Wall -Wextra -Wpedantic` (hoặc `/W4` trên MSVC).
8. Chạy test bằng một lệnh, không cần Qt.

## Non-goals

- Giao diện Qt, `paintEvent`, highlight.
- Tìm kiếm mờ, tìm nhiều kết quả, trả toàn bộ vị trí trùng.
- Cập nhật chỉ mục khi mảng thay đổi sau khi build.
- Đo thời gian chính xác cấp nano giây hoặc benchmark thống kê.
- So sánh hiệu năng với `std::lower_bound`.
