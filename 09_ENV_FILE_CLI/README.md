# 09 — Env CLI: nạp `.env.local` và chọn bản tin để preview

## Mục tiêu

Tự viết một CLI cục bộ đọc file `.env.local`, áp quy tắc ưu tiên với biến môi trường sẵn có, đọc manifest nội dung, chọn đúng mục theo `--slug` hoặc `--type`, rồi render payload cho từng kênh ra file JSON — không gửi mạng. Bài tập tách phần “cấu hình” khỏi phần “gửi”, và biến một loader `.env` ngây thơ thành hợp đồng có kiểm thử.

## Giá trị học được

- Quy tắc precedence của biến môi trường: process env thắng file, hay ngược lại? Nguồn chọn “không ghi đè biến đã có”.
- Parse `.env` đúng: dòng trống, comment, `=` trong giá trị, CRLF, khóa trùng.
- Chọn mục theo thứ tự fallback xác định, không phụ thuộc thứ tự object.
- Render văn bản có cấu trúc từ dữ liệu có thể thiếu trường.
- Mã thoát cho lỗi cấu hình/dữ liệu, không trộn với thành công.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Node.js 22, ESM.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Node.js 22+.
- Không cần npm install, không cần webhook, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/daily-research`, file `scripts/notify-team.mjs`.
- URL chính xác: <https://github.com/triet4p/daily-research/blob/main/scripts/notify-team.mjs>

Hành vi quan sát được trong nguồn:

- Tự nạp `${rootDir}/.env.local` nếu tồn tại; đọc UTF-8, tách theo `\n`, trim từng dòng, bỏ dòng trống và dòng bắt đầu bằng `#`.
- Tách dòng tại `=` đầu tiên; `key` được trim; giá trị là phần còn lại nối bằng `=` rồi trim; chỉ gán nếu `!process.env[key]` (không ghi đè biến đã có).
- `parseArgs` nhận `--dry-run`, `--channel <v>`, `--type <v>`, `--slug <v>`; mặc định `dryRun: false`, `channel: "all"`, `type: "latest"`, `slug: null`.
- `getLatestItem` ưu tiên tìm theo slug trong `daily_reports`, rồi `weekly_reports`, `deep_dives`, `overviews`; nếu không có slug, chọn theo type; mặc định lấy `daily_reports[0]`, sau đó `weekly_reports[0]`, rồi `overviews[0]`.
- `formatNotification` tạo tiêu đề/đường dẫn theo loại và ghép các dòng markdown: tiêu đề, tóm tắt, kênh quét, tags, link.
- Nếu `--dry-run`, in payload đã chuẩn bị và không gửi; ngược lại gửi tới Teams/Telegram/Slack/Discord nếu có webhook/token tương ứng.

## Phạm vi bài tập

Xây `notify-preview.mjs`:

- Loader `.env` với quy tắc rõ và có test.
- Chọn mục theo slug/type với fallback xác định.
- Render text và payload JSON.
- Ghi payload ra thư mục `--out` hoặc in ra stdout; không gọi `fetch`.
- Báo “skipped” cho kênh thiếu biến cấu hình, nhưng không lỗi.

Không nằm trong phạm vi: gửi webhook thật, render Adaptive Card đầy đủ, validate schema manifest bằng JSON Schema, đọc từ xa.

## Liên kết

- [SPEC.md](SPEC.md) — định dạng manifest, quy tắc env, chọn mục, output, mã thoát.
- [GUIDE.md](GUIDE.md) — loader, precedence, render, test.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn mặc định **không** dry-run và sẽ gửi mạng; bài tập bỏ hoàn toàn mạng, luôn chỉ tạo payload. Nguồn coi biến môi trường rỗng là “chưa có” (`!process.env[key]`) nên file có thể ghi đè giá trị rỗng; bài tập định nghĩa “đã tồn tại, kể cả rỗng, thì không ghi đè” và nêu rõ đây là khác biệt. Các quy tắc khác bám sát nguồn.
