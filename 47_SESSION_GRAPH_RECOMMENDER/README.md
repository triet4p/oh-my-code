# 47 — Gợi ý phiên bằng đồ thị hai phía

## Mục tiêu

Cài một bản **LightGCN tối giản** bằng Python thuần: đồ thị hai phía phiên–item, chuẩn hoá đối xứng, lan truyền nhiều lớp rồi lấy trung bình, huấn luyện BPR, và gợi ý top-k theo cosine từ lịch sử phiên.

1. Dựng ma trận kề chuẩn hoá `D^{-1/2} A D^{-1/2}` không self-loop.
2. Lan truyền `L` lớp và lấy trung bình các lớp (không có phép biến đổi tuyến tính).
3. Huấn luyện BPR với mẫu âm tất định, kiểm tra loss giảm.
4. Gợi ý: vector phiên = trung bình embedding item trong lịch sử, chuẩn hoá, cosine, loại item đã xem, top-k.

## Giá trị

- LightGCN bỏ hết phi tuyến và self-loop; hiểu **vì sao bỏ** quan trọng hơn thuộc công thức. Bài tập bắt bạn chứng minh từng bước bằng số.
- BPR là loss pairwise: bạn phải suy ra gradient và kiểm tra bằng tay, không thể "để autograd lo".
- Tách rõ ba thứ thường bị trộn: **biểu diễn** (lan truyền), **mục tiêu** (BPR), **truy hồi** (cosine top-k).

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Khó |
| Điều kiện | Đại số tuyến tính cơ bản, đạo hàm hàm hợp, chuẩn hoá vector, RNG có seed |
| Runtime | Không mạng, không GPU, không `torch`/`faiss`/`numpy` |
| Thời lượng gợi ý | 10–12 giờ |

## Nguồn gốc

- Repo: `triet4p/otto-rec-sys` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/otto-rec-sys/blob/main/src/candidate_generation/gnn.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Lan truyền kiểu LightGCN "hacked": gọi thẳng `x = conv.propagate(norm_edge_index, x=x, edge_weight=norm_edge_weight)` rồi `torch.mean(torch.stack(all_layer_embeddings, dim=0), dim=0)`.
  - Loss BPR: `return -torch.mean(F.logsigmoid(pos_scores - neg_scores))`.
  - Vector phiên bằng trung bình embedding lịch sử qua explode/group-by: `exploded_emb = history_with_emb.explode('embedding')`.
  - Truy hồi: `faiss.normalize_L2(query_vectors)` rồi `faiss_index.search(query_vectors, top_k)`.
  - Công nghệ nguồn: PyTorch, `torch_geometric`, FAISS, Polars.
- Giới hạn bằng chứng: đọc ở mức file; không quan sát được siêu tham số huấn luyện, cách sinh mẫu âm, hay chi tiết chuẩn hoá cạnh.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: ý tưởng lan truyền không có phép biến đổi tuyến tính, trung bình các lớp, loss BPR dạng `-log σ(s_pos - s_neg)`, vector phiên là trung bình embedding item, chuẩn hoá L2 trước khi tìm top-k.

Phần **do bài tập định nghĩa**:

- Ma trận kề **dense** cỡ nhỏ thay cho `torch_geometric`; không self-loop (LightGCN chuẩn).
- Khởi tạo embedding bằng LCG, mẫu âm tất định, thứ tự cập nhật cố định.
- Gradient BPR viết tay và test số học.
- Truy hồi bằng vòng lặp cosine thay FAISS (bài tập offline, không phụ thuộc thư viện).
- Định dạng fixture/output, tên lỗi, tiêu chí hội tụ.

Nguồn **không** bao gồm: dataset Otto thật, huấn luyện quy mô lớn, FAISS, hay pipeline candidate đầy đủ.

## Phạm vi

Trong phạm vi:

- Đồ thị ≤ 50 nút, `dim ≤ 8`, `layers ≤ 3` để chạy vài giây.
- Ba hàm công khai: `build_norm_adj`, `propagate`, `train_bpr`, cộng `recommend`.
- CLI: dựng đồ thị từ fixture, huấn luyện N bước, in loss theo mốc và top-k cho một lịch sử.

Ngoài phạm vi:

- Không `torch`, không autograd, không GPU, không FAISS.
- Không đánh giá offline (NDCG/recall) trên dữ liệu thật.
- Không tối ưu hiệu năng; đây là bài về đúng đắn số học.

## Cảnh báo production

- Ma trận dense `O((U+I)^2)` chỉ dùng cho đồ thị nhỏ; với dữ liệu thật phải dùng sparse và partition. Đừng suy ra hiệu năng từ bài này.
- LightGCN **không** chuẩn hoá hàng về 1; nếu bạn "sửa" cho hàng tổng bằng 1, bạn đã đổi mô hình và kết quả sẽ khác.
- BPR không có ràng buộc hiệu lực; mẫu âm ngẫu nhiên có thể trùng item dương nếu bạn không kiểm tra.
- Không có cold-start: phiên chưa có item nào không tạo được vector.

## Fixture offline

- `fixtures/toy_graph.json` — 2 phiên, 3 item, dùng cho ví dụ chuẩn hoá và lan truyền.
- `fixtures/session_history.json` — lịch sử phiên + embedding item cố định cho ví dụ cosine.
- `fixtures/bpr_step.json` — ba vector cho test gradient một bước.
- `fixtures/train_small.json` — 6 phiên, 10 item, dùng cho test loss giảm.
- Không có URL ngoài; không tải dữ liệu.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, đầu vào/ra, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế lan truyền, gradient BPR, cạm bẫy và kiểm chứng.
