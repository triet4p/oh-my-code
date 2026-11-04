# GUIDE 36 — Thiết kế cổng thao tác

## 1. Kiến trúc

```
operation_gate/
├─ policy.py    # ToolPolicy, role validate
├─ gate.py      # OperationGate
├─ errors.py
├─ scenario.py  # chạy kịch bản JSON
└─ cli.py
fixtures/
```

`gate.py` không biết LangChain hay mô hình ngôn ngữ; nó chỉ là state machine nhỏ.

## 2. Trạng thái

```python
@dataclass
class OperationGate:
    policies: dict[str, ToolPolicy]
    required_satisfied: set[str] = field(default_factory=set)
    pending_calls: dict[str, str] = field(default_factory=dict)
    activated_required: set[str] = field(default_factory=set)
```

Giữ ba tập tách biệt. `reset()` không đụng `policies`.

## 3. Luồng quyết định

```
required = role == required_action or name in activated
if not required: return True
if result is None: call path
else: result path
```

Đây là toàn bộ logic cốt lõi. Mọi nhánh lỗi nên ném `GateError` với `code`, không dùng `assert`.

## 4. Call path

- Duyệt `required_args` **theo thứ tự khai báo** để lỗi đầu tiên ổn định.
- Hàm `_missing(value)`:

```python
value is None or (isinstance(value, str) and not value.strip())
```

Không coi `0`/`False` là thiếu.

- Kiểm tra call id sau args: nếu args thiếu và call id thiếu, lỗi args thắng (nguồn làm vậy).
- Kiểm tra trùng call id trước khi ghi.

## 5. Result path

- Chỉ cần `call_id` và `tool_name` khớp; `arguments` có thể `{}`.
- `_typed_result` đúng bảng SPEC.
- Khi `EMPTY_RESULT`, **không** pop pending. Đây là điểm dễ sai: nếu pop, lần gửi lại không thể cứu.
- Khi thành công, pop rồi thêm satisfied. Nếu thêm trước rồi pop lỗi, trạng thái nửa vời.

## 6. Activated tools

`require_tool` dùng khi router xác định request này cần một thao tác mà policy mặc định là optional. Ví dụ: người dùng nói “gửi email xác nhận” → activate `send_email`; mô hình không thể bỏ qua.

Nếu tool đã satisfied trước khi activate, vẫn coi là xong; không bắt gọi lại.

## 7. Bẫy thường gặp

- **Kiểm tra args ở result**: `ToolMessage` không lặp args; sẽ từ chối oan. Đây là lỗi chính nguồn cảnh báo.
- **Dùng `if not tool_result`**: `0`/`False` bị coi là rỗng; sai. Chỉ None là “không có result”, và API dùng default None cho call.
- **Không phân biệt result None với call**: nếu tool thật trả None, không thể biểu diễn; ghi rõ hợp đồng.
- **Không kiểm tra call id**: ghép nhầm kết quả của tool khác.
- **Ghi đè pending khi trùng id**: mất call cũ; bài chặn.
- **`report_unsatisfied` không sort**: output không ổn định.
- **`required_satisfied` chứa tool optional**: `all_required` vẫn đúng nhưng report lạ; chỉ thêm required/activated.
- **Quên reset giữa request**: request sau tưởng đã đặt vé.
- **Coi gate là xác thực nghiệp vụ**: `{"status":"failed"}` vẫn qua; phải kiểm tra nội dung ở tầng sau.

## 8. Gỡ lỗi

- In `pending_calls` và `required_satisfied` sau mỗi bước.
- Test từng mã lỗi độc lập.
- Test result rỗng rồi gửi lại thành công.
- Test optional tool với result rác: không được đổi trạng thái.
- Test `require_tool` unknown.
- Dùng kịch bản JSON để tái lập.

## 9. Kiểm chứng

```bash
cd 36_OPERATION_GATE
python -m operation_gate --policies fixtures/policies.json \
  --scenario fixtures/scenarios/booking.json
```

Test:

```bash
python -m unittest discover -s tests -v
```

Kịch bản mẫu:

```json
{
  "steps": [
    {"op":"validate","tool":"book_flight","args":{"flight_id":"F1"},"call_id":"c1"},
    {"op":"validate","tool":"book_flight","args":{"flight_id":"F1","passenger_id":"P1"},"call_id":"c1"},
    {"op":"validate","tool":"book_flight","args":{},"result":{"status":"ok"},"call_id":"c1"},
    {"op":"status"}
  ]
}
```

Step 1 lỗi; step 2 pending; step 3 satisfied; step 4 báo `all_required=true`.

## 10. Gợi ý

- Viết `_missing` và `_typed_result` là hàm thuần, test riêng.
- Dùng `frozenset` cho required_args sau khi validate không trùng, nhưng giữ **tuple** để báo lỗi theo thứ tự khai báo.
- Tách `on_call`/`on_result` để dễ đọc.
- `GateError` nên có `to_dict()` cho CLI, nhưng không đưa stack trace.
- Không dùng `assert` cho kiểm tra runtime.

## 11. Mở rộng

1. Thêm schema Pydantic cho args.
2. Thêm thời hạn call (timeout) và dọn pending.
3. Thêm nhiều call song song cho cùng tool.
4. Thêm audit log chỉ mã tool/call id, không tham số.
5. Thêm trạng thái “failed” rõ ràng thay vì chỉ result rỗng.
