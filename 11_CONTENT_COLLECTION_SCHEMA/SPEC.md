# SPEC — Content collection schema

## Mục tiêu hành vi

Đọc hai tập nội dung từ filesystem, validate từng mục bằng schema, áp giá trị mặc định, ép ngày, rồi kiểm tra tính nhất quán toàn cục (slug duy nhất, `refs` trỏ tới bài có thật). Trả về một chỉ mục đã sắp xếp hoặc danh sách lỗi có đường dẫn.

## Cấu trúc thư mục đầu vào

```text
<root>/
├── posts/
│   ├── first-post.md
│   └── nested/second-post.md
└── planned-topics/
    ├── memory.json
    └── eval.json
```

Khác nguồn (dùng `src/content` và `src/content/planned-topics`), bài tập dùng hai thư mục ngang cấp để rõ ràng. Đường dẫn có thể cấu hình qua tham số.

## Kiểu đầu ra

```ts
export interface Post {
  slug: string;              // đường dẫn tương đối bỏ đuôi .md/.mdx, dùng "/"
  title: string;
  summary: string;
  tags: string[];            // default []
  refs: string[];            // default []
  draft: boolean;            // default false
  publishedAt: Date;
  file: string;              // đường dẫn tương đối tới root, dùng "/"
}

export interface PlannedTopic {
  slug: string;              // tên file bỏ .json
  tag: string;
  note?: string;
  status: "planned" | "researching" | "on-hold" | "done"; // default "planned"
  priority: "low" | "medium" | "high";                    // default "medium"
  updatedAt?: Date;
  file: string;
}

export interface ContentIndex {
  posts: Post[];             // sắp theo slug tăng dần
  plannedTopics: PlannedTopic[];
}
```

## Schema

### Post frontmatter

| Trường | Kiểu | Bắt buộc | Mặc định | Ghi chú |
|---|---|---|---|---|
| `title` | string | có | — | không rỗng sau trim? Xem dưới |
| `summary` | string | có | — | không rỗng |
| `tags` | string[] | không | `[]` | phần tử không rỗng |
| `refs` | string[] | không | `[]` | trỏ tới slug post khác |
| `draft` | boolean | không | `false` | |
| `publishedAt` | Date | có | — | nhận `Date`, chuỗi ISO, hoặc số epoch ms |

### Planned topic JSON

| Trường | Kiểu | Bắt buộc | Mặc định |
|---|---|---|---|
| `tag` | string | có | — |
| `note` | string | không | — |
| `status` | enum 4 giá trị | không | `planned` |
| `priority` | enum 3 giá trị | không | `medium` |
| `updatedAt` | Date | không | — |

## Quy tắc validate

- Dùng `.strict()`: khóa lạ → lỗi `unrecognized_keys` tại path của object. Đây là khác biệt có chủ đích so với Zod mặc định.
- `title`, `summary`, `tag` phải là string **không rỗng sau khi trim**; schema dùng `.trim().min(1)`. Giá trị đã trim được lưu.
- `tags`, `refs`: mảng string; mỗi phần tử trim, không rỗng; **không** dedupe tự động — trùng là lỗi `duplicate-tag`/`duplicate-ref`.
- `draft` phải là boolean thật; `"true"` không được ép.
- Ngày:
  - Nhận `Date` hợp lệ.
  - Nhận chuỗi mà `new Date(value)` parse được **và** không phải `Invalid Date`.
  - Nhận số hữu hạn (epoch ms).
  - Từ chối `null`, object, chuỗi rỗng, `NaN`, `Infinity`.
  - Kết quả là `Date`; không đổi múi giờ, không cắt ngày.
- `updatedAt` thiếu hoặc `null`: `null` bị từ chối (khác thiếu). Thiếu → `undefined`.

## Slug

