# 55 — Bộ thực thi workflow có ngân sách

## Mục tiêu

Cài một máy trạng thái cho một lượt workflow nhiều bước, với **bốn ngân sách** (lượt, công cụ, ngữ cảnh, thời gian), phát hiện vòng lặp, và **sổ thao tác idempotent** để một lệnh lặp lại không tạo hiệu ứng thứ hai.

1. Tám trạng thái: `READY → GENERATING → DISPATCHING → VERIFYING → COMPLETED`, cộng `CLARIFYING`, `REFUSED`, `INCOMPLETE`.
2. Lý do dừng có kiểu: `TURN_BUDGET`, `TOOL_CALL_BUDGET`, `CONTEXT_BUDGET`, `TIME_BUDGET`, `LOOP_DETECTED`, `EFFECT_NOT_VERIFIED`.
3. Mỗi lời gọi công cụ có **một khóa thao tác**; lặp y hệt ⇒ phát lại kết quả đã lưu, không thực thi lần hai.
4. Đồng hồ tiêm được để test `TIME_BUDGET` mà không `sleep`.

## Giá trị

- Ranh giới giữa "agent treo" và "agent dừng đúng" là một tập ngân sách được kiểm tra ở đúng chỗ. Bài tập biến điều đó thành bảng trạng thái + mã lý do kiểm chứng được.
- Idempotency ở tầng thao tác là thứ khó nhất: bạn phải chứng minh **không có hiệu ứng thứ hai**, không chỉ "không lỗi".
- Đồng hồ tiêm được là kỹ thuật test bắt buộc khi có ngân sách thời gian; nếu `sleep` trong test, bộ test sẽ chậm và flaky.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Khó |
| Điều kiện | Máy trạng thái, bảng chuyển, băm chuẩn hoá, đồng hồ tiêm, `dataclass` |
| Runtime | Không mạng, không GPU, không framework agent |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/aegis-f` (nhánh `main`; REST payload ghi `"archived": true`)
- File nguồn: <https://github.com/triet4p/aegis-f/blob/main/app/src/main/java/io/github/triet4p/aegisf/agent/BoundedWorkflowExecutor.kt>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `enum WorkflowRunState { READY, GENERATING, DISPATCHING, VERIFYING, COMPLETED, CLARIFYING, REFUSED, INCOMPLETE }`.
  - `WorkflowRunStopReason` gồm `TURN_BUDGET, TOOL_CALL_BUDGET, CONTEXT_BUDGET, TIME_BUDGET, LOOP_DETECTED, …, EFFECT_NOT_VERIFIED`.
  - `WorkflowRunLimits(maxTurns = 12, maxToolCalls = 24, maxContextCharacters = 160_000, maxWallClockMillis = 300_000, maxRepeatedIdenticalCalls = 3, maxCaptureObservations = 4)`.
  - Ghi chú về idempotency: *"A mutation keeps one trusted operation key per exact model-facing call within the run, so an exact repeat replays the stored operation instead of creating a second effect."*
- Giới hạn bằng chứng: đọc 110 dòng đầu; không quan sát được logic chuyển trạng thái chi tiết, cách tính "exact repeat", hay hành vi `maxCaptureObservations`.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: tám trạng thái; các lý do dừng; bộ giới hạn với đúng sáu con số (12/24/160 000/300 000/3/4); ý tưởng khóa thao tác và phát lại.

Phần **do bài tập định nghĩa**:

- Bảng chuyển hợp lệ và thứ tự kiểm tra ngân sách.
- Cách chuẩn hoá lời gọi để băm (`tool + args` sắp khóa, số/chuỗi giữ nguyên).
- Ngữ nghĩa "ngữ cảnh" (tổng ký tự của transcript, cộng dồn).
- `EFFECT_NOT_VERIFIED`: khi bước xác minh sau một mutation thất bại.
- `maxCaptureObservations` dùng để giới hạn số quan sát giữ lại trong kết quả.
- Định dạng fixture/CLI, tên lỗi.

Nguồn **không** bao gồm: mô hình, HTTP, hay chính sách bảo mật đầy đủ.

## Phạm vi

Trong phạm vi:

- Một `Executor` nhận một "kịch bản" (script) các bước tất định từ fixture; công cụ là hàm Python giả.
- Sổ thao tác trong bộ nhớ; đồng hồ tiêm được.
- Test: từng lý do dừng, phát lại, chuyển trạng thái sai, ngữ cảnh.

Ngoài phạm vi:

- Không gọi mô hình; không streaming; không lưu bền.
- Không đa luồng; không huỷ giữa chừng (có thể là mở rộng).
- Không kiểm soát tần suất hay chi phí token.

## Cảnh báo production

- `maxWallClockMillis` chỉ có ý nghĩa nếu mọi bước đều kiểm tra đồng hồ; một bước chặn 10 phút sẽ vượt ngân sách mà không ai thấy. Bài tập kiểm tra giữa các bước, không cưỡng chế bên trong một bước.
- Khóa thao tác dựa trên chuẩn hoá tham số: hai lời gọi "trông giống" nhưng khác kiểu (`1` vs `"1"`) là hai khóa. Đây là quyết định an toàn (không gộp nhầm), không phải lỗi.
- Phát lại chỉ an toàn cho thao tác idempotent hoặc có khóa nghiệp vụ; với tác dụng phụ ngoài hệ thống, cần khoá ở phía đích.
- `maxCaptureObservations = 4` cắt bớt dữ liệu; đừng dùng kết quả đã cắt để chẩn đoán.

## Fixture offline

- `fixtures/script_happy.json` — vài bước, kết thúc `COMPLETED`.
- `fixtures/script_loop.json` — lặp y hệt một lời gọi 4 lần.
- `fixtures/script_context.json` — ngữ cảnh phình nhanh.
- `fixtures/script_effect_unverified.json` — mutation rồi xác minh thất bại.
- Không có URL ngoài; đồng hồ là hàm tiêm.

## Liên kết

- [SPEC.md](SPEC.md) — bảng trạng thái, ngân sách, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế executor, bẫy idempotency và đồng hồ, cách kiểm chứng.
