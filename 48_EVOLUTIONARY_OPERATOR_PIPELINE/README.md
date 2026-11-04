# 48 — Pipeline toán tử tiến hoá gọi mô hình

## Mục tiêu

Cài khung **toán tử tiến hoá** theo mẫu template-method: mỗi toán tử dựng prompt, gọi một `ModelProvider`, và phân tích JSON trả về; kèm chọn lọc, elitism, và **chính sách sửa lỗi JSON** — tất cả chạy offline bằng provider kịch bản.

1. Định nghĩa `LLMBaseOperator` với bốn móc `_build_prompt`, `_build_config`, `_process_json_response`, `__call__`.
2. Cài năm toán tử: init, crossover, mutation, self-evolution, collective-reflection.
3. Chọn lọc không hoàn lại và thay thế elitism top-k.
4. Provider kịch bản đọc phản hồi từ fixture, có kiểm tra schema và một lần sửa lỗi.
5. Không có lời gọi mạng, không phụ thuộc nhà cung cấp trả phí.

## Giá trị

- Đây là bài tập về **hợp đồng với mô hình**: prompt vào, JSON ra, và mọi thứ phải kiểm tra được khi mô hình trả rác.
- Template-method giúp năm toán tử chia sẻ một đường ống (dựng → gọi → parse → xác thực) mà không lặp code.
- Bạn học cách kiểm thử hệ thống "có mô hình" mà không cần mô hình: thay provider, giữ nguyên phần còn lại.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Khó |
| Điều kiện | Kế thừa, `json`, xác thực lược đồ, thiết kế lỗi có thể thử lại |
| Runtime | Không mạng, không API key, không GPU |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/SeEvoDJSSP` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/SeEvoDJSSP/blob/main/se_evo.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Template method `class LLMBaseOperator(Operator)` với `_build_prompt` / `_build_config` / `_process_json_response` / `__call__`.
  - Trong `__call__`: `response = self.llm_model.get_response(prompt); json_repsonse = self.llm_model.extract_response(response)`.
  - Các toán tử: `LLMInitOperator`, `LLMCrossoverOperator` (nhận `p1`, `p2`, `reflection`), `SelfEvoOperator` (so sánh trước/sau reflection), `CollectiveRefOperator`, `LLMMutationOperator`.
  - Chọn lọc: `RandomSelectOperator` (`random.sample(population.inds, k=sub_size)`) và `TopKElitismReplaceOperator(problem, k=2)`.
  - Nguồn dùng OpenRouter / Google AI Studio làm backend.
- Giới hạn bằng chứng: nguồn 22.074 B, đọc 300 dòng đầu; không quan sát được toàn bộ prompt template hay chi tiết `evaluate.py`.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: cấu trúc template-method bốn móc; tên và tham số của năm toán tử; hai toán tử chọn lọc; việc mô hình trả JSON và cần `extract_response`; backend là dịch vụ ngoài.

Phần **do bài tập định nghĩa**:

- Thay backend bằng `ModelProvider` cục bộ (`ScriptedProvider` + `EchoProvider`).
- Lược đồ JSON cho từng toán tử, quy tắc sửa lỗi (một lần thử lại), và cách ghi nhận thất bại.
- Không gửi prompt/response thô vào log; chỉ ghi băm.
- Định nghĩa "cá thể", "quần thể", "fitness" bằng số nguyên nhỏ để tất định.
- Định dạng fixture/output, tên lỗi.

Nguồn **không** bao gồm: kết nối mạng, chi phí token, hay đánh giá trên DJSSP thật.

## Phạm vi

Trong phạm vi:

- Quần thể `list[Individual]` với `genes: list[int]`, `fitness: int`.
- Năm toán tử chạy trên provider kịch bản; hai toán tử chọn lọc thuần.
- Vòng tiến hoá nhỏ (3–5 thế hệ) trên fixture, xuất log JSON.
- Test: schema, sửa lỗi, elitism, không gọi mạng.

Ngoài phạm vi:

- Không gọi mô hình thật, không API key, không `requests`/`httpx`.
- Không huấn luyện, không tối ưu đa mục tiêu (bài 19 trong lộ trình làm NSGA-II).
- Không song song hoá lời gọi.

## Cảnh báo production

- Mô hình thật **không tất định** và có thể trả JSON sai, bịa khóa, hoặc từ chối. Bài tập mô phỏng đúng ba tình huống đó bằng script.
- Prompt chứa dữ liệu người dùng là bề mặt tấn công prompt injection; bài tập không xử lý, chỉ ghi chú.
- Chi phí: mỗi toán tử một lời gọi; với quần thể 50 và 5 thế hệ là 250 lời gọi. Bài tập đếm số lời gọi và yêu cầu in ra.
- Không log prompt/response thô: chúng có thể chứa dữ liệu nhạy cảm. Chỉ log băm và thông điệp lỗi đã lọc.

## Fixture offline

- `fixtures/script_cli.json` — chuỗi phản hồi hợp lệ cho 5 toán tử.
- `fixtures/script_bad_json.json` — một phản hồi hỏng, một phản hồi sửa được.
- `fixtures/script_unknown_key.json` — phản hồi có khóa lạ.
- `fixtures/population.json` — quần thể ban đầu với fitness cho trước.
- Không có URL ngoài, không biến môi trường bí mật.

## Liên kết

- [SPEC.md](SPEC.md) — giao diện toán tử, lược đồ JSON, ví dụ, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế template method, chính sách sửa lỗi, cách kiểm chứng.
