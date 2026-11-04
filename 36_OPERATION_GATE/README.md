# 36 — Cổng thao tác bắt buộc

## Mục tiêu

Cài đặt `OperationGate`: phân loại tool đọc tùy chọn và tool thay đổi trạng thái bắt buộc; xác thực tham số tại thời điểm gọi; theo dõi call id đang chờ; chỉ đánh dấu hoàn tất khi có kết quả có kiểu, tương ứng đúng call; chặn báo thành công khi thao tác bắt buộc chưa chạy.

## Giá trị

- Mô hình ngôn ngữ có thể “nói” đã đặt vé mà không gọi tool; cổng này biến lời nói thành điều kiện kiểm chứng được.
- Học cách tách **xác thực lúc gọi** khỏi **xác thực lúc có kết quả**: `ToolMessage` không lặp tham số.
- Học ghép call id để tránh nhận nhầm kết quả của tool khác.
- Học giới hạn: cổng chỉ chứng minh “đã gọi và có kết quả”, không chứng minh nghiệp vụ thành công.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | `dataclasses`, hiểu vòng đời tool call |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/ecommerce-agent-databricks`
- File nguồn: <https://github.com/triet4p/ecommerce-agent-databricks/blob/main/agent_core/tool_policy.py>
- Hành vi quan sát được:
  - `ToolRole.OPTIONAL_READ` và `ToolRole.REQUIRED_ACTION`.
  - Docstring: *"state-changing … MUST be executed before a success response can be returned"*.
  - `OperationGate(policies, required_satisfied, pending_calls, activated_required)`.
  - `validate_and_track(tool_name, arguments, tool_result=None, *, call_id=None)`.
  - Nếu không có policy → `return True`.
  - Nếu role không phải required và tool không được activate → `return True` (bỏ qua cả validate args).
  - Khi `tool_result is None`: kiểm tra từng `required_args` (None hoặc chuỗi rỗng/whitespace → `ValueError`); yêu cầu `call_id`; lưu `pending_calls[call_id] = tool_name`.
  - Comment: *"Validate required arguments only on the call. A ToolMessage does not repeat them, so validating them again on the result would incorrectly reject a valid correlated completion."*
  - Khi có result: yêu cầu `call_id` và `pending_calls.get(call_id) == tool_name`; kiểm tra `_is_typed_tool_result`; pop pending; thêm vào `required_satisfied`.
  - `all_required_satisfied()`: required names ⊆ satisfied.
  - `report_unsatisfied()` trả sorted.
  - `require_tool(name)`: unknown → `ValueError`.
  - `reset()` xóa ba tập.
  - `_is_typed_tool_result`: None → False; str → `bool(strip)`; dict/list/tuple/set → `bool`; khác → True.

**Phần là thiết kế của bài:** mã lỗi, từ chối call id trùng, CLI scenario, kiểm tra thứ tự, fixture. Nguồn ghi đè `pending_calls` khi trùng id; bài chặn để tránh mất dấu.

## Hành vi bài tập yêu cầu

- Tool không có policy → luôn hợp lệ, không theo dõi.
- Tool optional và không được activate → hợp lệ, không theo dõi, kể cả khi truyền result.
- Tool required (theo policy hoặc activate):
  - lần gọi: kiểm tra `required_args`; thiếu/rỗng → lỗi; thiếu `call_id` → lỗi; call id đã chờ → lỗi; lưu pending.
  - lần kết quả: phải khớp call id đã chờ; kết quả phải “typed non-empty”; pop + đánh dấu; không kiểm tra lại args.
- `all_required_satisfied` chỉ xét required policy ∪ activated.
- `require_tool` kích hoạt tool optional thành bắt buộc cho request hiện tại; không biết tool → lỗi.
- `reset` xóa sạch, dùng giữa các request.
- Không tự gọi tool, không tự sinh kết quả.

## Phạm vi

Trong phạm vi: policy, gate, call correlation, report, scenario CLI, test.

Ngoài phạm vi: gọi tool thật, JSON Schema/Pydantic, mô hình ngôn ngữ, retry, xác thực nghiệp vụ, lưu trạng thái qua request.

## Fixture offline

- `fixtures/policies.json`: 4 tool (optional, required, optional-activated, unknown).
- `fixtures/scenarios/*.json`: chuỗi bước call/result/status.
- `fixtures/expected/`.
- Không gọi mạng, không tool thật; dữ liệu tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — state, quy tắc, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế gate và kiểm chứng.
