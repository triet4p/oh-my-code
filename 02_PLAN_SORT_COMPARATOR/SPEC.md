# SPEC — Plan comparator

## Mục tiêu hành vi

Cho một danh sách chủ đề, trả về một mảng mới được sắp theo thứ tự: trạng thái tăng dần theo bảng hạng, rồi ưu tiên tăng dần theo bảng hạng, rồi `updatedAt` giảm dần (mới nhất trước), và cuối cùng `id` tăng dần. Kết quả phải là một tổng thứ tự xác định, không phụ thuộc thứ tự đầu vào khi các khóa trước bằng nhau.

## Kiểu dữ liệu

```ts
export type Status = "planned" | "researching" | "on-hold" | "done";
export type Priority = "low" | "medium" | "high";

export interface Plan {
  id: string;
  status: Status;
  priority: Priority;
  updatedAt: Date | null;
}

export interface ValidationIssue {
  path: string;       // ví dụ "plans[2].updatedAt"
  code: string;       // "invalid-status" | "invalid-date" | ...
  message: string;
}
```

## Bảng thứ hạng

| Status | Hạng | Priority | Hạng |
|---|---:|---|---:|
| `planned` | 1 | `high` | 1 |
| `researching` | 2 | `medium` | 2 |
| `on-hold` | 3 | `low` | 3 |
| `done` | 4 | | |

## API

| Hàm | Hợp đồng |
|---|---|
| `comparePlans(a, b)` | Trả số âm nếu `a` đứng trước, dương nếu sau, `0` chỉ khi `a.id === b.id` và mọi khóa bằng nhau. Không được ném lỗi với dữ liệu đã qua `validatePlans`. |
| `sortPlans(plans)` | Trả `[...plans].sort(comparePlans)`; không sửa đầu vào. |
| `validatePlans(plans)` | Trả mảng issue đã sắp theo `path`; rỗng nghĩa là hợp lệ. |

## Quy tắc so sánh

Thứ tự từ điển, dừng ở khóa đầu tiên khác nhau:

1. `rank(status)` tăng dần.
2. `rank(priority)` tăng dần.
3. `updatedAt` giảm dần: thời điểm lớn hơn đứng trước.
4. `updatedAt === null` được coi là **cũ nhất** (`-Infinity`), nên đứng sau mọi giá trị có thật trong cùng nhóm 1–2.
5. `id` tăng dần theo so sánh chuỗi UTF-16 (`a.id < b.id ? -1 : 1`). Không dùng `localeCompare` để tránh phụ thuộc locale.

Công thức cho khóa 3–4:

```text
const ta = a.updatedAt?.getTime() ?? -Infinity;
const tb = b.updatedAt?.getTime() ?? -Infinity;
if (ta !== tb) return tb - ta;
```

Không trả `tb - ta` khi cả hai là `-Infinity`: `-Infinity - -Infinity` là `NaN`, và `NaN` làm comparator không hợp lệ. Phải kiểm tra `ta !== tb` trước.

## Kiểm tra dữ liệu

`validatePlans` nhận `unknown` (hoặc `readonly Plan[]`) và trả issue, không ném:

| Điều kiện | `code` |
|---|---|
| Không phải mảng | `not-an-array` tại path `$` |
| Phần tử không phải object | `not-an-object` tại `plans[i]` |
| `id` rỗng hoặc không phải string | `invalid-id` |
| `id` trùng | `duplicate-id` tại lần xuất hiện thứ hai |
| `status` ngoài enum | `invalid-status` |
| `priority` ngoài enum | `invalid-priority` |
| `updatedAt` không phải `Date` hợp lệ và không phải `null` | `invalid-date` |
| `Date` có `getTime()` là `NaN` | `invalid-date` |

`updatedAt` là `undefined` bị coi là không hợp lệ — khác với `null`. Quy ước này buộc người gọi chọn rõ “chưa cập nhật” thay vì để trường bị thiếu.

`sortPlans` giả định đầu vào đã hợp lệ. Nếu không, hành vi là không xác định; đừng thêm kiểm tra ngầm trong comparator.

## Tính xác định

- Với cùng một tập `Plan`, kết quả giống nhau ở mọi lần chạy và mọi thứ tự đầu vào (vì `id` là khóa cuối duy nhất).
- Không đọc đồng hồ hệ thống, không dùng `Math.random`, không phụ thuộc locale.
- `Date` được so bằng `getTime()` (mili giây epoch), nên hai `Date` cùng thời điểm bằng nhau kể cả khác timezone hiển thị.

## Ví dụ

Đầu vào:

| id | status | priority | updatedAt |
|---|---|---|---|
| `p1` | planned | high | 2026-01-01T00:00:00Z |
| `p2` | planned | high | 2026-02-01T00:00:00Z |
| `p3` | researching | low | 2025-12-01T00:00:00Z |
| `p4` | done | high | 2026-03-01T00:00:00Z |
| `p5` | planned | medium | 2026-01-15T00:00:00Z |
| `p6` | planned | high | `null` |

Thứ tự đầu ra:

| Vị trí | id | Lý do |
|---:|---|---|
| 1 | `p2` | planned, high, mới nhất |
| 2 | `p1` | planned, high, cũ hơn |
| 3 | `p6` | planned, high, không có ngày → cũ nhất |
| 4 | `p5` | planned, medium |
| 5 | `p3` | researching |
| 6 | `p4` | done |

Nếu đảo ngẫu nhiên đầu vào, thứ tự trên không đổi.

Trường hợp hai phần tử hoàn toàn giống nhau trừ `id`: `q1` và `q2` cùng `planned/high/null` → `q1` trước `q2`.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Mảng rỗng | `[]` |
| Một phần tử | mảng một phần tử mới |
| Tất cả cùng status/priority/updatedAt | sắp theo `id` |
| `updatedAt` toàn `null` | không ném; sắp theo `id` trong cùng nhóm |
| Hai `Date` cùng epoch | bằng nhau; chuyển sang `id` |
| `updatedAt` là `new Date(NaN)` | `validatePlans` báo `invalid-date`; `sortPlans` không được gọi |
| Status lạ | `validatePlans` báo; comparator không nhận |
| `id` có chữ hoa/dấu | so sánh code unit, không locale |

## Tiêu chí nghiệm thu

1. Bảng ví dụ 6 phần tử cho đúng thứ tự `p2, p1, p6, p5, p3, p4`.
2. Hai lần gọi `sortPlans` trên cùng dữ liệu nhưng đảo thứ tự đầu vào cho cùng kết quả.
3. `sortPlans` không sửa mảng gốc: so sánh tham chiếu từng phần tử trước/sau.
4. `comparePlans(a, a) === 0` với mọi `a` hợp lệ.
5. Không có kết quả `NaN`: kiểm tra `Number.isFinite(comparePlans(a,b))` trên mọi cặp trong bộ dữ liệu mẫu, kể cả cặp `null`/`null`.
6. `validatePlans` phát hiện đủ 8 mã lỗi ở bảng trên, và các issue được sắp theo `path`.
7. Test chạy bằng một lệnh duy nhất, không cần Astro.

## Non-goals

- Render giao diện hoặc đọc content collection.
- Sắp xếp theo tag, theo tên, hoặc theo độ dài ghi chú.
- Phân trang, lọc, tìm kiếm.
- Giữ ổn định thứ tự đầu vào khi mọi khóa bằng nhau — bài tập cố tình dùng `id` để tránh phụ thuộc tính ổn định của engine.
