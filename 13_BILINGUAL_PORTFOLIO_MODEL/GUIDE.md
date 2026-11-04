# GUIDE — Bilingual portfolio model

## Bước 0 — Môi trường

```bash
mkdir 13_BILINGUAL_PORTFOLIO_MODEL/work && cd 13_BILINGUAL_PORTFOLIO_MODEL/work
npm init -y
npm install -D typescript vitest @types/node
npx tsc --init --strict --target ES2022 --module NodeNext --moduleResolution NodeNext
```

Thêm `"type": "module"`, script `"test": "vitest run"`, `"check": "tsc --noEmit"`.

## Bước 1 — Kiểu trước, validator sau

Viết toàn bộ interface trong `src/types.ts`. Mục tiêu: một lập trình viên có thể viết dữ liệu mới và được compiler chỉ lỗi thiếu trường.

Gợi ý dùng `satisfies` để vừa kiểm tra vừa giữ literal:

```ts
const sample = { vi: {...}, en: {...} } satisfies PortfolioContent;
```

Tại sao không `: PortfolioContent`? Vì annotation làm mất literal type (ví dụ `name: string` thay vì literal), khó dùng cho test snapshot. `satisfies` giữ literal.

Nhưng `satisfies` **không** kiểm tra parity giữa `vi` và `en`: cả hai cùng kiểu thì luôn “đúng kiểu” dù một bên có 2 project, bên kia 1. Đó là lý do cần validator runtime.

## Bước 2 — Validator dạng cây

Viết các helper nhỏ:

- `isObject(value): value is Record<string, unknown>`
- `expectString(obj, key, path, issues)`
- `expectArray(obj, key, path, issues)`
- `checkKeys(obj, required, path, issues)`

Mỗi helper nhận `issues: ValidationIssue[]` và đẩy lỗi. Không ném; validator luôn trả mảng.

Một cái bẫy: `typeof null === "object"`. `isObject` phải `value !== null && !Array.isArray(value)`.

Một cái bẫy khác: `Array.isArray` đúng cho mảng; đừng dùng `typeof === "object"`.

## Bước 3 — Validate từng locale

Viết `validateLocale(value, path): ValidationIssue[]`:

1. `isObject`.
2. `checkKeys` với bảy khóa.
3. `labels`: object đúng sáu khóa, mỗi giá trị string không rỗng.
4. `profile`: tám khóa; kiểm tra email/URL/phone/summary.
5. `education`: mảng object; mỗi item bốn khóa; `details` mảng string.
6. `experience`: bốn khóa; `description` mảng string.
7. `skills`: object; mỗi giá trị mảng string; khóa không rỗng; phần tử không rỗng; không trùng.
8. `projects`: bảy khóa; `tech`, `features` mảng string; repo https; không trùng repo trong locale.
9. `awards`: hai khóa; year regex.

Không cần generic schema; viết tường minh dễ đọc và dễ báo lỗi.

## Bước 4 — Parity

Sau khi cả hai locale không có lỗi cấu trúc (hoặc vẫn chạy nếu muốn báo nhiều), so sánh:

```text
const arrays = ["education", "experience", "projects", "awards"] as const;
for (const key of arrays) {
  if (vi[key].length !== en[key].length) issue(`en.${key}`, "parity-length", ...);
}
```

Chỉ so các cặp tồn tại; nếu một bên sai kiểu, bỏ qua parity cho trường đó để tránh crash.

Trường định danh:

| Mảng | Trường |
|---|---|
| education | `period` |
| experience | `period` |
| projects | `repo` |
| awards | `year` |

Với mỗi `i < min(len)`, so; lệch → issue tại `vi.<mảng>[i].<trường>`.

Skills:

```text
const viCats = new Set(Object.keys(vi.skills));
const enCats = new Set(Object.keys(en.skills));
// so bộ
for (const cat of viCats) {
  if (!enCats.has(cat)) issue(`en.skills`, "parity-skills", ...);
  else if (vi.skills[cat].length !== en.skills[cat].length) issue(`en.skills.${cat}`, "parity-skill-count", ...);
}
```

Tech: so **tập** giá trị, không thứ tự. Dùng `Set`; nếu kích thước khác hoặc có phần tử không thuộc → `parity-tech`.

