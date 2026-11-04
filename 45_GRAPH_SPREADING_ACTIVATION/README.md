# 45 — Lan truyền kích hoạt trên đồ thị có kiểu cạnh

## Mục tiêu

Cài **spreading activation** trên đồ thị có hướng: mỗi cạnh mang trọng số và loại, mỗi loại có hệ số nhân riêng; năng lượng lan theo công thức `A(u) * w * mu(kind) * delta`, bị chặn trên bởi `a_max`, có ngưỡng dừng `epsilon`, giới hạn số bước, **hạn ngạch số lần phát** mỗi nút và **thời gian trơ** một bước.

1. Nạp đồ thị từ fixture văn bản, không cần crate ngoài.
2. Lan truyền theo vòng lặp đồng bộ từng bước, thứ tự xử lý xác định.
3. Chặn bão hoà, dừng theo ngưỡng, giới hạn bước và hạn ngạch phát.
4. Xuất điểm kích hoạt cuối, số lần phát, và số bước đã chạy.

## Giá trị

- Đây là thuật toán lan truyền có **ba cơ chế chống bùng nổ** khác nhau (bão hoà, ngưỡng, hạn ngạch) — hiểu được cách chúng tương tác là kỹ năng thiết kế hệ thống, không chỉ cài đặt công thức.
- Vòng lặp đồng bộ theo bước buộc bạn tách "tính toán" khỏi "áp dụng", tránh lỗi cập nhật xen kẽ (một nút đọc giá trị vừa được nút khác ghi trong cùng bước).
- Bài tập Rust không dùng crate: bạn tự quản lý chỉ số, thứ tự duyệt, và định dạng xuất ổn định.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Rust 2021, chỉ `std` (không dùng `serde`, `petgraph`, `tokio`) |
| Độ khó | Trung bình–Khó |
| Điều kiện | `HashMap`, `Vec`, vòng lặp theo bước, đọc file, `cargo test` |
| Runtime | Rust 1.70+; không mạng, không GPU |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/cognition` (nhánh `master`)
- File nguồn: <https://github.com/triet4p/cognition/blob/master/crates/cognition-graph/src/activation.rs>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `fn get_multiplier(edge_type: EdgeType) -> f32 { … EdgeType::AoCausal => 2.0, EdgeType::Entity => 1.5, EdgeType::Transition => 1.8, EdgeType::Semantic => 0.8 … }`
  - `ActivationParams { delta: 0.8, a_max: 2.0, epsilon: 0.01, max_steps: 10, max_fires: 3 }`
  - Công thức trong chú thích mã nguồn: `// Energy = A(u,t) * w(u,v) * mu(edge_type) * delta`
  - Chống vòng lặp bằng tập trơ `just_fired: HashSet<NodeIndex>` cộng hạn ngạch `firing_counts`.
  - Bộ test có sẵn: `test_sum_accumulation_logic`, `test_saturation_guard`, `test_firing_quota_guard`.
- Giới hạn bằng chứng: nguồn là Rust bất đồng bộ (petgraph/tokio); bài tập bỏ phần async và petgraph, giữ đúng công thức và bốn tham số.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: bảng hệ số theo loại cạnh; bộ tham số mặc định `delta 0.8 / a_max 2.0 / epsilon 0.01 / max_steps 10 / max_fires 3`; công thức năng lượng; vai trò của tập trơ và hạn ngạch; ba nhóm test.

Phần **do bài tập định nghĩa**:

- Định dạng fixture văn bản thay cho cấu trúc đồ thị của petgraph.
- Việc **cộng dồn trong một bước rồi mới kẹp** `a_max` (để kết quả không phụ thuộc thứ tự cạnh).
- Nghĩa chính xác của "trơ": nút phát ở bước `t` không được phát ở bước `t+1`, được phát lại từ `t+2` nếu còn hạn ngạch.
- Quy tắc dừng: bước không có nút nào phát, hoặc chạm `max_steps`.
- Định dạng xuất cố định (ba cột, độ chính xác 6 chữ số), thứ tự sắp xếp.
- Tên lỗi và mã thoát CLI.

Nguồn **không** bao gồm: async runtime, khoá đọc/ghi, hay tích hợp memory. Bài này thuần thuật toán.

## Phạm vi

Trong phạm vi:

- Một binary `activation` đọc fixture, in bảng kết quả.
- `cargo test` cho công thức, bão hoà, hạn ngạch, chu trình, giới hạn bước.
- Đồ thị vài chục nút là đủ; không cần tối ưu.

Ngoài phạm vi:

- Không xử lý song song, không async, không đồ thị động.
- Không lưu trạng thái giữa các lần chạy.
- Không truy vấn "top-k liên quan" phức tạp; chỉ xuất điểm.

## Cảnh báo production

- Nguồn chạy trong hệ thống bất đồng bộ với khoá; ở đây mọi thứ tuần tự. Đừng suy ra tính an toàn luồng từ bài này.
- `f32` trong nguồn gây sai số tích luỹ; bài tập dùng `f64`. Nếu bạn giữ `f32`, các ví dụ số sẽ lệch ở chữ số thứ 7 — hãy ghi rõ.
- Hạn ngạch phát là biện pháp chống bùng nổ, **không** phải mô hình sinh học chính xác.
- Với đồ thị lớn, chi phí mỗi bước là `O(E)`; `max_steps` là chặn trên thực tế, đừng đặt lớn tuỳ tiện.

## Fixture offline

- `fixtures/chain.txt` — chuỗi ba nút, hai loại cạnh, dùng cho ví dụ chuẩn.
- `fixtures/cycle.txt` — chu trình hai nút để kiểm tra dừng.
- `fixtures/saturate.txt` — nhiều cạnh song song cùng đích để kiểm tra `a_max`.
- `fixtures/quota.txt` — nút nguồn không có cạnh ra, kiểm tra hạn ngạch và trơ.
- Không có URL ngoài, không đọc dữ liệu hệ thống.

## Liên kết

- [SPEC.md](SPEC.md) — định dạng fixture, thuật toán từng bước, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế cấu trúc Rust, cạm bẫy thứ tự cập nhật, cách kiểm chứng.
