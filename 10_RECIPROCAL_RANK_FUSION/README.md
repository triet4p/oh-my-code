# 10 — Reciprocal Rank Fusion có trọng số

## Mục tiêu

Tự viết hàm hợp nhất nhiều danh sách kết quả đã xếp hạng thành một danh sách duy nhất bằng Weighted Reciprocal Rank Fusion (RRF). Bài tập rèn cách biến một công thức ngắn thành hợp đồng xử lý trùng lặp, trọng số, thứ tự tie-break và kiểu dữ liệu rõ ràng.

## Giá trị học được

- RRF không cần điểm số gốc, chỉ cần thứ hạng — vì sao điều đó hữu ích khi trộn các nguồn khác thang đo.
- Cùng một tài liệu xuất hiện ở nhiều nguồn: cộng điểm, nhưng chỉ giữ metadata của lần xuất hiện đầu.
- Trọng số âm/không hợp lệ phải được chuẩn hóa trước khi tính.
- Tie-break phải xác định: thứ tự chèn của Python là một lựa chọn, nhưng cần nêu rõ.
- Phân biệt lỗi lập trình (sai kiểu) với dữ liệu hợp lệ nhưng rỗng.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 3–4 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- Không cần thư viện ngoài, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/cogmem`, file `cogmem_api/engine/search/fusion.py`.
- URL chính xác: <https://github.com/triet4p/cogmem/blob/master/cogmem_api/engine/search/fusion.py>

Hành vi quan sát được trong nguồn:

- `weighted_reciprocal_rank_fusion(result_lists, source_weights=None, k=60, source_names=None)`.
- Nếu `source_names is None`, mặc định `["semantic", "bm25", "graph", "temporal"]`.
- Nếu `source_weights is None`, dùng `{}`.
- Với mỗi danh sách, tên nguồn là `source_names[source_idx]` nếu có, ngược lại `f"source_{source_idx}"`.
- Trọng số: `max(float(source_weights.get(source_name, 1.0)), 0.0)` — trọng số âm bị kẹp về 0.
- Duyệt từng kết quả với `rank` bắt đầu từ 1; nếu là `tuple` hoặc không phải `RetrievalResult` thì ném `TypeError`.
- `doc_id = retrieval.id`; lần xuất hiện đầu lưu `all_retrievals[doc_id]`; điểm cộng dồn `source_weight / (k + rank)`; `source_ranks[doc_id][f"{source_name}_rank"] = rank`.
- Kết quả sắp theo điểm giảm dần bằng `sorted(..., reverse=True)`, gán `rrf_rank` từ 1.
- Nguồn không kiểm tra `k`; không khử trùng lặp trong cùng một danh sách; không định nghĩa tie-break ngoài thứ tự chèn.

## Phạm vi bài tập

Xây module `rrf`:

- `RetrievalResult` bất biến với `id`, `score`, `payload`.
- `MergedCandidate` với `result`, `score`, `rank`, `source_ranks`.
- `fuse(result_lists, source_names=None, source_weights=None, k=60)`.
- Kiểm tra `k`, trọng số, tên nguồn, kiểu phần tử.
- Khử trùng lặp trong một danh sách theo lần xuất hiện đầu.
- Tie-break xác định theo thứ tự xuất hiện đầu tiên.

Không nằm trong phạm vi: tính BM25/embedding, chuẩn hóa điểm, lọc theo ngưỡng, phân trang.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, quy tắc, ví dụ tính tay.
- [GUIDE.md](GUIDE.md) — thiết kế, bẫy, test.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn không khử trùng lặp trong một danh sách và không có tie-break tường minh. Bài tập thêm hai quy tắc này và nêu rõ. Công thức, thứ tự rank bắt đầu từ 1, kẹp trọng số và việc giữ kết quả đầu tiên bám sát nguồn.