Một cái bẫy: khóa object có thể là `"__proto__"` hoặc `"constructor"`. Khi dùng object thường, `Object.keys` không trả `__proto__` từ JSON parse? JSON.parse tạo own property `__proto__`? Nó tạo own data property; `Object.keys` có thể trả. Để an toàn, dùng `Object.create(null)` hoặc kiểm tra `Object.hasOwn`. Bài tập không cần chống prototype pollution sâu, nhưng nêu trong gotchas.

## Bước 5 — Sắp xếp issue

```text
issues.sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : a.code < b.code ? -1 : a.code > b.code ? 1 : 0);
```

Không dùng `localeCompare` để tránh phụ thuộc locale.

## Bước 6 — `assertPortfolio`

```ts
export class PortfolioValidationError extends Error {
  constructor(public readonly issues: ValidationIssue[]) {
    super(`portfolio invalid: ${issues.length} issue(s)`);
  }
}

export function assertPortfolio(value: unknown): asserts value is PortfolioContent {
  const issues = validatePortfolio(value);
  if (issues.length) throw new PortfolioValidationError(issues);
}
```

TypeScript assertion function cần khai báo `asserts`; người gọi có thể dùng giá trị sau khi gọi mà không cần ép kiểu.

## Bước 7 — `pickLocale`

```ts
export function pickLocale(content: PortfolioContent, locale: Locale): LocaleContent {
  if (locale !== "vi" && locale !== "en") throw new RangeError(`unsupported locale: ${locale}`);
  return content[locale];
}
```

Tại sao không fallback? Fallback âm thầm trộn ngôn ngữ và che lỗi cấu hình. Nếu cần fallback, đó là quyết định của lớp render, không phải model.

## Bước 8 — Test

Fixture:

- `valid.ts` với dữ liệu tối thiểu.
- Các hàm `clone()` rồi sửa một trường để tạo lỗi.

Nhóm test:

1. Valid → `[]`.
2. Từng mã lỗi.
3. Parity length/keys/skills/identity/tech.
4. Thứ tự issue.
5. `assertPortfolio` ném đúng lớp và issues.
6. `pickLocale` đúng và lỗi.
7. `tsc` bắt lỗi compile với dữ liệu thiếu trường (dùng `// @ts-expect-error`).

Một cái bẫy: test “valid” dễ vô tình thiếu một nhóm skills; hãy dùng `satisfies` để compiler giúp.

## Bước 9 — Kiểm chứng độc lập

```bash
npm test
npx tsc --noEmit
npx tsx -e "import {validatePortfolio} from './src/validate.ts'; import {sample} from './test/fixtures.ts'; console.log(validatePortfolio(sample).length)"
```

Kỳ vọng: `0`.

Sửa thử `en.projects[0].repo` thành URL khác, chạy lại; phải thấy `parity-identity`.

## Bước 10 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `null` lọt qua `isObject` | Thiếu kiểm tra `null`. |
| Mảng bị coi là object | Thiếu `!Array.isArray`. |
| Parity không chạy | Locale sai kiểu nên bị bỏ qua. |
| Issue trùng lặp | Validate locale hai lần hoặc parity chạy trên dữ liệu lỗi. |
| Thứ tự issue đổi | Chưa sort. |
| Tech khác thứ tự bị báo | So mảng thay vì set. |
| `satisfies` không bắt parity | Đúng; cần runtime. |
| `assertPortfolio` không narrow | Thiếu `asserts value is`. |
| Skills `__proto__` gây lỗi | Dùng object thường; kiểm tra `Object.hasOwn`. |

## Bước 11 — Mở rộng

- Thêm `schemaVersion`.
- Thêm locale thứ ba và kiểm tra N-way parity.
- Sinh type từ JSON Schema.
- Thêm `pickLocalized(field, locale)` cho từng trường.
- Thêm renderer terminal để xem CV hai ngôn ngữ.

## Tự đánh giá

1. Vì sao `satisfies` hữu ích hơn annotation ở đây?
2. Vì sao parity là kiểm tra runtime chứ không phải kiểu?
3. Trường nào được phép khác giữa hai ngôn ngữ, trường nào không?
4. Vì sao `pickLocale` không nên fallback?
