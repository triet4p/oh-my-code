# GUIDE 50 — API hoàn thành kiểu streaming

## 1. Ba lớp

```text
HTTP layer      (http.server): đọc body, route, status, header
Protocol layer  (chat.py)    : validate, dựng prompt, sinh token, dựng frame
Model layer     (toy_model)  : vocab, greedy/sampling, lazy load
```

Test được từng lớp:

- Model: gọi thuần, so token.
- Protocol: gọi `handle_chat(payload) -> (status, headers, body_parts)`, so byte.
- HTTP: chạy server thật trên cổng 0, dùng `http.client`.

Nếu bạn viết tất cả trong `do_POST`, mọi test phải qua socket và sẽ chậm, khó debug.

## 2. Cấu trúc gợi ý

```text
src/
├── __main__.py     # argparse: serve --port, hoặc --once để chạy 1 request
├── model.py        # VOCAB, generate(), get_model() + lock + load_count
├── chat.py         # validate, render_prompt, build_stream_frames, build_response
└── server.py       # Handler, route
```

## 3. Thứ tự cài đặt

### Bước 1 — Model thuần

`generate(prompt, max_tokens, temperature, seed) -> list[str]`.

Kiểm tra bằng tay: `prompt = "user: hi\nassistant:"` ⇒ `h = 1800` ⇒ `["hình", ",", "."]` với `max_tokens = 3`. Nếu bạn ra token khác, kiểm tra lại phép `mod 11` và chỉ số `i*7`.

Cẩn thận với `sum(ord(c))` và Unicode: `ord("ì")` là `236`, không phải byte. SPEC dùng codepoint, nên `sum(ord(c) for c in prompt)` là đúng; đừng dùng `len(prompt.encode())`.

### Bước 2 — Ghép nội dung

Viết `render(tokens) -> str` theo luật 1.4. Test riêng: `["hình", ",", "."]` ⇒ `"hình,."`; `["Xin", "chào"]` ⇒ `"Xin chào"`.

### Bước 3 — Frame SSE

Viết `frame(obj) -> str` trả `"data: " + json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n\n"`.

Hai lỗi phổ biến:

- Dùng `indent=2` ⇒ JSON nhiều dòng ⇒ SSE hỏng (mỗi dòng phải bắt đầu bằng `data: `).
- Quên `\n\n` ⇒ client treo vì chưa nhận đủ event.

Xây danh sách frame như **list các chuỗi**, không nối dần vào một biến toàn cục — dễ test và dễ so byte.

### Bước 4 — Handler HTTP

```python
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
```

Với streaming, đặt `Connection: close` và **không** gửi `Content-Length`. Ghi từng frame rồi `self.wfile.flush()`; nếu không flush, client chỉ nhận khi handler kết thúc — mất toàn bộ ý nghĩa streaming.

Với non-stream, tính `body = json.dumps(...).encode()`, gửi `Content-Length` chính xác.

Đọc body: `int(self.headers.get("Content-Length", "0"))`, đọc đúng số byte, `json.loads`. Đừng đọc `rfile` đến EOF (sẽ treo với keep-alive).

### Bước 5 — Thứ tự validate

Theo SPEC 5. Viết `validate(payload) -> (params | Error)`, không rải `if` trong handler.

Một điểm tinh tế: `messages` sai kiểu (ví dụ string) phải ra `missing_messages` hay `invalid_messages`? SPEC chọn: thiếu/rỗng/không phải list ⇒ `missing_messages`; list nhưng phần tử sai ⇒ `invalid_messages`. Test cả hai.

### Bước 6 — Lazy load

```python
_model = None
_lock = threading.Lock()
_loads = 0

def get_model():
    global _model, _loads
    if _model is None:
        with _lock:
            if _model is None:
                _model = ToyModel()
                _loads += 1
    return _model
```

Double-checked locking trong Python không cần thiết về mặt bộ nhớ, nhưng mẫu này vẫn đúng và dễ đọc. Test 5 request đồng thời ⇒ `loads == 1`.

## 4. Cạm bẫy

