# SPEC — Env loader và notify preview

## Mục tiêu hành vi

Nạp cấu hình từ `.env.local` theo quy tắc precedence xác định, đọc manifest nội dung, chọn một mục theo slug hoặc loại, render văn bản thông báo và payload JSON cho từng kênh. Không thực hiện bất kỳ yêu cầu mạng nào.

## CLI

```text
node notify-preview.mjs [--root DIR] [--manifest PATH] [--env PATH]
                        [--type TYPE] [--slug SLUG] [--channel CHANNEL]
                        [--out DIR] [--json]
```

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--root` | cwd | gốc để resolve đường dẫn mặc định |
| `--manifest` | `<root>/content/manifest.json` | manifest |
| `--env` | `<root>/.env.local` | file env; thiếu file không phải lỗi |
| `--type` | `latest` | `latest`, `daily`, `weekly`, `deep-dive`, `overview` |
| `--slug` | không | chọn chính xác theo slug |
| `--channel` | `all` | `all`, `teams`, `telegram`, `slack`, `discord` |
| `--out` | không | ghi payload JSON vào thư mục |
| `--json` | tắt | in payload JSON ra stdout thay vì văn bản |

Cờ lặp / thiếu giá trị / giá trị lạ → exit 2.

## Cấu trúc manifest

```json
{
  "daily_reports": [
    { "slug": "2026-11-04-ai", "title": "…", "summary": "…", "date": "2026-11-04",
      "channels_monitored": ["A", "B"], "tags": ["ai", "llm"] }
  ],
  "weekly_reports": [
    { "slug": "week-45", "title": "…", "summary": "…", "week_number": 45 }
  ],
  "deep_dives": [
    { "slug": "agent-memory", "title": "…", "summary": "…", "sector": "ai" }
  ],
  "overviews": [
    { "slug": "landscape", "title": "…", "summary": "…" }
  ]
}
```

- Bốn mảng đều tùy chọn; thiếu được coi là rỗng.
- Mỗi mục phải có `slug` và `title` không rỗng, `summary` không rỗng, khi được chọn.
- `channels_monitored` và `tags`, nếu có, phải là mảng chuỗi.
- Không yêu cầu thứ tự mục; mục đầu tiên của mảng là “mới nhất” theo quy ước dữ liệu.

## Loader `.env`

File được đọc UTF-8. Với mỗi dòng:

1. Tách theo `\r?\n`.
2. `trim()` toàn dòng.
3. Bỏ qua nếu rỗng hoặc bắt đầu bằng `#`.
4. Bỏ qua nếu không chứa `=`.
5. Tách tại `=` **đầu tiên**: `key = left.trim()`; `value = rest.join("=").trim()`.
6. Bỏ qua nếu `key` rỗng.
7. Nếu `process.env` đã có thuộc tính `key` (kể cả giá trị `""`), **không ghi đè**.
8. Ngược lại gán `process.env[key] = value`.

Hệ quả:

- Khóa trùng trong file: lần xuất hiện đầu thắng (lần sau thấy key đã tồn tại).
- `A=x=y` → `x=y`.
- `A=` → `""`, và biến tồn tại.
- Không xử lý quote: `A="x"` giữ nguyên dấu `"`.
- Không mở rộng `$VAR`, không escape `\n`.
- Không ghi log giá trị; chỉ trả danh sách khóa đã nạp (không có khóa nào nếu bị chặn bởi env sẵn có).

Nếu file không tồn tại: bỏ qua, không cảnh báo là lỗi. Nếu không đọc được vì lý do khác (quyền): exit 2.

## Chọn mục

Nếu có `--slug`:

1. Tìm trong `daily_reports`; nếu thấy → loại `daily`.
2. Rồi `weekly_reports` → `weekly`.
3. Rồi `deep_dives` → `deep-dive`.
4. Rồi `overviews` → `overview`.
5. Không thấy → exit 3 (`slug not found`). **Không** fallback sang mục mới nhất.

Nếu không có slug:

| `--type` | Chọn |
|---|---|
| `latest` | `daily_reports[0]`, nếu không có → `weekly_reports[0]`, nếu không → `overviews[0]` |
| `daily` | `daily_reports[0]`; thiếu → exit 3 |
| `weekly` | `weekly_reports[0]`; thiếu → exit 3 |
| `deep-dive` | `deep_dives[0]`; thiếu → exit 3 |
| `overview` | `overviews[0]`; thiếu → exit 3 |

`--slug` thắng `--type` khi cả hai có mặt; loại được suy ra từ mảng tìm thấy.

## Site URL

Thứ tự: `SITE_URL` → `VERCEL_PROJECT_URL` → `https://daily-research-two.vercel.app`. Bỏ `/` cuối trước khi ghép.

## Render văn bản

Tiêu đề theo loại:

| Loại | Tiền tố |
|---|---|
| daily | `⚡ [DAILY PULSE • {date}]` |
| weekly | `📅 [WEEKLY BRIEFING • Tuần {week_number}]` |
| deep-dive | `🔬 [CHUYÊN ĐỀ SÂU • {SECTOR}]` (`sector` rỗng → `TECH`) |
| overview | `🌐 [BÁO CÁO TOÀN CẢNH]` |

Nội dung chính xác:

```text
{prefix} *{title}*

📝 *Tóm tắt:* {summary}
[📡 *Kênh quét:* {channels.join(" • ")}]      (chỉ khi mảng không rỗng)
[🏷 *Tags:* {tags.map(t => "#" + t.replace(/\s+/g, "_")).join(" ")}]  (chỉ khi không rỗng)

👉 *Đọc bài đầy đủ:* {url}
```

- Dòng trống giữa tiêu đề và tóm tắt; dòng trống trước link.
- Không có dòng cuối thừa.
- `url`: daily → `/daily/{slug}`, weekly → `/weekly/{slug}`, deep-dive → `/deep-dives/{slug}`, overview → `/overview/{slug}`.
- Tag có khoảng trắng được thay bằng `_`; không chuẩn hóa dấu tiếng Việt.

## Payload JSON

Mỗi kênh một object:

```json
{
  "channel": "teams",
  "status": "ready",
  "reason": null,
  "type": "daily",
  "title": "…",
  "text": "…",
  "url": "https://…/daily/…"
}
```

Kênh thiếu cấu hình:

```json
{ "channel": "telegram", "status": "skipped", "reason": "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", "type": "daily", "title": "…", "text": "…", "url": "…" }
```

Biến cấu hình cần:

| Kênh | Biến |
|---|---|
| teams | `TEAMS_WEBHOOK_URL` |
| telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| slack | `SLACK_WEBHOOK_URL` |
| discord | `DISCORD_WEBHOOK_URL` |

`--channel all` xử lý theo thứ tự `teams`, `telegram`, `slack`, `discord`. Kênh cụ thể chỉ xử lý một. “Skipped” không phải lỗi: exit vẫn 0.

## Output

- Mặc định (`--json` tắt): in văn bản đã render cho mục được chọn, một lần, ra stdout.
- `--json`: in một object JSON cho mỗi kênh được chọn, mỗi object một dòng (NDJSON).
- `--out DIR`: tạo thư mục, ghi `<channel>.json` cho từng kênh, và `rendered.txt` chứa văn bản. Không in nội dung ra stdout, chỉ in đường dẫn đã ghi.
- Nếu cả `--json` và `--out` được truyền, `--out` thắng: chỉ ghi file và in đường dẫn, không in NDJSON.
- Không ghi đè file ngoài `DIR`; không tạo thư mục cha ngầm ngoài `DIR`.

## Mã thoát

| Tình huống | Mã |
|---|---:|
| Thành công (kể cả mọi kênh skipped) | 0 |
| Cờ sai, thiếu giá trị, giá trị lạ | 2 |
| Không đọc được env (không phải thiếu file) | 2 |
| Manifest thiếu/JSON sai | 3 |
| Không tìm thấy slug/loại | 3 |
| Mục thiếu trường bắt buộc, sai kiểu | 3 |
| Không ghi được `--out` | 4 |

## Ví dụ

`.env.local`:

```dotenv
# cấu hình cục bộ
SITE_URL="https://example.test/"
TEAMS_WEBHOOK_URL=https://example.test/hook?a=1
EMPTY=
TOKEN=x=y
```

Với `process.env.TEAMS_WEBHOOK_URL` chưa có, loader đặt giá trị từ file. Với `SITE_URL` đã có trong process, file không ghi đè (kể cả giá trị rỗng: nếu process có `SITE_URL=""`, kết quả vẫn rỗng và url thành `/daily/...`).

Manifest có daily đầu tiên slug `2026-11-04-ai`:

```bash
node notify-preview.mjs --root . --type latest --channel all --json
```

In bốn dòng JSON theo thứ tự teams, telegram, slack, discord; teams `ready` (nếu env có), các kênh còn lại `skipped`.

Với `--slug week-45`, loại thành `weekly`, đường dẫn `/weekly/week-45`, tiêu đề `Tuần 45`.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `.env.local` không tồn tại | tiếp tục; không lỗi |
| Dòng `FOO` không có `=` | bỏ qua |
| Dòng `=bar` | bỏ qua (key rỗng) |
| Dòng ` FOO = bar ` | `FOO=bar` |
| Giá trị chứa `=` | giữ toàn bộ sau dấu đầu |
| Khóa trùng | lần đầu thắng |
| Process env đã có khóa rỗng | không ghi đè |
| Slug không tồn tại | exit 3, không fallback |
| `--type deep-dive` không có mục | exit 3 |
| Manifest `daily_reports` không phải mảng | exit 3 |
| `tags` chứa số | exit 3 |
| Summary rỗng | exit 3 |
| `--out` không ghi được | exit 4 |
| `--channel all` và không có env nào | 4 payload skipped, exit 0 |

## Tiêu chí nghiệm thu

1. Test loader với bảng precedence ở trên, kiểm tra `process.env` sau khi nạp.
2. Test chọn slug ưu tiên daily trước weekly khi trùng slug.
3. Test slug không tồn tại → exit 3.
4. Test `latest` fallback đúng thứ tự.
5. Test render văn bản khớp chính xác cho một mục daily có đủ trường.
6. Test `--channel all` tạo đúng bốn payload theo thứ tự, `skipped` khi thiếu env.
7. Test `--out` ghi file và không in nội dung.
8. Test không có lời gọi `fetch`/`http` trong mã nguồn (grep).
9. `node --test` xanh.

## Non-goals

- Gửi webhook thật, retry, rate limit.
- Adaptive Card đầy đủ cho Teams.
- Parse `.env` với quote/escape/multiline.
- Validate toàn bộ manifest bằng JSON Schema.
- Sinh HTML.
