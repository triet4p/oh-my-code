# 50 — API hoàn thành kiểu streaming

## Mục tiêu

Cài một **tập con tương thích OpenAI** cho `POST /v1/chat/completions`, có nhánh streaming SSE và nhánh trả một lần, với mô hình đồ chơi tất định chạy hoàn toàn cục bộ.

1. Nạp mô hình **lười** (lazy), đếm số lần nạp, an toàn khi nhiều request đồng thời.
2. Dựng prompt kiểu chat template rồi sinh token theo luật tất định.
3. Phát SSE đúng khung: chunk đầu có `role`, các chunk sau có `content`, chunk cuối `finish_reason`, rồi `data: [DONE]`.
4. Trả JSON một lần khi `stream: false`, kèm `usage`.
5. Trả lỗi theo phong bì `{"error": {...}}` với mã HTTP chuẩn.

## Giá trị

- Giao thức streaming là nơi dễ sai lệch "gần đúng": thiếu dòng trống giữa các frame, `[DONE]` không có, hoặc client nhận lại prompt. Bài tập ghim từng byte.
- Lazy loading + khoá là mẫu production nhỏ: nạp hai lần vì race condition là lỗi tốn kém thật.
- Bạn học cách kiểm thử server HTTP **không** cần mạng ngoài: gọi handler trực tiếp và chạy một server thật trên cổng 0.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`http.server`, `json`, `threading`, `hashlib`) |
| Độ khó | Trung bình |
| Điều kiện | HTTP cơ bản, SSE, `ThreadingHTTPServer`, hiểu `Content-Type`/`Transfer-Encoding` |
| Runtime | Không mạng ngoài, không GPU, không `transformers` |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/llm-serving-lab` (nhánh `main`, repo đã archived 2026-10-23)
- File nguồn: <https://github.com/triet4p/llm-serving-lab/blob/main/servers/baseline-fastapi/app.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3.5-2B")` và `load_model()` được gọi lười.
  - `_prepare_inputs` dùng `tokenizer.apply_chat_template(..., add_generation_prompt=True)`.
  - Endpoint `POST /v1/chat/completions`, phân nhánh `stream` → `_stream_chat_completions` dùng `TextIteratorStreamer(skip_prompt=True)`.
  - `_generation_kwargs` đặt `do_sample = temperature > 0`.
- Giới hạn bằng chứng: đọc 90 dòng đầu; không quan sát được phần xử lý lỗi, đo usage, hay huỷ request của nguồn.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: biến môi trường chọn model; nạp lười; chat template có `add_generation_prompt`; endpoint và nhánh `stream`; streamer bỏ phần prompt; `do_sample` phụ thuộc `temperature > 0`.

Phần **do bài tập định nghĩa**:

- Mô hình đồ chơi tất định thay cho HF (vocab cố định, token theo băm prompt).
- Khung SSE chính xác, `created = 0` để tất định, `id` theo bộ đếm.
- Phong bì lỗi và mã lỗi; giới hạn `max_tokens`, độ dài ngữ cảnh.
- `seed` trong request cho nhánh sampling.
- Test gọi handler trực tiếp và server thật trên cổng 0.

Nguồn **không** bao gồm: `transformers`, trọng số thật, GPU, hay đo hiệu năng.

## Phạm vi

Trong phạm vi:

- Hai route: `POST /v1/chat/completions` và `GET /healthz`.
- Sinh tối đa 256 token; vocab 11 token; prompt ≤ 2000 ký tự.
- Streaming và non-streaming trên cùng một hàm sinh.
- Test: khung SSE, usage, lỗi, lazy load một lần, không rò prompt.

Ngoài phạm vi:

- Không auth, rate limit, CORS, TLS.
- Không `tools`/`functions`, không logit bias, không beam search.
- Không mô hình thật, không đảm bảo chất lượng câu trả lời.

## Cảnh báo production

- Server này **không** dùng được cho production: thiếu auth, giới hạn tần suất, timeout, backpressure, và không chịu tải. Chỉ dùng để học giao thức.
- `created: 0` là quyết định để test tất định; API thật dùng timestamp Unix. Đừng copy sang dịch vụ thật.
- Mô hình đồ chơi không có ngữ nghĩa; đừng đánh giá chất lượng câu trả lời.
- Streamer thật phải dừng sinh khi client ngắt; ở đây chỉ bắt `BrokenPipeError` để dừng vòng lặp — chưa giải phóng tài nguyên mô hình.

## Fixture offline

- `fixtures/request_stream.json` — request mẫu `stream: true`.
- `fixtures/request_once.json` — request mẫu `stream: false`.
- `fixtures/request_bad.json` — JSON hỏng, thiếu `messages`, model lạ.
- `fixtures/expected_stream.txt` — khung SSE kỳ vọng cho request ở 1.1 của SPEC.
- Không có URL ngoài, không biến môi trường bí mật.

## Liên kết

- [SPEC.md](SPEC.md) — giao thức, khung SSE, ví dụ byte-level, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế handler, streamer, bẫy SSE, cách kiểm chứng.
