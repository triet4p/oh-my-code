# GUIDE — Content collection schema

## Bước 0 — Môi trường

```bash
mkdir 11_CONTENT_COLLECTION_SCHEMA/work && cd 11_CONTENT_COLLECTION_SCHEMA/work
npm init -y
npm install zod yaml gray-matter
npm install -D typescript tsx vitest @types/node
npx tsc --init --strict --target ES2022 --module NodeNext --moduleResolution NodeNext
```

Thêm `"type": "module"` và script `"check": "tsx src/cli.ts"`, `"test": "vitest run"`.

## Bước 1 — Viết schema trước loader

Tạo `src/schema.ts`:

- `postSchema` và `plannedTopicSchema`.
- Export type bằng `z.infer`.

Gợi ý cấu trúc:

```text
const nonEmpty = z.string().trim().min(1);
const dateValue = z.union([z.date(), z.number().finite(), z.string().min(1)]).transform(...)
```

Nhưng `z.coerce.date()` của Zod là điểm khởi đầu tốt; sau đó thêm kiểm tra chặt cho chuỗi ngày.

## Bước 2 — Ngày: cái bẫy rollover

`new Date("2026-02-30")` trong JavaScript **không** ném; nó thành `2026-03-02`. Vì vậy `z.coerce.date()` một mình sẽ chấp nhận ngày không tồn tại.

Một bẫy thứ hai: `z.coerce.date()` gọi `new Date(value)`, mà `new Date(null)` là epoch `0` và `new Date(true)` là `1 ms`. Nếu SPEC nói `null` bị từ chối, bạn phải chặn `null` **trước** bước coerce, ví dụ bằng `z.preprocess` hoặc union chỉ nhận `Date | number | string` rồi transform. Đừng dựa vào `z.coerce.date()` để phân biệt “thiếu” với “null”.

Cách kiểm tra chặt:

1. Nếu đầu vào là `Date`: kiểm tra `!Number.isNaN(getTime())`.
2. Nếu là number: `Number.isFinite`, rồi `new Date(n)`.
3. Nếu là string:
   - Trim.
   - Khớp `^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$` hoặc các định dạng bạn muốn hỗ trợ.
   - Tạo `Date` từ chuỗi.
   - Kiểm tra `!Number.isNaN`.
   - Nếu chuỗi chỉ có ngày (không giờ), so `getUTCFullYear/Month/Date` với các nhóm đã parse. Nếu lệch → lỗi.
   - Với chuỗi có giờ, vẫn nên kiểm tra phần ngày bằng cách tách trước `T`/dấu cách.
4. Từ chối mọi thứ khác.

Ghi rõ: `Date` không mang timezone gốc; bài tập giữ epoch và không “chuẩn hóa” về nửa đêm địa phương.

## Bước 3 — Default và null

Zod `default` chỉ chạy khi giá trị là `undefined`, không chạy với `null`.

- `tags: z.array(...).default([])` → thiếu → `[]`; `null` → lỗi.
- `draft: z.boolean().default(false)`.
- `status: z.enum([...]).default("planned")`.
- `updatedAt: dateSchema.optional()` → thiếu → `undefined`; `null` → lỗi.

Đây là hành vi bạn phải test, vì nhiều người nhầm `null` cũng được default.

## Bước 4 — Strict

`z.object({...}).strict()` từ chối khóa lạ. Nếu không strict, Zod loại bỏ khóa lạ và người viết không biết mình gõ sai `publisedAt`.

Muốn báo đường dẫn chính xác, dùng `safeParse` và map `error.issues`:

```text
issue.path.join(".")  // ["publishedAt"] -> "publishedAt"
```

Với mảng lồng nhau, path có thể chứa số.

## Bước 5 — Tách frontmatter

Dùng `gray-matter`:

```text
const parsed = matter(raw);
parsed.data     // object frontmatter
parsed.content  // body, bỏ qua
```

Bắt lỗi parse YAML và trả `invalid-frontmatter` gắn file. Nếu `parsed.data` rỗng (không có `---`), coi là `invalid-frontmatter` thay vì để schema báo thiếu từng trường — thông điệp rõ hơn.

Với planned topics, `JSON.parse` và kiểm tra object không mảng/không null.

## Bước 6 — Slug và thứ tự

