# SPEC 55 — Bộ thực thi workflow có ngân sách

## 1. Trạng thái

```text
READY → GENERATING → DISPATCHING → VERIFYING → COMPLETED
                 ↕            ↘
             CLARIFYING      INCOMPLETE
                 ↘
              REFUSED
```

| Trạng thái | Vào khi | Ra khi |
|---|---|---|
| `READY` | Trước bước đầu | Bước đầu tiên |
| `GENERATING` | Bắt đầu, hoặc sau `CLARIFYING`, hoặc sau `VERIFYING` còn bước | Gặp bước `tool`, `clarify`, `refuse`, hoặc hết script |
| `DISPATCHING` | Ngay sau khi chọn bước `tool` | Sang `VERIFYING` |
| `VERIFYING` | Bước kế là `verify` | `COMPLETED` hoặc quay `GENERATING` |
| `CLARIFYING` | Bước `clarify` | Bước `generate` kế tiếp |
| `COMPLETED` | Hết script với mọi mutation đã xác minh | — |
| `REFUSED` | Bước `refuse` | — |
| `INCOMPLETE` | Bất kỳ lý do dừng nào | — |

Bảng chuyển hợp lệ (mọi cặp khác ⇒ `IllegalTransition(from, to)`):

```text
(READY, GENERATING)
(GENERATING, DISPATCHING)
(GENERATING, CLARIFYING)
(GENERATING, REFUSED)
(GENERATING, COMPLETED)
(DISPATCHING, VERIFYING)
(VERIFYING, GENERATING)
(VERIFYING, COMPLETED)
(CLARIFYING, GENERATING)
(_, INCOMPLETE)          # từ mọi trạng thái chưa kết thúc
```

## 2. Giới hạn

```text
max_turns = 12
max_tool_calls = 24
max_context_characters = 160_000
max_wall_clock_millis = 300_000
max_repeated_identical_calls = 3
max_capture_observations = 4
```

## 3. Kịch bản (fixture)

```json
{
  "steps": [
    {"kind": "generate", "text": "hello"},
    {"kind": "tool", "tool": "charge", "args": {"order": "A1", "amount": 100}, "mutation": true},
    {"kind": "verify", "ok": true},
    {"kind": "tool", "tool": "charge", "args": {"order": "A1", "amount": 100}, "mutation": true}
  ],
  "clock_ticks_ms": 1000
}
```

| `kind` | Trường | Tác dụng |
|---|---|---|
| `generate` | `text` | `turns += 1`; `context_chars += len(text)`; trạng thái `GENERATING` |
| `tool` | `tool`, `args`, `mutation` | `tool_calls += 1`; có thể thực thi hoặc phát lại |
| `verify` | `ok` | Xác nhận mutation gần nhất; `ok == false` ⇒ `EFFECT_NOT_VERIFIED` |
| `clarify` | `text` | `context_chars += len(text)`; trạng thái `CLARIFYING` |
| `refuse` | `reason` | Trạng thái `REFUSED`; dừng |

## 4. Thứ tự kiểm tra mỗi bước

Trước khi thực thi bước `i`:

```text
1. elapsed = clock() - start_ms
   nếu elapsed >= max_wall_clock_millis: dừng TIME_BUDGET
2. nếu bước là "generate" và turns + 1 > max_turns: dừng TURN_BUDGET
3. nếu bước là "tool" và tool_calls + 1 > max_tool_calls: dừng TOOL_CALL_BUDGET
4. nếu bước thêm văn bản (generate/clarify) và context_chars + len(text) > max_context_characters:
       dừng CONTEXT_BUDGET
5. nếu bước là "tool": key = operation_key(tool, args)
       occurrences[key] += 1
       nếu occurrences[key] > max_repeated_identical_calls: dừng LOOP_DETECTED   # chưa dispatch
6. kiểm tra chuyển trạng thái hợp lệ; sai ⇒ IllegalTransition
7. thực thi bước
```

Mọi lý do dừng chuyển trạng thái sang `INCOMPLETE` (trừ `refuse` → `REFUSED`), ghi `stop_reason`, và **không** thực thi bước gây dừng.

## 5. Khóa thao tác và sổ

```text
operation_key(tool, args) = sha256_hex(canonical_json({"tool": tool, "args": args}))
canonical_json: sort_keys=True, separators=(",", ":"), ensure_ascii=False
```

Sổ `ledger: dict[key, {"result": ..., "executed": True}]`.

- Lần đầu gặp key: gọi hàm công cụ, `executions += 1`, lưu kết quả.
- Lần sau: trả kết quả đã lưu, `replays += 1`, **không** gọi hàm.
- `1` và `"1"` là hai khóa khác nhau (kiểu khác nhau) — đúng ý đồ an toàn.

`occurrences` đếm **mọi** lần dispatch (kể cả replay) cho cùng key, trong phạm vi một lượt chạy.

## 6. Xác minh hiệu ứng

- Một bước `tool` với `mutation: true` đặt cờ `pending_mutation = key`.
- Bước `verify` kế tiếp:
  - `ok: true` ⇒ xoá cờ, `verified_mutations += 1`.
  - `ok: false` ⇒ dừng `EFFECT_NOT_VERIFIED`.
