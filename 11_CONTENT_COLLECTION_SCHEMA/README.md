# 11 — Content schema: kiểm tra hai collection bằng Zod

## Mục tiêu

Tự xây một lớp biên dữ liệu cho hai “collection” nội dung: bài viết Markdown và chủ đề kế hoạch JSON. Mỗi collection có schema, giá trị mặc định, ép kiểu ngày, và thông báo lỗi theo đường dẫn. Bài tập lấy ý tưởng từ `content.config.ts` của Astro nhưng bỏ Astro để bạn tự viết loader và validator.

## Giá trị học được

- Schema là hợp đồng ở biên: dữ liệu bên ngoài vào hệ thống phải qua đó.
- `default` áp dụng cho `undefined`, không áp dụng cho `null`; phân biệt này quan trọng.
- `z.coerce.date()` chấp nhận chuỗi/số; cần biết nó từ chối gì.
- Lỗi theo `path` giúp người viết nội dung sửa đúng chỗ.
- Tính nhất quán tham chiếu (`refs`) là kiểm tra **sau** schema, không phải trong schema.
- Duplicate slug là lỗi dữ liệu, không phải lỗi schema.

## Ngôn ngữ và độ khó

- Ngôn ngữ: TypeScript, Node 22.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Node.js 22+, npm.
- `zod`, `yaml`, `gray-matter` (hoặc tự tách frontmatter), `vitest`.
- Không cần Astro, không cần mạng sau khi cài.

## Nguồn gốc

- Nguồn: `triet4p/math-ai-connect`, file `src/content.config.ts`.
- URL chính xác: <https://github.com/triet4p/math-ai-connect/blob/master/src/content.config.ts>

Hành vi quan sát được trong nguồn:

- `posts` dùng loader `glob({ pattern: '**/*.{md,mdx}', base: './src/content' })`.
- Schema `posts`: `title: z.string()`, `summary: z.string()`, `tags: z.array(z.string()).optional()`, `refs: z.array(z.string()).optional()`, `draft: z.boolean().default(false)`, `publishedAt: z.coerce.date()`.
- `plannedTopics` dùng loader `glob({ pattern: '**/*.json', base: './src/content/planned-topics' })`.
- Schema `plannedTopics`: `tag: z.string()`, `note: z.string().optional()`, `status: z.enum(['planned', 'researching', 'on-hold', 'done']).default('planned')`, `priority: z.enum(['low', 'medium', 'high']).default('medium')`, `updatedAt: z.coerce.date().optional()`.
- `export const collections = { posts, plannedTopics }`.
- Nguồn không kiểm tra slug trùng, không kiểm tra `refs` tồn tại, không cấu hình `.strict()`.

## Phạm vi bài tập

Xây package `content-model`:

- Định nghĩa `Post`, `PlannedTopic`, `ContentIndex`.
- `postSchema`, `plannedTopicSchema` (Zod).
- `loadContent(rootDir)` đọc file, tách frontmatter/JSON, validate, áp default, kiểm tra trùng slug và refs.
- `validateContent(raw)` cho dữ liệu đã parse (dùng trong test).
- CLI `content-check <root>` in lỗi và mã thoát.

Không nằm trong phạm vi: Astro, render Markdown, MDX, watch mode, SEO, image processing.

## Liên kết

- [SPEC.md](SPEC.md) — schema, quy tắc slug/refs, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — loader, Zod, bẫy ngày và đường dẫn.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập thêm `.strict()` (từ chối khóa lạ), kiểm tra slug trùng và tham chiếu `refs`. Nguồn dùng Zod mặc định (bỏ khóa lạ) và không kiểm tra hai điều sau. Các bổ sung này là thiết kế của bài tập.
