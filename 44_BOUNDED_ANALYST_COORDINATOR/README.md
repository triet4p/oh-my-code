# 44 — Coordinator có ngân sách analyst

## Mục tiêu

Cài một coordinator tuần tự với **ngân sách gọi analyst** và **ngân sách sửa kế hoạch**, kiểm tra khả thi trên **bản sao sâu** của thế giới, và luôn kết thúc bằng `decided` hoặc `bounded_stop`.

1. `coordinate(fixture, analyst) -> CoordinationResult` với tối đa 6 lần gọi analyst và 2 lần sửa.
2. Mỗi đề xuất được kiểm tra bằng cách thực thi trên bản sao sâu; thế giới gốc không đổi.
3. Kết quả có kiểu chặt: từ chối trường lạ, `outcome` chỉ thuộc `{"decided", "bounded_stop"}`.
4. Ghi `trace` đủ để tái dựng quyết định mà không cần chạy lại.

## Giá trị

- "Bounded stop" là kỹ năng production: hệ thống phải dừng **có lý do** và báo cáo trung thực thay vì treo hoặc trả kết quả dở.
- Kiểm tra khả thi trên bản sao sâu là mẫu an toàn: thử nghiệm không được để lại tác dụng phụ. Đây là bài tập trực tiếp về `deepcopy` và tính thuần.
- Lược đồ kết quả `extra="forbid"` dạy cách giữ hợp đồng giữa các tầng — trường lạ thường là dấu hiệu ai đó đang lách hợp đồng.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Trung bình |
| Điều kiện | `dataclass`, `copy.deepcopy`, kiểm tra kiểu, vòng lặp có ngân sách |
| Runtime | Không mạng, không LLM, không GPU |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/mosaic-slm` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/mosaic-slm/blob/main/src/mosaic/agents/coordinator.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Hằng ngân sách: `_DEFAULT_MAX_ANALYST_CALLS = 6`, `_DEFAULT_MAX_REVISIONS = 2`.
  - `CoordinationResult(BaseModel)` với `model_config = ConfigDict(extra="forbid")` và các trường `episode_seed, day, requests, recommendations, decision, outcome, analyst_calls, revision_count, trace`.
  - `CoordinationOutcome = Literal["decided", "bounded_stop"]`.
  - `CoordinatorAgent.coordinate(...)` kiểm tra `episode_seed`/`day` khớp với simulator.
  - Ghi chú về kiểm tra khả thi: *"feasibility is checked on a deep copy with the real ActionExecutor. No LLM, tokens, memory tools, or parallel calls are used."*
- Giới hạn bằng chứng: đọc ở mức file/đoạn đã nêu; không thấy chi tiết định dạng `trace` hay nội dung `ActionExecutor`.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: hai ngân sách 6/2; bộ trường của kết quả; `extra="forbid"`; hai giá trị `outcome`; kiểm tra khớp seed/ngày; kiểm tra khả thi trên bản sao sâu, tuần tự, không LLM.

Phần **do bài tập định nghĩa**:

- Mô hình thế giới tối giản: tài nguyên có sức chứa, yêu cầu có khối lượng, ánh xạ `kind -> resource`.
- Giao diện `Analyst`, `ScriptedAnalyst`, `DefaultAnalyst` và nghĩa của việc trả `None` (abstain).
- Định dạng `trace` (step, kind, detail) và chuỗi lý do khả thi.
- Tên ngoại lệ; luật "kiểm tra ngân sách trước khi gọi".
- Rằng analyst sai **không** phải ngoại lệ — đó là dữ liệu để vòng lặp sửa.

Nguồn **không** bao gồm: LLM thật, memory tool, simulator sản xuất.

## Phạm vi

Trong phạm vi:

- Thế giới tối giản + `ActionExecutor` trên bản sao; scripted analyst đọc từ fixture.
- Bất biến ngân sách, tính cô lập, kiểm thử tất định.

Ngoài phạm vi:

- Không gọi mô hình, không token, không memory, không song song.
- Không tối ưu tổ hợp (không phải solver).
- Không lưu episode giữa các lần chạy, không giao diện mạng.

## Cảnh báo production

- Coordinator thật chạy với LLM: mỗi lần gọi tốn tiền và không tất định. Bài này cố ý thay bằng analyst thuần để bạn kiểm chứng phần **điều phối**, không phải phần sinh.
- `deepcopy` không miễn phí: với thế giới lớn, chi phí kiểm tra có thể vượt chi phí thực thi. Ở quy mô bài này, an toàn quan trọng hơn tốc độ.
- Ngân sách phải kiểm tra **trước** khi gọi. Gọi rồi mới đếm là đã vượt một lượt.
- `bounded_stop` là kết quả hợp lệ, không phải lỗi — đừng ném ngoại lệ khi hết ngân sách.

## Fixture offline

- `fixtures/infeasible_then_feasible.json` — script hai bước, kết thúc `decided`.
- `fixtures/always_infeasible.json` — script một đề xuất lặp lại, kết thúc `bounded_stop` do hết lượt sửa.
- `fixtures/abstain_forever.json` — script toàn `null`, kết thúc `bounded_stop` do hết lượt gọi.
- `fixtures/seed_mismatch.json` — `episode_seed` lệch để kiểm tra ngoại lệ.
- Không có URL ngoài; mọi đầu vào là JSON cục bộ.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng fixture, luật khả thi, ví dụ trace, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế vòng lặp ngân sách, cô lập bản sao, cách kiểm chứng.