- **Không flush**: chunk cuối mới tới client.
- **Thiếu dòng trống giữa frame**: client gộp frame, parse lỗi.
- **`[DONE]` có JSON**: phải là chuỗi trần `data: [DONE]`.
- **`Content-Length` trên stream**: nếu bạn tính trước độ dài, phải biết toàn bộ body; hoặc bỏ hẳn. Đừng gửi sai.
- **`created` lấy `time.time()`**: phá tính tất định; SPEC cấm.
- **`id` dùng bộ đếm toàn cục**: kết quả phụ thuộc thứ tự request; SPEC dùng `h`.
- **Rò prompt**: nếu bạn "stream" cả prompt trước khi sinh, test 8.3 bắt. Đây chính là lý do `TextIteratorStreamer(skip_prompt=True)` tồn tại.
- **`allow_reuse_address` và cổng 0**: khi test, đọc `server.server_address[1]` để lấy cổng thật.
- **ThreadingHTTPServer không daemon**: nhớ `server.shutdown()` trong `tearDown`, nếu không test treo.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `model_greedy` | `["hình", ",", "."]`, `h = 1800` |
| `render_punct` | `"hình,."` |
| `frame_compact` | một frame đúng chuỗi, không `indent` |
| `stream_bytes` | body khớp `fixtures/expected_stream.txt` |
| `nonstream_json` | đúng object, `usage` 3/3/6 |
| `errors` | 10 dòng bảng lỗi |
| `lazy_load` | 5 request đồng thời ⇒ `loads == 1` |
| `no_prompt_leak` | nối delta không chứa `"assistant:"` |
| `sampling_deterministic` | cùng seed ⇒ cùng body |
| `method_not_allowed` | GET ⇒ 405 |

## 6. Kiểm chứng độc lập

Chạy server:

```bash
python -m src serve --port 8000
```

Gọi thử (dùng Python để không phụ thuộc curl):

```bash
python -c "import http.client,json; c=http.client.HTTPConnection('127.0.0.1',8000); c.request('POST','/v1/chat/completions',json.dumps({'model':'toy-1','messages':[{'role':'user','content':'hi'}],'stream':True,'max_tokens':3}),{'Content-Type':'application/json'}); r=c.getresponse(); print(r.status); print(r.read().decode())"
```

So với mục 3 của SPEC. So byte với fixture:

```bash
python -c "import http.client,json,pathlib; body=pathlib.Path('fixtures/request_stream.json').read_text(); c=http.client.HTTPConnection('127.0.0.1',8000); c.request('POST','/v1/chat/completions',body,{'Content-Type':'application/json'}); got=c.getresponse().read().decode(); exp=pathlib.Path('fixtures/expected_stream.txt').read_text(); print('match', got==exp)"
```

Phải in `match True`. Kiểm tra non-stream:

```bash
python -c "import http.client,json,pathlib; body=pathlib.Path('fixtures/request_once.json').read_text(); c=http.client.HTTPConnection('127.0.0.1',8000); c.request('POST','/v1/chat/completions',body,{'Content-Type':'application/json'}); r=c.getresponse(); print(r.status, json.loads(r.read()))"
```

## 7. Gợi ý

- Viết `handle_chat(payload) -> Result` trả `(status, headers, frames)`; handler HTTP chỉ ghi ra. Toàn bộ test logic chạy không cần socket.
- Viết `assert_sse(body)` trong test: tách theo `"\n\n"`, kiểm tra mỗi phần bắt đầu `"data: "`, phần cuối là `"[DONE]"`.
- Để tạo `expected_stream.txt`, **đừng** chép từ output của chính bạn rồi coi là đúng — hãy dựng từ SPEC bằng tay (hoặc bằng một script nhỏ dựa trên công thức), rồi so.
- Nếu muốn thấy hành vi client ngắt, dùng `curl` với `--max-time 0.2` và kiểm tra server không crash.

## 8. Mở rộng

- **`stream_options.include_usage`**: thêm frame `usage` trước `[DONE]`; cập nhật golden.
- **Nhiều lựa chọn**: `n = 2`, trả hai choice song song trong cùng frame; SSE phải giữ `index`.
- **`stop` sequences**: dừng sinh khi gặp chuỗi dừng; test với token ghép thành chuỗi dừng.
- **Timeout**: đóng kết nối nếu sinh quá X giây; dùng đồng hồ giả để test.
- **So sánh giao thức**: chạy một client OpenAI thật (nếu có sẵn offline) trỏ vào server để xem nó chấp nhận đến đâu — ghi lại khác biệt.