- Nếu bước kế không phải `verify`, hoặc script kết thúc khi cờ còn bật ⇒ dừng `EFFECT_NOT_VERIFIED`.
- Mutation phát lại (replay) **không** đặt lại cờ nếu key đã được xác minh trước đó.

## 7. Kết quả

```json
{
  "context_chars": 5,
  "dropped_observations": 0,
  "elapsed_ms": 3000,
  "executions": 1,
  "observations": [{"key": "…64 hex…", "result": {"ok": true}}],
  "replays": 2,
  "state": "INCOMPLETE",
  "stop_reason": "LOOP_DETECTED",
  "tool_calls": 3,
  "turns": 1,
  "verified_mutations": 1
}
```

- `observations` giữ tối đa `max_capture_observations` kết quả **mới nhất**, theo thứ tự thời gian; phần dư tăng `dropped_observations`.
- `elapsed_ms` = giá trị đồng hồ tiêm tại lần kiểm tra cuối.
- `tool_calls` đếm số lần dispatch **đã qua** bước kiểm tra 5 (không tính lần bị chặn).
- `state` luôn là một trong tám giá trị.

## 8. Ví dụ cụ thể

### 8.1 Vòng lặp

Script mục 3 (4 bước) với `max_repeated_identical_calls = 3`:

| Bước | occurrences | Hành động | executions | replays |
|---|---|---|---|---|
| 0 `generate` | — | turns 1, context 5 | 0 | 0 |
| 1 `tool` | 1 | thực thi | 1 | 0 |
| 2 `verify ok` | — | xác minh | 1 | 0 |
| 3 `tool` | 2 | phát lại | 1 | 1 |

Nếu thêm hai bước giống hệt nữa (tổng 6 bước): bước thứ 5 là lần phát lại thứ hai (`occurrences = 3`, vẫn hợp lệ); bước thứ 6 có `occurrences = 4 > 3` ⇒ dừng **trước** dispatch với `LOOP_DETECTED`, `tool_calls = 3`, `replays = 2`, `state = INCOMPLETE`.

### 8.2 Ngân sách ngữ cảnh

Hai bước `generate` với `text` dài 100 000 và 60 001 ký tự:

- Bước 1: `0 + 100 000 = 100 000 <= 160 000` ⇒ nhận; `context_chars = 100 000`.
- Bước 2: `100 000 + 60 001 = 160 001 > 160 000` ⇒ dừng `CONTEXT_BUDGET`; `context_chars` vẫn `100 000`.

### 8.3 Ngân sách thời gian

`clock_ticks_ms = 100_000`, mỗi bước đồng hồ tăng 100 000 ms.
Sau 3 bước: `elapsed = 300 000`. Trước bước 4: `elapsed >= 300 000` ⇒ dừng `TIME_BUDGET` với `elapsed_ms = 300000`, số bước đã chạy là 3.

### 8.4 Ngân sách lượt và công cụ

13 bước `generate` ⇒ 12 bước đầu chạy, bước 13 dừng `TURN_BUDGET` với `turns = 12`.
25 bước `tool` khác nhau ⇒ 24 bước đầu chạy, bước 25 dừng `TOOL_CALL_BUDGET` với `tool_calls = 24`.

### 8.5 Hiệu ứng chưa xác minh

Script: `[generate, tool(mutation), generate]`.
Bước 2 thực thi mutation; bước 3 không phải `verify` ⇒ dừng `EFFECT_NOT_VERIFIED` **trước** khi xử lý bước 3; `turns = 1`, `executions = 1`.

`verify ok = false` cũng cho cùng lý do dừng, nhưng `turns`/`tool_calls` đã tính bước verify là bước đã xử lý (verify không tiêu ngân sách).

## 9. Tiêu chí chấp nhận

1. 8.1, 8.2, 8.3, 8.4, 8.5 cho đúng các bộ đếm và `stop_reason`.
2. `executions == 1` trong 8.1 dù lời gọi lặp 3 lần — bằng chứng không có hiệu ứng thứ hai.
3. Bảng chuyển: `verify` khi đang `GENERATING` (không có dispatch trước) ⇒ `IllegalTransition`.
4. `state ∈ {READY, GENERATING, DISPATCHING, VERIFYING, COMPLETED, CLARIFYING, REFUSED, INCOMPLETE}` với mọi fixture.
5. `clock_ticks_ms = 0` ⇒ không bao giờ chạm `TIME_BUDGET` (dùng đồng hồ giả đứng yên).
6. `observations` ≤ 4 và `dropped_observations` khớp số kết quả bị bỏ.
7. Cùng fixture + cùng đồng hồ ⇒ cùng output byte-identical.
8. `python -m src run --fixture fixtures/script_loop.json` in JSON có `"executions": 1`.
9. Không có `sleep`/`time.time` trong mã nguồn (đồng hồ tiêm).

## 10. Non-goals

- Không gọi mô hình, không HTTP, không streaming.
- Không lưu bền sổ thao tác; không huỷ giữa chừng.
- Không kiểm soát tần suất/chi phí token.
- Không mô phỏng "capture observations" phức tạp của nguồn.
