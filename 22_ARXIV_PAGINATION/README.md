# 22 — Phân trang kết quả tìm kiếm kiểu ArXiv

## Mục tiêu

Xây dựng client tìm kiếm có phân trang, chạy hoàn toàn trên fixture Atom XML cục bộ: dựng `search_query` đúng cú pháp, gọi từng trang với kích thước tối đa 100, dừng đúng lúc, khử trùng lặp theo định danh đã bỏ hậu tố phiên bản, và trả kết quả ổn định.

## Giá trị

- Phân trang là nơi dễ sinh lỗi lặp/thiếu bản ghi nhất: offset, kích thước trang cuối, trang rỗng, bản ghi trùng.
- Học cách tách **xây truy vấn** khỏi **thực thi phân trang** khỏi **parse XML**, để kiểm thử từng phần.
- Học cách làm việc với dữ liệu Atom có namespace và các trường thiếu.
- Bài tập cố ý sửa một điểm bất nhất quan sát được trong nguồn (xem mục Nguồn gốc).

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (chỉ thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Không cần mạng; hiểu XML namespace và HTTP semantics cơ bản |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/bridge-research`
- File nguồn: <https://github.com/triet4p/bridge-research/blob/main/python-sidecar/src/services/arxiv.py>
- Hành vi quan sát được:
  - Dựng truy vấn: `search_query += f" AND submittedDate:[{s_str} TO {e_str}]"` với `s_str = start_date.replace('-', '') + '0000'` và `e_str = … + '2359'`.
  - Mặc định không có keyword/category: `query_parts.append("cat:cs.AI")`.
  - Phân trang: `while len(all_papers) < max_results: … current_max = min(page_size, max_results - len(all_papers)) … start_index += page_size` (page size 100).
  - Parse Atom: `p_id = id_url.split('/abs/')[-1].split('v')[0]`; `entry.findall('atom:entry', ARXIV_XML_NAMESPACE)`.
  - Lỗi tải hoặc parse cả trang: ghi log rồi trả `[]`/dừng vòng lặp.
  - Nhánh bulk có `await self.arxiv_api_state.wait_for_arxiv()` trước mỗi trang (rate-limit).

**Phần là thiết kế của bài:** định dạng output JSON, fixture offline, luồng lỗi có mã, việc tăng offset theo số bản ghi thực nhận thay vì cố định 100, và kiểm tra ngày hợp lệ. Nguồn dùng `start_index += page_size` ngay cả khi `current_max` nhỏ hơn 100; bài yêu cầu `offset += received` để không bỏ sót khi trang cuối không đầy.

## Hành vi bài tập yêu cầu

- Không gọi mạng. Mọi phản hồi đọc từ `fixtures/pages/`.
- Truy vấn được dựng thuần, có thể kiểm thử không cần I/O.
- Phân trang tuần tự, tối đa 100 mục mỗi yêu cầu, không lặp offset, dừng khi đủ `max_results`, trang rỗng, hoặc lỗi toàn trang.
- Khử trùng lặp theo `paper_id` đã bỏ `vN`; giữ lần xuất hiện đầu tiên.
- Mọi bản ghi lỗi riêng lẻ bị bỏ qua kèm cảnh báo; một trang XML hỏng dừng mạch và được báo rõ.
- Kết quả sắp theo thứ tự nhận được (fixture đã sắp `submittedDate` giảm dần).

## Phạm vi

Trong phạm vi: query builder, transport offline, pagination, Atom parser, khử trùng, báo cáo, CLI.

Ngoài phạm vi: tải PDF, lưu file, gọi API thật, rate limiter thật, tìm kiếm mờ, UI.

## Fixture offline

`fixtures/` chứa:

- `pages/000000.xml`, `000100.xml`, `000200.xml`, `000300.xml` (rỗng) — 300 entry tổng hợp cho ba trang đầu; client chỉ lấy 250 mục đầu, không có dữ liệu thật.
- `duplicate/000000.xml` — 3 entry có một bản trùng, dùng riêng cho test khử trùng.
- `saved.json` — danh sách `paper_id` đã lưu.
- `expected/` — output mẫu cho ba truy vấn.

Fixture dùng ngày cố định, tác giả giả (`Author 001`), không chứa email hay định danh thật. Transport offline ghi lại các lời gọi vào bộ nhớ để test, không tạo file ngoài.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng dữ liệu, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế parser/phân trang và cách kiểm chứng.
