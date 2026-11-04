# SPEC 50 — API hoàn thành kiểu streaming

## 1. Giao thức

### 1.1 Request

```json
{
  "model": "toy-1",
  "messages": [{"role": "user", "content": "hi"}],
  "stream": true,
  "max_tokens": 3,
  "temperature": 0
}
```

| Khóa | Mặc định | Ràng buộc |
|---|---|---|
| `model` | bắt buộc | Chỉ `"toy-1"`; khác ⇒ 404 |
| `messages` | bắt buộc | list không rỗng; mỗi phần tử có `role` (str) và `content` (str) |
| `stream` | `false` | bool |
| `max_tokens` | `16` | int trong `[1, 256]` |
| `temperature` | `0` | số trong `[0, 2]`; `> 0` ⇒ sampling |
| `seed` | `0` | int `0..2^32-1`; chỉ dùng khi sampling |

### 1.2 Dựng prompt

```text
prompt = "".join(f"{m['role']}: {m['content']}\n" for m in messages) + "assistant:"
```

Với request 1.1: `prompt = "user: hi\nassistant:"`.

Giới hạn: `len(prompt) <= 2000`; vượt ⇒ `context_length_exceeded`.

### 1.3 Sinh token

`h = sum(ord(c) for c in prompt) mod 9973`

`VOCAB = ["Xin", "chào", "bạn", ",", "tôi", "là", "mô", "hình", "đồ", "chơi", "."]` (11 phần tử).

**Greedy (`temperature == 0`)**:

```text
token[i] = VOCAB[(h + i * 7) mod 11]   với i = 0..max_tokens-1
```

**Sampling (`temperature > 0`)**: LCG 32-bit khởi tạo `state = seed`, mỗi token:

```text
state = (1664525*state + 1013904223) mod 2^32
token[i] = VOCAB[floor((state / 2^32) * 11)]
```

Mô hình đồ chơi cố ý bỏ qua nội dung câu hỏi; mục đích là kiểm chứng giao thức, không phải chất lượng.

### 1.4 Ghép nội dung

Token đầu tiên đứng một mình. Các token sau: nếu token thuộc `{",", ".", "!", "?"}` thì nối trực tiếp, ngược lại thêm một dấu cách rồi nối.

Với 1.1 (`h = 1800`): `token = ["hình", ",", "."]` ⇒ `content = "hình,."`.

## 2. id và created

- `id = "chatcmpl-" + str(h)` — với 1.1 là `"chatcmpl-1800"`. Không dùng bộ đếm toàn cục để kết quả không phụ thuộc thứ tự request.
- `created = 0` cố định.

## 3. Nhánh streaming

Header phản hồi:

```text
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
Connection: close
```

Mỗi frame là `data: <json>\n\n` (đúng hai ký tự xuống dòng sau JSON). JSON in **compact**: `separators=(",", ":")`, `ensure_ascii=False`, thứ tự khóa cố định như dưới.

Thứ tự frame cho 1.1:

```text
data: {"id":"chatcmpl-1800","object":"chat.completion.chunk","created":0,"model":"toy-1","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-1800","object":"chat.completion.chunk","created":0,"model":"toy-1","choices":[{"index":0,"delta":{"content":"hình"},"finish_reason":null}]}

data: {"id":"chatcmpl-1800","object":"chat.completion.chunk","created":0,"model":"toy-1","choices":[{"index":0,"delta":{"content":","},"finish_reason":null}]}

data: {"id":"chatcmpl-1800","object":"chat.completion.chunk","created":0,"model":"toy-1","choices":[{"index":0,"delta":{"content":"."},"finish_reason":null}]}

data: {"id":"chatcmpl-1800","object":"chat.completion.chunk","created":0,"model":"toy-1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

Bắt buộc:

- Frame 1 là `role` và **không** có `content`.
- Không frame nào được chứa prompt hoặc tiền tố `"assistant:"`.
- Frame cuối trước `[DONE]` có `"delta": {}` và `"finish_reason": "stop"`.
- `[DONE]` là dòng cuối cùng, theo sau là một dòng trống.

## 4. Nhánh không streaming

`status 200`, `Content-Type: application/json; charset=utf-8`.

```json
{
  "id": "chatcmpl-1800",
  "object": "chat.completion",
  "created": 0,
  "model": "toy-1",
  "choices": [
    {"index": 0, "message": {"role": "assistant", "content": "hình,."}, "finish_reason": "stop"}
  ],
  "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6}
}
```

`prompt_tokens = len(prompt.split())`; `completion_tokens = số token đã sinh`; `total = tổng`.

## 5. Lỗi

Mọi lỗi trả JSON:

```json
{"error": {"message": "<mô tả>", "type": "<loại>", "param": null, "code": "<mã>"}}
```

| Tình huống | HTTP | `type` | `code` |
|---|---|---|---|
| Body không phải JSON | 400 | `invalid_request_error` | `invalid_json` |
| Thiếu/rỗng `messages` | 400 | `invalid_request_error` | `missing_messages` |
| Phần tử message thiếu `role`/`content` | 400 | `invalid_request_error` | `invalid_messages` |
| `model` khác `toy-1` | 404 | `invalid_request_error` | `model_not_found` |
| Prompt > 2000 ký tự | 400 | `invalid_request_error` | `context_length_exceeded` |
| `max_tokens` ngoài miền | 400 | `invalid_request_error` | `invalid_max_tokens` |
| `temperature` ngoài miền | 400 | `invalid_request_error` | `invalid_temperature` |
| `stream` không phải bool | 400 | `invalid_request_error` | `invalid_stream` |
| Đường dẫn khác | 404 | `invalid_request_error` | `not_found` |
| Phương thức khác | 405 | `invalid_request_error` | `method_not_allowed` |

Thứ tự kiểm tra: JSON → `messages` → `model` → `stream` → `max_tokens` → `temperature` → độ dài prompt.

## 6. Nạp mô hình lười

- `get_model()` chỉ nạp lần đầu, dưới một `threading.Lock`.
- `GET /healthz` trả `{"status": "ok", "loads": <int>, "requests": <int>}`.
- 5 request đồng thời ngay sau khởi động ⇒ `loads == 1`.

## 7. Ví dụ byte-level

Với request 1.1 và `stream: true`, toàn bộ body phải bằng đúng chuỗi ở mục 3 (so từng byte, kể cả dòng trống cuối).

Với `stream: false`, body phải parse thành đúng object ở mục 4.

### 7.1 Sampling tất định

`temperature = 0.7`, `seed = 1`, `max_tokens = 2`:

```text
state1 = (1664525*1 + 1013904223) mod 2^32 = 1015568748
u1 = 1015568748 / 4294967296 ≈ 0.2365…  ⇒ idx = floor(0.2365*11) = 2 ⇒ "bạn"
```

Giá trị `u1` phải được tính trong test bằng số nguyên (`state1 * 11 // 2^32 = 2`), không dùng float — tránh sai số.

Tiếp tục cho token thứ hai bằng cùng công thức; test khẳng định chuỗi kết quả ổn định qua hai lần gọi.

## 8. Tiêu chí chấp nhận

1. Body streaming của 1.1 khớp **từng byte** với mục 3.
2. Body non-stream khớp mục 4 (`usage` đúng 3/3/6).
3. Không frame nào chứa `"assistant:"` và nội dung ghép lại đúng `"hình,."`.
4. Frame 1 có `role` và không có `content`; frame cuối có `delta == {}`.
5. Bảng lỗi: mỗi dòng một test, khẳng định HTTP status **và** `code`.
6. `healthz` sau 5 request đồng thời: `loads == 1`, `requests == 5`.
7. `max_tokens = 256` chạy được; `257` ⇒ lỗi.
8. Cùng request (kể cả sampling với cùng seed) cho cùng body.
9. `GET /v1/chat/completions` ⇒ 405.

## 9. Non-goals

- Không auth, rate limit, CORS, TLS, timeout phía server.
- Không `tools`, `functions`, logit bias, beam search.
- Không mô hình thật, không tokenizer thật, không GPU.
- Không `usage` trong frame streaming (đó là `stream_options.include_usage`, ngoài phạm vi).
