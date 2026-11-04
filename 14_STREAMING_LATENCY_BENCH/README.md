# 14 — Streaming latency benchmark: TTFT và percentile

## Mục tiêu

Tự viết một benchmark đo độ trễ của API chat streaming tương thích OpenAI, tách phần **đo** khỏi phần **thống kê**, và chạy được với một server giả cục bộ. Báo cáo min/max/mean, p50/p90/p95 cho tổng thời gian, time-to-first-token (TTFT) và thời gian sinh; đồng thời đếm số chunk văn bản.

## Giá trị học được

- Đo streaming khác đo request thường: TTFT chỉ có khi chunk đầu tiên có nội dung.
- `time.perf_counter()` là đồng hồ đúng; `time.time()` có thể nhảy.
- Percentile cần một định nghĩa chính xác; “p90” không tự hiển nhiên.
- SSE có định dạng dòng; chunk đầu có thể chỉ chứa `role`, không có content.
- Tách `summarize(values)` khỏi mạng để test tất định.
- Lỗi một request không nên làm mất toàn bộ kết quả.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–6 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `httpx`, `pytest`.
- Một server giả cục bộ (bạn tự viết trong bài) phát SSE; không cần GPU, API key hay dịch vụ ngoài.

## Nguồn gốc

- Nguồn: `triet4p/llm-serving-lab`, file `benchmarks/latency.py`.
- URL chính xác: <https://github.com/triet4p/llm-serving-lab/blob/main/benchmarks/latency.py>

Hành vi quan sát được trong nguồn:

- Header PEP 723 với `dependencies = ["httpx>=0.27"]`, `requires-python = ">=3.12"`.
- Đọc `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME` từ môi trường; thiếu thì `SystemExit`.
- `send_request` mở `client.stream("POST", url, headers, json=payload)`, đo `time.perf_counter()`.
- Duyệt `response.iter_lines()`; bỏ qua dòng không bắt đầu `data:`; dừng ở `[DONE]`; parse JSON; lấy `choices[0].delta`, ưu tiên `content`, rồi `reasoning`, `reasoning_content`.
- Mỗi chunk có text không rỗng tăng `tokens`; lần đầu ghi `time_to_first_token`.
- `total = perf_counter() - start`; `ttft = first_token_time` nếu có, ngược lại `total`; `generation = max(total - ttft, 0)`.
- `percentile(values, p)` sắp xếp, `index = min(len - 1, int(p / 100 * len))`.
- `summarize` trả `min`, `max`, `mean` (`statistics.fmean`), `p50`, `p90`, `p95`.
- Ghi JSON + CSV vào `benchmarks/results/` với timestamp, trừ khi `--no-save`.
- `--dataset` cho phép lặp qua danh sách request; `--thinking` thêm `chat_template_kwargs`.

## Phạm vi bài tập

Xây package `latency_bench`:

- `parse_sse(lines)` / `send_request(client, ...)`.
- `percentile(values, p)` theo **nearest-rank**, định nghĩa rõ.
- `summarize(values)`.
- CLI `bench` với server giả hoặc bất kỳ endpoint tương thích.
- `fixture_server.py` phát chunk cố định với delay cấu hình.
- Ghi JSON/CSV; lỗi từng request được ghi nhận, không hủy cả mẻ.

Không nằm trong phạm vi: benchmark khoa học, đo GPU, tokenizer thật, so sánh backend, tải đồng thời (bài 15).

## Liên kết

- [SPEC.md](SPEC.md) — công thức percentile, lược đồ kết quả, ví dụ.
- [GUIDE.md](GUIDE.md) — SSE, đo, test tất định.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn yêu cầu biến môi trường trỏ tới backend thật và dừng khi thiếu. Bài tập mặc định trỏ tới `http://127.0.0.1:8765/v1` với key giả, để chạy không cần dịch vụ. Nguồn tính percentile bằng `int(p/100*n)`; bài tập định nghĩa nearest-rank `ceil(p/100*n)-1` và nêu rõ khác biệt. Nguồn để lỗi request lan ra; bài tập ghi nhận lỗi từng request.
