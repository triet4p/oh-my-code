# 54 — Phong bì an toàn cho agent

## Mục tiêu

Dựng lớp **phong bì ứng dụng** quanh một agent: chặn đầu vào quá dài, đếm số bước, chuyển đổi công cụ async↔sync an toàn, và chuẩn hoá thông điệp khi xuất ra client mà không làm hỏng bản ghi nội bộ.

1. `check_input(text)` với giới hạn **100 000 ký tự** (codepoint), biên rõ ràng.
2. `StepBudget(max_steps=12)` — dùng hết 12 bước được, bước 13 ném lỗi.
3. `run_sync(coro)` chạy được cả trong và ngoài event loop, không lỗi "asyncio.run() cannot be called from a running event loop".
4. `make_sync_tool(async_fn)` bọc công cụ async thành hàm sync.
5. `safe_messages(messages)` chuẩn hoá content-block khi xuất, giữ nguyên thông điệp gốc.

## Giá trị

- Đây là những dòng code production thường bị viết vội: giới hạn độ dài, đếm bước, và cầu async/sync. Mỗi thứ đều có lỗi biên nếu không được test ở đúng ngưỡng.
- "Chuẩn hoá khi xuất, giữ nguyên khi lưu" là mẫu quan trọng: nếu bạn chuẩn hoá tại chỗ, bạn mất thông tin cho các bước sau; nếu không chuẩn hoá khi xuất, client nhận cấu trúc nội bộ.
- Bạn học cách viết một lớp `envelope` **không phụ thuộc framework**: chỉ hàm thuần và một cầu async nhỏ.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`asyncio`, `concurrent.futures`, `threading`) |
| Độ khó | Trung bình–Khó |
| Điều kiện | `async`/`await`, event loop, `ThreadPoolExecutor`, `deepcopy` |
| Runtime | Không mạng, không GPU, không framework agent |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/ecommerce-agent-databricks` (nhánh `main`, repo đã archived 2026-10-23)
- File nguồn: <https://github.com/triet4p/ecommerce-agent-databricks/blob/main/agent_core/orchestrator.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Hằng số `MAX_REQUEST_INPUT_CHARACTERS = 100_000`, `MAX_AGENT_GRAPH_STEPS = 12`, kèm chú thích: *"Application-level safety envelope used when an endpoint cannot enable AI Gateway rate or token controls"*.
  - `_await_tool_invocation` tránh lồng `asyncio.run` bằng `ThreadPoolExecutor(max_workers=1)` khi loop đã sở hữu.
  - `_make_sync_tool_adapters` bọc công cụ chỉ có async thành `StructuredTool.from_function`.
  - `_responses_safe_messages` chuẩn hoá danh sách content-block khi serialize ra client nhưng giữ nguyên graph message.
- Giới hạn bằng chứng: đọc 120 dòng đầu; không quan sát được hành vi khi vượt giới hạn, thông điệp lỗi, hay chi tiết định dạng block.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: hai hằng số 100 000/12; ý tưởng phong bì ở tầng ứng dụng; cầu async/sync dùng thread pool một worker; adapter sync cho tool async; chuẩn hoá khi xuất nhưng giữ bản gốc.

Phần **do bài tập định nghĩa**:

- Đếm "ký tự" theo codepoint Python (`len(str)`), không theo byte — nêu rõ vì emoji khác nhau.
- Tên lỗi, mã lỗi, cách đếm bước (bước 13 mới lỗi).
- Định dạng content-block và quy tắc lọc (`type == "text"`), cách xử lý `str`.
- Hành vi khi coroutine ném ngoại lệ (truyền nguyên, không nuốt).
- CLI và fixture.

Nguồn **không** bao gồm: LangChain, Databricks, mô hình, hay endpoint thật.

## Phạm vi

Trong phạm vi:

- `src/envelope.py` với bốn API ở mục Mục tiêu.
- Test: biên 100 000/100 001, bước 12/13, gọi `run_sync` trong `async def`, tool async bọc sync, chuẩn hoá egress.
- CLI: `python -m src check --input fixtures/input_big.txt`.

Ngoài phạm vi:

- Không gọi mạng, không SDK, không kiểm soát tần suất thật.
- Không đo token; không cắt ngữ cảnh theo token.
- Không xử lý streaming.

## Cảnh báo production

- 100 000 **ký tự** không phải 100 000 token; một ký tự có thể tốn vài token. Đừng dùng con số này để tính chi phí.
- `run_sync` bên trong event loop sẽ chặn loop trong lúc chờ thread; đó là lựa chọn có ý thức cho CLI/notebook, không dùng trong server phục vụ nhiều request.
- Chuẩn hoá egress làm mất khối `internal`/`image`; nếu client cần chúng, phải có đường riêng, không nới lỏng hàm này.
- Giới hạn độ dài không thay thế giới hạn tần suất hay ngân sách token; chúng bổ sung nhau.

## Fixture offline

- `fixtures/input_boundary.json` — ba chuỗi: 99 999, 100 000, 100 001 ký tự.
- `fixtures/messages_internal.json` — thông điệp có block `text` và block nội bộ.
- `fixtures/tools.json` — mô tả tool async giả để bọc.
- Không có URL ngoài; không cần khoá API.

## Liên kết

- [SPEC.md](SPEC.md) — ngưỡng, lỗi, ví dụ số, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế cầu async, bẫy đo lường, cách kiểm chứng.
