# GUIDE — Plan comparator

## Bước 0 — Môi trường

```bash
mkdir 02_PLAN_SORT_COMPARATOR/work && cd 02_PLAN_SORT_COMPARATOR/work
npm init -y
npm install -D typescript vitest @types/node
npx tsc --init --strict --target ES2022 --module NodeNext --moduleResolution NodeNext
```

Đặt `src/plan-order.ts` và `tests/plan-order.test.ts`. Thêm `"type": "module"` vào `package.json` và script `"test": "vitest run"`.

## Bước 1 — Mô hình hóa dữ liệu

Bắt đầu bằng kiểu, chưa viết logic:

- `Status` và `Priority` là union chuỗi, không phải `string`.
- `updatedAt` là `Date | null`, không phải `string | undefined`.
- `Plan` có `id` bắt buộc.

Tự hỏi: nếu người gọi có dữ liệu JSON, ai chịu trách nhiệm đổi `publishedAt` sang `Date`? Câu trả lời: lớp biên (`validatePlans` / parser), không phải comparator. Comparator chỉ làm việc với kiểu đã chuẩn hóa.

## Bước 2 — Bảng hạng

Viết hai object `as const`:

```ts
const STATUS_RANK: Record<Status, number> = { planned: 1, researching: 2, "on-hold": 3, done: 4 };
const PRIORITY_RANK: Record<Priority, number> = { high: 1, medium: 2, low: 3 };
```

Dùng `Record<Status, number>` để TypeScript bắt thiếu khóa khi bạn thêm status mới. Đây là lợi ích lớn hơn `enum`.

## Bước 3 — Viết comparator từng tầng

Viết theo thứ tự và **return sớm** ở mỗi tầng:

1. Hiệu số hạng trạng thái.
2. Hiệu số hạng ưu tiên.
3. So sánh thời gian với `?? -Infinity`.
4. So sánh `id`.

Gợi ý cho tầng 3: đừng viết `return tb - ta` ngay. Viết một helper `timeOf(plan): number` trả `plan.updatedAt?.getTime() ?? -Infinity`, rồi:

- Nếu `ta < tb` → `1` (vì mới hơn đứng trước).
- Nếu `ta > tb` → `-1`.
- Nếu bằng nhau → đi tiếp.

Cách này tránh `NaN` khi cả hai là `null` và tránh tràn số khi hai mốc thời gian rất xa nhau.

Tầng 4: so sánh chuỗi bằng `<`/`>`; trả `0` khi `id` bằng nhau. Vì `id` là duy nhất sau validate, `0` chỉ xuất hiện khi so một phần tử với chính nó.

## Bước 4 — Không sửa đầu vào

`sortPlans` phải là:

- Tạo bản sao nông bằng spread.
- Gọi `.sort(comparePlans)` trên bản sao.
- Trả bản sao.

Đừng dùng `toSorted` nếu môi trường đích chưa hỗ trợ; spread là đủ và rõ ràng.

Kiểm thử: lưu `const before = [...plans]`, gọi hàm, rồi `expect(plans).toEqual(before)` và `expect(plans[0]).toBe(before[0])`.

## Bước 5 — Validate ở biên

Viết `validatePlans(input: unknown)`:

- Kiểm tra `Array.isArray` trước.
- Với mỗi phần tử, kiểm tra object không null, không mảng.
- Kiểm tra từng trường; đẩy issue với `path` dạng `plans[3].status`.
- Theo dõi `Set<string>` cho `id` để báo trùng ở lần thứ hai.
- Sắp issue theo `path` trước khi trả.

Gợi ý: tách `validatePlan(plan, path): ValidationIssue[]` để dễ test từng phần tử.

Một cái bẫy: `typeof value === "object"` đúng với `null` và mảng. Phải kiểm tra riêng.

Một cái bẫy khác: `new Date("not-a-date")` không ném; nó tạo `Date` có `getTime() === NaN`. Phải kiểm tra `Number.isFinite(date.getTime())`.

## Bước 6 — Test theo bảng

Tạo mảng 6 phần tử như SPEC, viết test:

- `expect(sortPlans(plans).map(p => p.id)).toEqual([...])`.
- `expect(sortPlans(shuffle(plans))).toEqual(sortPlans(plans))` với một hoán vị cố định.
- Với mọi cặp, `Number.isFinite(comparePlans(a,b))`.
- Với `null`/`null`, comparator trả `0` hoặc so `id`, không `NaN`.

Thêm test đột biến: cố tình đổi `high` thành 3 và xem test nào đỏ. Nếu không test nào đỏ, bảng ví dụ chưa đủ mạnh.

## Bước 7 — Kiểm chứng độc lập

```bash
npm test
npx tsc --noEmit
```

Kỳ vọng: cả hai lệnh thoát 0. Nếu `tsc` báo `Object is possibly 'null'`, bạn chưa xử lý `updatedAt` ở một nhánh.

Chạy thử bằng tay:

```bash
npx tsx -e "import {sortPlans} from './src/plan-order.ts'; console.log(sortPlans([{id:'b',status:'done',priority:'high',updatedAt:null},{id:'a',status:'planned',priority:'low',updatedAt:new Date('2026-01-01')}]).map(p=>p.id))"
```

Kết quả mong đợi: `[ 'a', 'b' ]`.

## Bước 8 — Gỡ vướng

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Thứ tự đúng nhưng đảo đầu vào thì khác | Thiếu khóa `id` cuối. |
| `NaN` trong comparator | Trừ hai `-Infinity`, hoặc `Date` không hợp lệ. |
| `null` đứng đầu | Bạn dùng `?? 0` thay vì `-Infinity`, hoặc quên đảo dấu. |
| Test “không sửa đầu vào” đỏ | `sort` gọi trên mảng gốc. |
| TypeScript không bắt thiếu status | Bảng hạng đang là `Record<string, number>`. |
| Issue validate sai thứ tự | Chưa sort theo `path`. |

## Bước 9 — Mở rộng

- Thêm `sortBy` cấu hình được (mảng khóa + hướng), rồi biểu diễn thứ tự hiện tại như dữ liệu.
- Thêm nhóm theo trạng thái và chỉ sắp trong nhóm.
- Thêm comparator cho ngày theo múi giờ nghiệp vụ, có ghi rõ chuyển đổi.
- Viết test property-based: sinh ngẫu nhiên 100 plan, kiểm tra phản đối xứng, bắc cầu, và tính nhất quán với một sắp xếp tham chiếu.

## Tự đánh giá

1. Vì sao `updatedAt` thiếu phải là `-Infinity` chứ không phải `0`?
2. Vì sao `id` là khóa cuối tốt hơn dựa vào sort ổn định?
3. `comparePlans` có nên gọi `validatePlans` không? Vì sao?
4. Nếu thêm status `archived`, những chỗ nào phải sửa và compiler giúp gì?
