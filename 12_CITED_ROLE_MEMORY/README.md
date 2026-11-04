# 12 — Cited role memory: đọc trước khi quyết định và trích dẫn fact id

## Mục tiêu

Tự viết lớp “đọc bộ nhớ theo vai” cho một agent: trước khi ra quyết định, agent đọc một ngữ cảnh có giới hạn, và đầu ra trích dẫn chính xác các `fact_id` đã dùng (hoặc nói rõ không có fact nào). Bài tập rèn thiết kế Protocol, kiểm soát rò rỉ thời gian (temporal leakage), và sinh chuỗi trích dẫn tất định.

## Giá trị học được

- Bộ nhớ không phải “event log trang trí”: nếu đọc mà không trích dẫn, không chứng minh được nó ảnh hưởng quyết định.
- Phân biệt `None` (bộ nhớ tắt) với “đọc nhưng không tìm thấy fact”.
- Cắt theo ngân sách ký tự phải tất định và không làm hỏng fact.
- Knowledge cutoff: chỉ dùng fact đã biết tại thời điểm quyết định, tránh nhìn trước.
- Protocol giúp thay store thật bằng fake trong test mà không kế thừa.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- Không cần mạng, không cần LLM.

## Nguồn gốc

- Nguồn: `triet4p/mosaic-slm`, file `src/mosaic/agents/role_memory.py`.
- URL chính xác: <https://github.com/triet4p/mosaic-slm/blob/main/src/mosaic/agents/role_memory.py>

Hành vi quan sát được trong nguồn:

- `read_role_memory(tools, role, *, episode_seed, day)` trả `MemoryContextRead | None`.
- Nếu `not tools.memory_enabled`: trả `None`.
- Ngược lại gọi `tools.memory_request_context(role=role, valid_at_day=day, known_as_of_day=memory_knowledge_cutoff(day), stable_prefix=f"{role.value} role decision episode {episode_seed} day {day}")`.
- `memory_citation(read)`:
  - `None` → chuỗi rỗng.
  - Có `fact_ids` khác rỗng → `" Shared memory read {read_id} cited facts: {id1, id2}."`
  - Không có fact → `" Shared memory read {read_id} found no matching shared fact."`
- Nguồn không định nghĩa `memory_knowledge_cutoff`, không giới hạn số fact/ký tự, và không chỉ định thứ tự fact.

## Phạm vi bài tập

Xây module `role_memory`:

- `AgentRole` enum (ít nhất `analyst`, `planner`).
- `MemoryFact`, `MemoryContextRead` bất biến.
- `MemoryStore` Protocol với `enabled` và `request_context(...)`.
- `read_role_memory(store, role, *, episode_seed, day)`.
- `memory_citation(read)`.
- Một `InMemoryStore` tham chiếu, tất định, có cutoff `day - 1`.
- Giới hạn `MAX_FACTS = 5`, `MAX_CHARS = 400`.

Không nằm trong phạm vi: vector search, LLM, cơ sở dữ liệu thật, phân quyền nhiều người dùng, nén ngữ cảnh.

## Liên kết

- [SPEC.md](SPEC.md) — lựa chọn fact, cutoff, định dạng citation, ví dụ.
- [GUIDE.md](GUIDE.md) — Protocol, fake store, kiểm thử thời gian.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn chỉ chuyển tiếp tới `tools.memory_request_context` và định nghĩa định dạng citation. Bài tập **tự định nghĩa** cutoff (`day - 1`), thứ tự fact, giới hạn số lượng/ký tự, và store tham chiếu. Đây là thiết kế của bài tập, không phải hành vi của nguồn.