- Post: đường dẫn tương đối từ thư mục `posts`, bỏ đuôi `.md` hoặc `.mdx`, đổi `\` thành `/`.
- Planned topic: tên file bỏ `.json`.
- Slug phải khớp `^[a-z0-9][a-z0-9/_-]*$`; chữ hoa, dấu cách, ký tự Unicode → lỗi `invalid-slug` (bài tập thắt chặt để URL ổn định).
- Không chuẩn hóa tự động; người viết phải đặt tên đúng.
- Trùng slug trong cùng một collection → lỗi `duplicate-slug` gắn với file xuất hiện sau.

## Tham chiếu `refs`

Sau khi tất cả post hợp lệ:

- Mỗi `ref` phải khớp `slug` của một post khác.
- Tự tham chiếu → lỗi `self-ref`.
- Không tồn tại → lỗi `unknown-ref` tại `posts[i].refs[j]`.
- Không kiểm tra chu trình; chỉ kiểm tra tồn tại.

Nếu có lỗi schema ở bất kỳ post nào, **không** chạy kiểm tra refs (tránh báo lỗi dây chuyền khó hiểu).

## Lỗi

```ts
export interface ValidationIssue {
  file: string;    // tương đối, hoặc "<memory>" khi validate object
  path: string;    // "posts[2].publishedAt" hoặc "plannedTopics[0].status"
  code: string;    // mã ổn định
  message: string; // tiếng Việt hoặc tiếng Anh, không quan trọng bằng code
}
```

Mã tối thiểu:

| Code | Khi nào |
|---|---|
| `invalid-type` | sai kiểu cơ bản |
| `missing-field` | thiếu trường bắt buộc |
| `empty-string` | chuỗi rỗng sau trim |
| `unrecognized-keys` | khóa lạ |
| `invalid-enum` | status/priority ngoài enum |
| `invalid-date` | ngày không parse được |
| `invalid-slug` | slug sai regex |
| `duplicate-slug` | trùng trong collection |
| `duplicate-tag` | tag trùng trong một post |
| `duplicate-ref` | ref trùng trong một post |
| `unknown-ref` | ref không tồn tại |
| `self-ref` | ref trỏ chính nó |
| `unreadable-file` | không đọc được |
| `invalid-frontmatter` | thiếu/không parse được frontmatter |
| `invalid-json` | JSON sai cú pháp |

Sắp xếp issue theo `(file, path, code)` tăng dần.

## CLI

```text
content-check <root>
```

- Không đối số → usage, exit 2.
- Có lỗi validate → in mỗi issue một dòng `file: path [code] message` ra stderr, exit 1.
- Không lỗi → in `OK: N posts, M planned topics` ra stdout, exit 0.
- Không đọc được root → exit 2.

## Ví dụ

`posts/first-post.md`:

```markdown
---
title: "Memory systems"
summary: "Notes on agent memory"
tags: ["ai", "memory"]
refs: ["second-post"]
publishedAt: "2026-11-04"
---

Body không được đọc.
```

`posts/second-post.md`:

```markdown
---
title: "Evaluation"
summary: "How to evaluate recall"
publishedAt: "2026-10-01T00:00:00Z"
---
```

Kết quả: 2 post; `first-post` có `draft: false`, `tags: ["ai","memory"]`, `refs: ["second-post"]`, `publishedAt` là `Date` tương ứng nửa đêm UTC ngày 2026-11-04.

Lỗi mẫu:

| File | Nội dung sai | Issue |
|---|---|---|
| `posts/Bad Slug.md` | tên file | `invalid-slug` |
| `posts/a.md` | thiếu `summary` | `missing-field` tại `summary` |
| `posts/a.md` | `draft: "true"` | `invalid-type` |
| `posts/a.md` | `extra: 1` | `unrecognized-keys` |
| `posts/a.md` | `publishedAt: ""` | `invalid-date` |
| `posts/a.md` | `refs: ["nope"]` | `unknown-ref` |
| `planned-topics/x.json` | `status: "done "` | `invalid-enum` |
| hai file cùng slug sau chuẩn hóa | | `duplicate-slug` |

## Tính xác định

- Thứ tự file đọc không ảnh hưởng kết quả cuối: sắp theo slug và sắp issue.
- Không phụ thuộc timezone hệ thống: `Date` giữ nguyên epoch; test so `getTime()`.
- Không tự sinh slug từ title.
- Cùng input → cùng output và cùng thứ tự lỗi.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Thư mục `posts` rỗng | `posts: []`, OK nếu `planned-topics` hợp lệ |
| Thiếu thư mục `posts` | coi như rỗng? **Không**: lỗi `unreadable-file` ở root (bài tập yêu cầu cả hai thư mục tồn tại) |
| File `.md` không có frontmatter | `invalid-frontmatter` |
| Frontmatter không phải mapping | `invalid-frontmatter` |
| JSON là mảng thay vì object | `invalid-type` |
| `tags: null` | `invalid-type` |
| `updatedAt: null` | `invalid-type` |
| `publishedAt: 0` | hợp lệ (epoch 0) |
| `publishedAt: "2026-02-30"` | `invalid-date` (JS `Date` rollover? xem GUIDE) |
| Slug có dấu cách | `invalid-slug` |
| Hai bài tham chiếu vòng | hợp lệ (không kiểm tra chu trình) |
| Ref tới bài `draft` | hợp lệ (không lọc draft) |
| Root không tồn tại | exit 2 |

## Tiêu chí nghiệm thu

1. `postSchema.parse` áp đúng default và trim.
2. `publishedAt` nhận chuỗi, số, `Date`; từ chối `null`, `""`, `"not-a-date"`.
3. `.strict()` báo khóa lạ.
4. Trùng slug báo đúng file thứ hai.
5. `refs` không tồn tại báo `unknown-ref`; tự tham chiếu báo `self-ref`.
6. CLI trên fixture hợp lệ exit 0 và in đúng số lượng.
7. CLI trên fixture lỗi exit 1 và in issue đã sắp.
8. Kết quả không phụ thuộc thứ tự duyệt file (đảo tên file, chạy lại).
9. `vitest run` xanh.

## Non-goals

- Render Markdown/MDX, syntax highlight.
- Astro content collections hoặc `astro:content`.
- Validate `refs` theo chu trình, theo draft, hay theo tag.
- Watch mode, incremental rebuild.
- Sinh slug từ title.
