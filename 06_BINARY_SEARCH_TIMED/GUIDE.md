# GUIDE — Binary searcher có chỉ mục và đo thời gian

## Bước 0 — Môi trường

Linux/macOS:

```bash
mkdir -p 06_BINARY_SEARCH_TIMED/work/src 06_BINARY_SEARCH_TIMED/work/tests
cd 06_BINARY_SEARCH_TIMED/work
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force 06_BINARY_SEARCH_TIMED/work/src, 06_BINARY_SEARCH_TIMED/work/tests
```

Không cần CMake. Cấu trúc gợi ý:

```text
src/binary_searcher.h
src/binary_searcher.cpp
tests/test_binary_searcher.cpp
```

## Bước 1 — Quyết định chỉ mục trước khi viết code

Có ba lựa chọn:

1. Sắp mảng giá trị và dùng `std::lower_bound` — mất vị trí gốc.
2. Sắp vector `pair<int, size_t>` — đơn giản, đúng.
3. Sắp vector chỉ số, comparator so `values_[i]` — tiết kiệm bộ nhớ, nhưng comparator phức tạp hơn.

Bài tập chọn (2) vì dễ nhìn và dễ chứng minh chính sách trùng. Viết comparator:

```text
if (a.first != b.first) return a.first < b.first;
return a.second < b.second;
```

Tại sao cần vế thứ hai? Vì chính sách “vị trí gốc nhỏ nhất” dựa vào thứ tự các bản trùng trong chỉ mục. Nếu comparator chỉ so `first`, `std::sort` có thể đảo chúng.

## Bước 2 — Dựng lớp

- Constructor nhận `std::vector<int>` **theo giá trị**, rồi `std::move` vào thành viên. Điều này tạo bản sao độc lập.
- `built_` khởi tạo `false`.
- `size()` trả `values_.size()`.
- `is_built()` trả `built_`.

Không cần `mutable` nếu `search` không `const`. Bài tập chọn `search` non-const để tránh ngụ ý thread-safe.

## Bước 3 — Build idempotent

```text
void build_index() {
    if (built_) return;
    auto start = steady_clock::now();
    index_.clear();
    index_.reserve(values_.size());
    for (size_t i = 0; i < values_.size(); ++i)
        index_.emplace_back(values_[i], i);
    std::sort(index_.begin(), index_.end(), compare);
    built_ = true;
    // lưu thời gian nếu cần
}
```

Vấn đề: `build_index()` không có tham số `stats`, nhưng `search` cần báo `build_seconds`. Có hai cách:

- `build_index()` lưu `last_build_seconds_` vào thành viên; `search` đọc và gán.
- Viết helper private `build_index_impl()` trả thời gian; API công khai gọi nó và bỏ kết quả.

Cách hai sạch hơn. Ghi rõ: gọi `build_index()` thủ công trước, rồi `search` sẽ báo `build_seconds == 0.0` vì lần search đó không build.

## Bước 4 — Tìm biên dưới

Đừng dùng `std::lower_bound` nếu bạn cần đếm `comparisons` chính xác theo định nghĩa “số midpoint đã dò”. Viết vòng lặp:

```text
size_t lo = 0, hi = index_.size();
while (lo < hi) {
    size_t mid = lo + (hi - lo) / 2;
    ++comparisons;
    if (index_[mid].first < value) lo = mid + 1;
    else hi = mid;
}
```

Sau vòng lặp, `lo` là biên dưới. Kiểm tra `lo < size && index_[lo].first == value`.

Ghi chú:

- `mid = lo + (hi - lo) / 2` tránh tràn `lo + hi` (dù `size_t` lớn, vẫn là thói quen đúng).
- `hi` là **one-past-the-end**, không phải `size - 1`. Đây là nguồn lỗi phổ biến nhất.
- Với mảng rỗng, vòng lặp không chạy, `comparisons == 0`.

Nếu bạn muốn dùng `std::lower_bound`, hãy định nghĩa `comparisons` là “số lần comparator được gọi” và truyền comparator đếm được. Cả hai cách đều hợp lệ miễn test khớp định nghĩa; bài tập chọn vòng lặp tường minh để dễ hiểu.

## Bước 5 — Đo thời gian

