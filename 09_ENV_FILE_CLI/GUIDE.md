# GUIDE — Env loader và notify preview

## Bước 0 — Môi trường

```bash
mkdir 09_ENV_FILE_CLI/work && cd 09_ENV_FILE_CLI/work
printf '{"type":"module","scripts":{"test":"node --test"}}' > package.json
mkdir -p src test content
```

## Bước 1 — Tách loader thành hàm thuần

Đừng để loader đọc thẳng `process.env` trong lúc test. Viết:

```text
export function parseEnvFile(text, baseEnv = process.env) -> string[]
```

Nó sửa `baseEnv` tại chỗ (giống `process.env`) và trả danh sách khóa đã nạp. Trong test, truyền một object thường `{}`; trong CLI, truyền `process.env`.

Nhờ vậy bạn kiểm tra precedence mà không làm bẩn môi trường test.

## Bước 2 — Parse đúng thứ tự

Với mỗi dòng:

1. `line.replace(/\r$/, "")` nếu bạn tách bằng `\n`; hoặc tách `/\r?\n/`.
2. `trim()`.
3. `if (!trimmed || trimmed.startsWith("#")) continue;`
4. `const eq = trimmed.indexOf("="); if (eq < 0) continue;`
5. `const key = trimmed.slice(0, eq).trim();`
6. `const value = trimmed.slice(eq + 1).trim();`
7. `if (!key) continue;`
8. `if (Object.hasOwn(baseEnv, key)) continue;`
9. `baseEnv[key] = value; loaded.push(key);`

Tại sao `Object.hasOwn` thay vì `!baseEnv[key]`? Vì `!` coi chuỗi rỗng là chưa có, dẫn đến file ghi đè một biến rỗng có chủ đích. Đây là khác biệt so với nguồn; ghi rõ trong README bài làm.

Tại sao `indexOf` thay vì `split("=")`? `split` rồi `join` cũng đúng, nhưng `indexOf` rõ ý hơn và không tạo mảng thừa.

Không dùng `trim()` lên value nếu bạn muốn giữ khoảng trắng có nghĩa? Bài tập chọn trim cả hai đầu, giống nguồn; ghi rõ.

## Bước 3 — Đọc file an toàn

```text
try {
  const text = await readFile(envPath, "utf8");
  const loaded = parseEnvFile(text);
} catch (err) {
  if (err.code === "ENOENT") { /* bỏ qua */ }
  else throw new UsageError(...);
}
```

Không coi `ENOENT` là lỗi; coi `EACCES` là lỗi cấu hình.

Không in `loaded` kèm giá trị. Nếu muốn in, chỉ in tên khóa.

## Bước 4 — Chọn mục

Viết một hàm `selectItem(manifest, { type, slug })` trả `{ item, type }` hoặc ném `DataError`.

Thứ tự slug:

```text
const groups = [
  ["daily", manifest.daily_reports],
  ["weekly", manifest.weekly_reports],
  ["deep-dive", manifest.deep_dives],
  ["overview", manifest.overviews],
];
if (slug) {
  for (const [kind, arr] of groups) {
    const found = (arr ?? []).find(x => x.slug === slug);
    if (found) return { item: found, type: kind };
  }
  throw new DataError(`slug not found: ${slug}`);
}
```

Sau đó `switch (type)`.

Một cái bẫy: nếu bạn dùng `manifest.daily_reports?.find(...) || manifest.weekly_reports?.find(...)`, một object rỗng `{}` là truthy; nhưng `find` trả `undefined` khi không thấy, nên chuỗi `||` vẫn đúng. Tuy nhiên nếu mục tìm thấy là `null`, sẽ sai. Dùng vòng lặp rõ ràng.

## Bước 5 — Validate tối thiểu

Trước khi render, kiểm tra mục được chọn:

- `slug` string không rỗng.
- `title` string không rỗng.
- `summary` string không rỗng.
- `channels_monitored` nếu có: mảng string.
- `tags` nếu có: mảng string.
- `date`/`week_number`/`sector` nếu cần cho tiêu đề: đúng kiểu; nếu thiếu, dùng giá trị rỗng có kiểm soát (hoặc lỗi — SPEC yêu cầu lỗi khi trường bắt buộc của loại thiếu; hãy chọn và ghi rõ).

Đừng validate toàn bộ manifest; chỉ mục được chọn. Điều này giữ CLI dùng được với manifest lớn có mục lỗi không liên quan.

## Bước 6 — Render

Viết `renderText(item, type, siteUrl)`:

- Chuẩn hóa `siteUrl` bằng `replace(/\/$/, "")` một lần.
- Chọn prefix bằng `switch`.
- Tạo mảng dòng, dùng `push` có điều kiện.
- `join("\n")`.

