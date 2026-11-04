# 49 — Trạng thái lịch trình job-shop động

## Mục tiêu

Mô phỏng rời rạc một job-shop động: job đến theo lịch, mỗi job có chuỗi công đoạn trên máy khác nhau, trạng thái chuyển theo bảng luật, máy chọn job bằng luật điều phối, và metric tính từ nhật ký sự kiện.

1. Cài vòng lặp sự kiện với thứ tự xử lý xác định khi trùng thời điểm.
2. Cài năm trạng thái `ARRIVED / WAITING / READY / PROCESSING / FINISHED` và bảng chuyển hợp lệ.
3. Tính `slack = max(0, deadline - now - remaining_processing)`.
4. Cài ba luật điều phối: SPT, SLACK, WSPT.
5. Sinh instance theo ba kiểu đến (`uniform`, `gauss`, `burst`) có seed.

## Giá trị

- Bảng chuyển trạng thái là cách rẻ nhất để bắt lỗi logic lịch trình: mọi bước sai đều thành ngoại lệ có ngữ cảnh thay vì số liệu lệch khó truy.
- Trùng thời điểm là nơi mô phỏng rời rạc hay sai: thứ tự "hoàn thành trước, phát hành sau, điều phối cuối" phải được viết thành luật, không phải ngẫu nhiên.
- Bạn học cách tách **sinh dữ liệu** (arrival/proc distribution) khỏi **mô phỏng** — hai thứ dễ trộn và làm mất tính tất định.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Trung bình–Khó |
| Điều kiện | Hàng đợi ưu tiên, vòng sự kiện, RNG có seed, đọc bảng chuyển trạng thái |
| Runtime | Không mạng, không GPU, không thư viện mô phỏng |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/SeEvoDJSSP` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/SeEvoDJSSP/blob/main/problem.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Tập biến `AVAIABLE_TERMINALS` gồm 18 `Terminal` dùng cho luật điều phối, trong đó có `JNPT`, `JD`, `JS`, `MUTIL`, `TNOW`, `AVGWT`.
  - `class Job.Status(Enum): ARRIVED / WAITING / READY / PROCESSING / FINISHED`.
  - Hàm truy vấn `get_slack_time(curr_time) = max(0, deadline - curr_time - remain_process_time)`.
  - Sinh instance `custom_generate(..., arrival_type='uniform'|'gauss'|'burst', proc_dist=..., deadline_factor=...)`.
- Giới hạn bằng chứng: đọc 300/334 dòng đầu; không quan sát được phần đánh giá và toàn bộ ngữ nghĩa 18 terminal. Tên `AVAIABLE_TERMINALS` giữ nguyên lỗi chính tả như trong nguồn khi trích dẫn.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: năm trạng thái và thứ tự của chúng; công thức slack có `max(0, …)`; ba kiểu đến; tham số `proc_dist`, `deadline_factor`; ý tưởng terminal cho luật điều phối.

Phần **do bài tập định nghĩa**:

- Bảng chuyển trạng thái đầy đủ và ngoại lệ `IllegalTransition`.
- Thứ tự xử lý khi trùng thời điểm: hoàn thành → phát hành → điều phối theo mã máy.
- Ba luật SPT/SLACK/WSPT với tie-break theo `job_id`.
- Sáu terminal tối giản (`JNPT`, `JD`, `JS`, `MUTIL`, `TNOW`, `AVGWT`) thay cho 18; không cài DSL biểu thức.
- Định nghĩa metric (makespan, tardiness trung bình, flow time trung bình, utilization).
- Định dạng fixture/output, tên lỗi.

Nguồn **không** bao gồm: thuật toán tiến hoá, LLM, hay đánh giá trên benchmark DJSSP thật.

## Phạm vi

Trong phạm vi:

- Mô phỏng ≤ 200 job, ≤ 5 máy, mỗi job ≤ 4 công đoạn.
- Ba luật điều phối; ba kiểu sinh đến; metric và nhật ký sự kiện.
- CLI chạy một instance từ fixture hoặc sinh từ seed, in JSON.

Ngoài phạm vi:

- Không tối ưu lịch trình (không GA, không MILP) — chỉ mô phỏng theo luật.
- Không máy hỏng, không bảo trì, không preemption.
- Không 18 terminal đầy đủ, không parser biểu thức (đó là phần mở rộng).
- Không đa luồng; thời gian mô phỏng là biến rời rạc, không dùng đồng hồ hệ thống.

## Cảnh báo production

- Mô phỏng rời rạc khác hệ thống thật: không có jitter, không thời gian chuyển máy, không giới hạn bộ đệm. Đừng dùng kết quả để cam kết năng lực sản xuất.
- `slack` dùng "remaining processing" là tổng thời gian còn lại, không chỉ công đoạn hiện tại — nếu hiểu sai, luật SLACK sẽ ưu tiên sai.
- Trùng thời điểm phải có luật; thay đổi thứ tự sẽ đổi makespan. Ghi rõ và test.
- Sinh `gauss` bằng tổng 12 số đều là xấp xỉ; không dùng để suy luận thống kê chặt.

## Fixture offline

- `fixtures/toy_shop.json` — 2 máy, 3 job, dùng cho ví dụ chuẩn.
- `fixtures/tight_deadlines.json` — deadline sát để có tardiness dương.
- `fixtures/gen_uniform.json`, `gen_gauss.json`, `gen_burst.json` — cấu hình sinh.
- `fixtures/illegal.json` — ép một chuyển trạng thái sai để kiểm tra ngoại lệ.
- Không có URL ngoài; không phụ thuộc thời gian hệ thống.

## Liên kết

- [SPEC.md](SPEC.md) — mô hình, bảng chuyển, luật điều phối, ví dụ số, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế vòng sự kiện, bẫy trùng thời điểm, cách kiểm chứng.
