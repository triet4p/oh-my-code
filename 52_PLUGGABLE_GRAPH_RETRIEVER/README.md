# 52 — Bộ truy hồi đồ thị cắm được

## Mục tiêu

Định nghĩa **một** giao diện truy hồi đồ thị với đúng bộ tham số của nguồn, cài hai chiến lược (BFS lan truyền và PPR), đăng ký theo tên, và chứng minh pipeline phía sau **không đổi** khi thay chiến lược.

1. Khai báo `GraphRetriever` (ABC) với 14 tham số đúng tên và đúng thứ tự như nguồn.
2. Cài `BFSRetriever` (đa nguồn, giới hạn bước và ngân sách mở rộng) và `PPRRetriever` (lặp công suất có damping).
3. Dùng chung một bộ lọc (`tags`, `tags_match`, `tag_groups`, `allowed_fact_types`, `fact_type`).
4. Đăng ký theo tên; tên lạ ném lỗi kèm danh sách hợp lệ đã sắp.
5. Pipeline hậu xử lý cố định: sắp xếp, cắt top-k, không nhánh theo tên retriever.

## Giá trị

- Đây là bài tập về **ranh giới trừu tượng**: nếu pipeline phải `if name == "ppr"`, trừu tượng đã rò. Bài kiểm tra là "thay tên, chỉ đổi thứ hạng".
- Bộ tham số dài 14 mục là bài học thực tế: chữ ký rộng thường là dấu hiệu ranh giới chưa đúng, nhưng khi đã có hợp đồng thì phải giữ đúng để thay thế được.
- BFS và PPR cho hai kiểu điểm khác nhau (theo bước vs theo xác suất dừng); chuẩn hoá và so sánh chúng là bài học về "cùng API, khác ngữ nghĩa".

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`abc`, `asyncio`, `math`) |
| Độ khó | Trung bình |
| Điều kiện | `ABC`/`Protocol`, `async`/`await`, lặp công suất, `inspect.signature` |
| Runtime | Không mạng, không GPU, không cơ sở dữ liệu |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/cogmem` (nhánh `master`, repo đã archived 2026-10-23)
- File nguồn: <https://github.com/triet4p/cogmem/blob/master/cogmem_api/engine/search/graph_retrieval.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `class GraphRetriever(ABC)` với thuộc tính `name` và `async retrieve(pool, query_embedding_str, bank_id, fact_type, budget, query_text, semantic_seeds, temporal_seeds, adjacency, tags, tags_match, tag_groups, allowed_fact_types) -> tuple[list[RetrievalResult], MPFPTimings | None]`.
  - Docstring nêu mục đích: *"BFS spreading activation, PPR, etc. … swapped without changing the rest of the recall pipeline"*.
- Giới hạn bằng chứng: đọc 60 dòng đầu; không quan sát được cài đặt cụ thể của BFS/PPR trong nguồn, cũng không thấy định nghĩa `RetrievalResult`/`MPFPTimings`.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: lớp trừu tượng `GraphRetriever` với `name`; chữ ký `async retrieve(...)` và đúng 14 tham số; kiểu trả về `(list[RetrievalResult], timings | None)`; mục tiêu "thay được mà không đổi pipeline".

Phần **do bài tập định nghĩa**:

- Nội dung `RetrievalResult`, `MPFPTimings`, `GraphPool` (nguồn không nêu).
- Thuật toán cụ thể của BFS và PPR, damping, ngưỡng hội tụ.
- Ngữ nghĩa từng tham số lọc, cách xử lý `tags_match`/`tag_groups`.
- Registry theo tên, lỗi `UnknownRetriever`.
- Pipeline hậu xử lý cố định và test "chỉ đổi thứ hạng".

Nguồn **không** bao gồm: cơ sở dữ liệu thật, SQL, hay pool kết nối; bài tập dùng `GraphPool` trong bộ nhớ.

## Phạm vi

Trong phạm vi:

- Đồ thị ≤ 200 nút, mỗi nút ≤ 10 cạnh; embedding 4 chiều.
- Hai retriever; bộ lọc dùng chung; registry; pipeline.
- CLI: `recall --retriever bfs|ppr --fixture ...`, in kết quả JSON.

Ngoài phạm vi:

- Không DB, không SQL, không vector index; không song song.
- Không học tham số; damping và ngưỡng là hằng của bài.
- Không hợp nhất nhiều nguồn (RRF là bài 10 trong lộ trình).

## Cảnh báo production

- Chữ ký 14 tham số là dấu hiệu nợ thiết kế: trong hệ thống thật nên gói thành một `RetrievalRequest` để thêm tham số không phá implementer. Bài tập giữ nguyên để học sự đánh đổi.
- BFS và PPR cho **điểm không cùng thang đo**; nếu pipeline trộn với nguồn khác, phải chuẩn hoá hoặc dùng RRF.
- `budget` là chặn chi phí, không phải chặn thời gian; với đồ thị lớn, `O(budget)` vẫn có thể chậm nếu mỗi bước quét rộng.
- Không tin `adjacency` từ nguồn ngoài: nút lạ trong danh sách kề phải bị bỏ hoặc báo lỗi, đừng để `KeyError` giữa pipeline.

## Fixture offline

- `fixtures/graph_small.json` — 5 nút, dùng cho ví dụ BFS.
- `fixtures/graph_two_nodes.json` — hai nút đối xứng, dùng cho PPR có nghiệm giải tích.
- `fixtures/graph_tagged.json` — nút có `tags` và `type` để kiểm tra lọc.
- `fixtures/configs.json` — cấu hình budget/top_k/damping.
- Không có URL ngoài; không kết nối DB.

## Liên kết

- [SPEC.md](SPEC.md) — chữ ký, thuật toán, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế trừu tượng, kiểm tra rò rỉ, cách kiểm chứng.