Viết `toSlug(relativePath, extension)`:

- Chuẩn hóa `\` → `/`.
- Bỏ đuôi.
- Kiểm tra regex.
- Không đổi chữ hoa.

Duyệt file: dùng `fs.readdir({ recursive: true })` (Node 20+) hoặc tự đệ quy. Sắp danh sách đường dẫn trước khi đọc để lỗi ổn định.

Sau khi có mảng post, sắp theo `slug`; nếu trùng slug, giữ lỗi và vẫn trả các mục không trùng? SPEC yêu cầu trả lỗi; CLI dừng. Với API, trả `{index, issues}`; nếu có issue thì index có thể undefined. Chọn một: trả `Result`-like.

Gợi ý kiểu:

```ts
type LoadResult =
  | { ok: true; index: ContentIndex }
  | { ok: false; issues: ValidationIssue[] };
```

## Bước 7 — Refs

Chỉ chạy khi không có lỗi schema:

1. Tạo `Set` slug post.
2. Với mỗi post, với mỗi ref:
   - `ref === post.slug` → `self-ref`.
   - không có trong set → `unknown-ref`.
3. Trùng ref trong cùng mảng: kiểm tra trước hoặc trong lúc validate schema.

Không kiểm tra ref tới planned topic; refs chỉ trỏ post.

## Bước 8 — CLI

`src/cli.ts`:

- `process.argv[2]` là root; thiếu → usage exit 2.
- Gọi loader; nếu lỗi đọc root → 2.
- Nếu `ok` → in `OK: ...`, exit 0.
- Nếu không → in từng issue đã sắp, exit 1.

Dùng `process.exitCode`, không `process.exit` trước khi in xong.

## Bước 9 — Test

Fixture trong `test/fixtures/`:

- `valid/` với 2 post + 1 topic.
- `invalid/` với từng lỗi.
- `dup-slug/`.
- `bad-date/` với `2026-02-30`.

Test schema trực tiếp bằng object (không I/O) cho nhanh:

```ts
const parsed = postSchema.safeParse({ title: " x ", summary: "y", publishedAt: "2026-11-04" });
expect(parsed.success).toBe(true);
expect(parsed.data?.title).toBe("x");
expect(parsed.data?.draft).toBe(false);
```

Test loader cho thứ tự issue và slug.

## Bước 10 — Kiểm chứng độc lập

```bash
npm test
npx tsc --noEmit
npx tsx src/cli.ts test/fixtures/valid; echo "exit=$?"
npx tsx src/cli.ts test/fixtures/invalid; echo "exit=$?"
```

Kỳ vọng: `OK: 2 posts, 1 planned topics`/exit 0; danh sách lỗi/exit 1.

Kiểm tra rollover:

```bash
npx tsx -e "console.log(new Date('2026-02-30'))"
```

Bạn sẽ thấy ngày bị đẩy sang tháng 3; đó là lý do phải kiểm tra thành phần ngày.

## Bước 11 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `null` được default | Bạn nhầm `default` với `nullable`. |
| Khóa lạ không báo | Thiếu `.strict()`. |
| Ngày 30/02 lọt | Chỉ dùng `z.coerce.date()`. |
| Slug có `\` trên Windows | Chưa chuẩn hóa separator. |
| Thứ tự lỗi thay đổi | Chưa sắp file/issue. |
| Ref báo lỗi dù có bài | Slug tính cả đuôi hoặc khác chuẩn hóa. |
| `publishedAt` lệch ngày | Chuyển sang local time; dùng UTC/epoch. |
| Frontmatter `---` trong body bị cắt | `gray-matter` xử lý đúng; kiểm tra file thật. |

## Bước 12 — Mở rộng

- Thêm `series` và kiểm tra thứ tự.
- Thêm `updatedAt >= publishedAt`.
- Thêm kiểm tra tag thuộc taxonomy.
- Thêm `--json` cho CLI.
- Thêm cache theo mtime.

## Tự đánh giá

1. `default([])` và `optional()` khác nhau thế nào khi gặp `null`?
2. Vì sao phải kiểm tra thành phần ngày thay vì tin `new Date`?
3. Vì sao kiểm tra refs sau schema?
4. `.strict()` bảo vệ điều gì trong một hệ thống nội dung?