Kiểm tra bằng mắt với một ví dụ, rồi chuyển thành snapshot test. Snapshot ở đây hợp lý vì định dạng là hợp đồng.

Một cái bẫy: emoji và tiếng Việt đều là Unicode; đừng đếm `length` để cắt. Bài này không cắt.

## Bước 7 — Payload theo kênh

```text
const CHANNELS = [
  ["teams", ["TEAMS_WEBHOOK_URL"]],
  ["telegram", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]],
  ["slack", ["SLACK_WEBHOOK_URL"]],
  ["discord", ["DISCORD_WEBHOOK_URL"]],
];
```

Với mỗi kênh:

- Nếu được chọn, kiểm tra tất cả biến bằng `typeof process.env[name] === "string" && length > 0`? SPEC nói “thiếu cấu hình”; một biến rỗng nên coi là thiếu. Định nghĩa: `!value` (chuỗi rỗng → thiếu). Ghi rõ.
- `ready` nếu đủ; `skipped` kèm reason nếu thiếu.
- Không bao giờ gọi `fetch`.

Payload không chứa giá trị webhook/token — chỉ trạng thái. Đây là quy tắc bảo mật nhỏ nhưng quan trọng: payload có thể bị ghi ra file hoặc log.

## Bước 8 — Output

- `--json`: `console.log(JSON.stringify(payload))` từng dòng.
- `--out`: `mkdir(dir, {recursive:true})`; ghi từng file bằng `writeFile`; ghi `rendered.txt`; in `wrote <path>` cho từng file.
- Mặc định: in `rendered.txt` ra stdout.

Không dùng `process.exit()` trước khi `await writeFile` xong.

## Bước 9 — Kiểm thử

Test loader (hàm thuần):

| Input env | Input file | Kỳ vọng |
|---|---|---|
| `{A:"1"}` | `A=2` | `A === "1"` |
| `{}` | `A=2` | `A === "2"` |
| `{A:""}` | `A=2` | `A === ""` |
| `{}` | `A=` | `A === ""`, key có mặt |
| `{}` | `B=x=y` | `"x=y"` |
| `{}` | ` C = 3 ` | `"3"` |
| `{}` | `#X=1` | không có |
| `{}` | `X=1\nX=2` | `"1"` |

Test chọn mục:

- slug trùng ở daily và weekly → daily.
- slug không tồn tại → lỗi.
- latest fallback.
- type thiếu mảng → lỗi.

Test render: snapshot chính xác.

Test CLI: dùng `spawnSync` với `--root` trỏ tới thư mục fixture; kiểm tra status/stdout.

## Bước 10 — Kiểm chứng độc lập

```bash
node --test
node notify-preview.mjs --root fixtures --type latest
node notify-preview.mjs --root fixtures --slug week-45 --json
node notify-preview.mjs --root fixtures --channel all --out out --json
ls out
```

Kỳ vọng: văn bản đúng; JSON một dòng; `out/teams.json`, `out/telegram.json`, `out/slack.json`, `out/discord.json`, `out/rendered.txt`.

Kiểm tra không có mạng:

```bash
grep -R "fetch\|https\?://" --include='*.mjs' .
```

Chỉ được thấy URL trong dữ liệu render, không có lời gọi `fetch`.

## Bước 11 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Process env bị ghi đè | Dùng `!baseEnv[key]` thay vì `Object.hasOwn`. |
| Giá trị bị cắt sau `=` | Dùng `split("=")` rồi lấy `[1]`. |
| CRLF để lại `\r` | Không tách `\r?\n` hoặc không trim. |
| Slug không thấy nhưng vẫn ra kết quả | Fallback ngầm sau khi tìm slug thất bại. |
| Type `deep-dive` không khớp | Dùng `deep_dive` (snake) thay vì `deep-dive`. |
| Payload chứa token | Bạn spread toàn bộ `process.env`. |
| `--out` in cả nội dung | Vẫn `console.log(text)` sau khi ghi file. |
| Exit 0 khi manifest sai | Bắt lỗi quá rộng. |

## Bước 12 — Mở rộng

- Thêm `--check` chỉ validate manifest.
- Thêm `--format teams-card` render Adaptive Card.
- Thêm loader hỗ trợ quote/escape có test.
- Thêm `--site-url` ghi đè env.
- Thêm so sánh hai lần chạy để phát hiện manifest thay đổi.

## Tự đánh giá

1. Vì sao `Object.hasOwn` khác `!env[key]`?
2. Vì sao slug không tồn tại nên lỗi thay vì fallback?
3. Tại sao payload không nên chứa webhook URL?
4. Điều gì xảy ra nếu manifest có hai mục cùng slug trong cùng một mảng?
