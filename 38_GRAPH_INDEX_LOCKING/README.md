# 38 — Đồ thị có chỉ mục và khóa

## Mục tiêu

Cài đặt đồ thị có hướng với hai khóa độc lập: dữ liệu đồ thị và bảng ánh xạ `NodeId → index`. Thực hiện đúng thứ tự khóa để tránh deadlock, giữ bất biến giữa map và đồ thị, và chứng minh bằng stress test đa luồng có thời hạn.

## Giá trị

- Hai khóa lồng nhau là nguồn deadlock kinh điển; bài học là **thu thập dữ liệu rồi thả khóa** trước khi lấy khóa ghi.
- Học bất biến: mọi entry trong map phải trỏ tới node tồn tại; node mới chỉ quan sát được khi cả hai cấu trúc đã nhất quán.
- Học test tất định cho chương trình đồng thời: khẳng định số đếm, không khẳng định thứ tự.
- Học vì sao clone index (Copy) quan trọng.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Rust 1.75+ (chỉ `std`, không crate ngoài) |
| Độ khó | Trung bình–khó |
| Điều kiện | `RwLock`, `thread`, `mpsc`; hiểu borrow checker cơ bản |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/cognition`
- File nguồn: <https://github.com/triet4p/cognition/blob/master/crates/cognition-graph/src/graph.rs>
- Hành vi quan sát được:
  - `pub(crate) inner: RwLock<DiGraph<MemoryNode, EdgeData>>`.
  - `pub(crate) node_indices: RwLock<HashMap<NodeId, NodeIndex>>` để map UUID → index O(1).
  - `add_node`: lấy write lock `node_indices`, kiểm tra trùng, lấy write lock `inner`, `add_node`, chèn index.
  - `add_edge`: đọc index, sao chép `NodeIndex` ra biến, **thả read lock**, rồi mới lấy write lock `inner`.
  - Comment nguyên văn: *"IMPORTANT DEADLOCK PREVENTION: We acquire the read lock, extract the data we need (copying the NodeIndex), and then EXPLICITLY drop the read lock before acquiring the write lock."*
  - `get_node`: đọc index, copy, thả; đọc graph; clone node.
  - `node_count`: read lock graph.
  - `Default` triển khai `new`.

**Phần là thiết kế của bài:** thay `petgraph` bằng cấu trúc `Vec` tự viết để không cần dependency, giữ nguyên hai khóa/thứ tự; thêm `edge_count`, mã lỗi, stress test có timeout. Nguồn dùng tokio; bài dùng `std::sync` cho dễ chạy offline, phần mở rộng yêu cầu port sang tokio.

## Hành vi bài tập yêu cầu

- `add_node` trùng id → `DuplicateNode`, không thay đổi gì.
- `add_edge` thiếu nguồn/đích → `MissingNode` tương ứng; không thêm cạnh.
- Tự loop hợp lệ; cạnh trùng được phép (multigraph).
- `get_node` trả clone; không expose tham chiếu nội bộ.
- `node_count`/`edge_count` chính xác dưới đa luồng.
- Không giữ read guard của index khi lấy write guard của graph.
- Không dùng `unsafe`.
- Stress test 8 luồng × 100 node/cạnh hoàn tất trong 5 giây, số đếm đúng.

## Phạm vi

Trong phạm vi: hai khóa, add/get/count, lỗi, test tuần tự và song song.

Ngoài phạm vi: xóa node/cạnh, duyệt BFS/DFS, trọng số lan truyền, async tokio, persistence, petgraph.

## Fixture offline

- Test Rust dựng dữ liệu trong bộ nhớ; không file, không mạng.
- `fixtures/graph.json` (tùy chọn) mô tả node/cạnh cho CLI demo, nhưng test không phụ thuộc.
- Không crate ngoài; `cargo test` không cần tải dependency.

## Liên kết

- [SPEC.md](SPEC.md) — API, thứ tự khóa, bất biến, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế khóa và stress test.
