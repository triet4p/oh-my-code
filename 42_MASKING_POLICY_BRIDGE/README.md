# 42 — Cầu nối policy masking với tensor

## Mục tiêu

Cài một **cổng duy nhất** nối policy chọn vị trí che (dữ liệu thuần) với batch tensor có padding: policy chỉ trả chỉ số, bridge giữ luật tổng số cố định, khôi phục mask đúng shape/device/dtype và không bao giờ chạm vùng đệm.

1. Định nghĩa giao diện `MaskPolicy` tối thiểu và `TensorLike` đủ dùng (không bắt buộc `torch`).
2. Cài `apply_batched_masking(batch, config, *, seed=None, rng=None, policy=None)`.
3. Kiểm tra luật "tổng số cố định" **tại bridge**, từ chối policy trả sai thay vì tự sửa.
4. Bảo toàn padding, thiết bị, dtype và tính bất biến của đầu vào.

## Giá trị

- Đây là dạng lỗi rất thật trong code ML: logic đúng nhưng biên giới hai thế giới (tensor có thiết bị, policy thuần Python) bị rò — mask rơi về CPU, pad bị che, hoặc tổng số lệch một đơn vị mà không ai phát hiện.
- Bài tập buộc tách **ba trách nhiệm**: chọn (policy), đếm (bridge), biểu diễn (adapter). Trộn chúng là nguồn gốc của phần lớn bug masking.
- Rèn cách viết "cổng" có kiểm tra: mọi đường đi đều qua đó, không có đường tắt.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn; adapter `torch` là tùy chọn |
| Độ khó | Trung bình |
| Điều kiện | `Protocol`, `deepcopy`, hiểu shape/dtype/device; nên đọc bài 41 trước |
| Runtime | Không mạng, không GPU; `torch` chỉ cần nếu thử adapter thật |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/anomaly-representation-learning` (nhánh `master`)
- File nguồn: <https://github.com/triet4p/anomaly-representation-learning/blob/master/src/representation/masking.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Chữ ký hàm: `apply_batched_masking(batch, config, *, seed=None, rng=None, policy=None)`.
  - Docstring nêu vai trò: *"This bridge only converts one padded torch row to PatchBatch and restores the resulting boolean mask to the original device … the frozen total-count rule stays in this bridge"*.
  - Có kiểm tra lỗi khi cấp đồng thời hai nguồn ngẫu nhiên: *"provide either seed or rng, not both"*.
- Giới hạn bằng chứng: các trích dẫn trên là mức file/đoạn, không có số dòng; bài tập không đọc phần huấn luyện của repo.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: chữ ký ba tham số từ khóa; bridge là nơi giữ luật tổng số; khôi phục mask về thiết bị gốc; lỗi khi vừa `seed` vừa `rng`.

Phần **do bài tập định nghĩa**:

- Giao diện `MaskPolicy` và kiểu `TensorLike` tối thiểu (5 thành viên).
- Luật padding: `valid_lengths` theo hàng, `n_patches = ceil(valid / patch_size)`, pad luôn `False`.
- Bridge **từ chối** policy trả sai tổng (`PolicyCountMismatch`) thay vì tự sửa.
- Ngoại lệ có tên, định dạng fixture, PRNG LCG 32-bit.
- Bộ đếm gọi policy để chứng minh lỗi tham số xảy ra trước mọi tác dụng phụ.

Nguồn **không** bao gồm: chạy `torch` thật, autograd, hay vòng huấn luyện. Adapter `torch` là phần mở rộng tùy chọn, không tính vào tiêu chí.

## Phạm vi

Trong phạm vi:

- `FakeTensor` thuần Python để test không cần `torch`.
- Bridge một hàm, policy một protocol, lỗi có tên, CLI đọc fixture JSON.

Ngoài phạm vi:

- Không autograd, không tensor thưa, không `bfloat16`, không nhiều thiết bị trong một batch.
- Không tối ưu hiệu năng — đây là bài về hợp đồng và biên giới.
- Không cài encoder/loss.

## Cảnh báo production

- Trong nguồn, `batch` là tensor thật và mask phải quay về đúng thiết bị trước khi dùng cho encoder; bài này mô phỏng bằng `FakeTensor`. Khi port sang `torch`, kiểm tra `mask.device == batch.device` bằng test.
- Padding là nguồn lỗi âm thầm số một: mask "đúng số lượng" nhưng che vào pad làm loss vô nghĩa mà không crash. Luôn có test riêng.
- Bridge **không** phải nơi chứa chiến lược học; nếu bạn thêm heuristic chọn vị trí vào bridge, đó là dấu hiệu thiết kế sai.
- Không dùng `random` toàn cục: kết quả sẽ phụ thuộc thứ tự gọi từ nơi khác.

## Fixture offline

- `fixtures/padded_batch.json` — batch 2 hàng, hàng thứ hai có 1 điểm pad, kèm `config`.
- `fixtures/invalid_counts.json` — policy trả sai tổng để kiểm tra `PolicyCountMismatch`.
- `fixtures/seed_conflict.json` — mô tả lời gọi có cả `seed` và `rng`.
- Không có URL ngoài; test dùng `FakeTensor` và PRNG cục bộ.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng dữ liệu, luật padding, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế bridge, cạm bẫy thiết bị/pad, cách kiểm chứng.