```text
auto t0 = steady_clock::now();
... build ...
auto t1 = steady_clock::now();
build_seconds = duration<double>(t1 - t0).count();
```

`steady_clock` không bị chỉnh bởi đồng hồ hệ thống. Không dùng `system_clock`.

Trong `search`:

```text
auto s0 = steady_clock::now();
bool did_build = !built_;
if (did_build) build...
... tìm ...
auto s1 = steady_clock::now();
```

Gán `stats` sau khi tính xong. Nếu `stats == nullptr`, bỏ qua.

Một cái bẫy: nếu bạn đo cả thời gian gán `stats` vào `search_seconds`, giá trị sẽ phụ thuộc người gọi. Hãy chốt `s1` trước khi ghi stats.

## Bước 6 — Test

Không dùng framework; viết `expect(bool, message)` đếm fail và trả mã thoát.

Các ca:

1. Bảng ví dụ SPEC, so `optional` và `comparisons`.
2. Trùng lặp: `{3,3,3}` → `search(3) == 0`.
3. Lần hai không rebuild.
4. Rỗng, một phần tử.
5. `INT_MIN`, `INT_MAX`.
6. Gọi `build_index()` trước, rồi search: `rebuilt == false`.
7. `stats == nullptr` không crash.
8. Kiểm tra `size()`.

Gợi ý: viết helper `check_found(searcher, value, expected_index, expected_comparisons)`.

## Bước 7 — Biên dịch và chạy

Linux/macOS:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic \
    src/binary_searcher.cpp tests/test_binary_searcher.cpp -o run_tests
./run_tests
```

Windows MSVC (Developer Command Prompt):

```bat
cl /std:c++17 /EHsc /W4 src\binary_searcher.cpp tests\test_binary_searcher.cpp /Fe:run_tests.exe
run_tests.exe
```

Windows MinGW:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic src/binary_searcher.cpp tests/test_binary_searcher.cpp -o run_tests.exe
```

Kỳ vọng: không warning, exit 0.

## Bước 8 — Kiểm chứng độc lập

Thêm một `main` nhỏ hoặc dùng test hiện có để in:

```text
values: 5 1 3 3 9 7
search(3) -> 2 (1 comparison)
search(4) -> not found (3 comparisons)
second search rebuilt? false
```

Nếu `search(3)` ra `3`, comparator của bạn thiếu khóa phụ. Nếu `search(4)` ra 2 comparisons, bạn đang dùng `hi = size - 1` với vòng `lo <= hi`, dẫn đến số probe khác.

Kiểm tra tràn: chạy với mảng 1 triệu phần tử toàn `INT_MAX`; không được crash hay treo.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Trả vị trí trong mảng đã sắp | Quên lấy `.second`. |
| Trùng trả vị trí bất kỳ | Comparator thiếu `original_index`. |
| Không tìm thấy dù có | `hi` sai (one-past-end) hoặc điều kiện `<`/`<=` sai. |
| Vòng lặp vô hạn | `hi = mid` nhưng `lo = mid` (thiếu `+1`). |
| `build_seconds` luôn 0 | Build thủ công trước, hoặc đo sai nhánh. |
| Lần hai vẫn rebuild | `built_` không được đặt hoặc bị reset. |
| Kết quả khác nhau giữa lần chạy | Dùng `sort` với comparator không toàn phần. |
| Warning signed/unsigned | `int` so với `size_t`; ép kiểu có chủ đích. |

## Bước 10 — Mở rộng

- Trả toàn bộ vị trí trùng bằng `equal_range`.
- Thêm `insert`/`erase` cập nhật chỉ mục (bài học về chi phí).
- So sánh thời gian build/search với tìm kiếm tuyến tính trên nhiều kích thước.
- Thêm `search_all` và kiểm thử với dữ liệu ngẫu nhiên so với tìm tuyến tính.
- Nếu đi xa: chỉ mục trên đĩa hoặc cấu trúc B-tree.

## Tự đánh giá

1. Vì sao cần khóa phụ `original_index` trong comparator?
2. Vì sao `hi` là `size()` chứ không phải `size() - 1`?
3. `comparisons` của bạn định nghĩa chính xác là gì, và test có khớp không?
4. Vì sao không nên khẳng định thời gian `> 0`?
