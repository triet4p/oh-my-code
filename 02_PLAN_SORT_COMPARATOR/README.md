# 02 — Plan comparator: sắp thứ tự có nhiều khóa

## Mục tiêu

Tự viết một comparator nhiều tầng cho danh sách “chủ đề đang lên kế hoạch”: trạng thái trước, độ ưu tiên sau, thời điểm cập nhật mới nhất trước, và một khóa cuối để thứ tự hoàn toàn xác định. Bài tập rèn cách biến một đoạn `sort` ngắn trong trang web thành một hàm thuần có hợp đồng, kiểm thử được và không phụ thuộc framework.

## Giá trị học được

- Thứ tự nhiều khóa là một **tổng thứ tự từ điển**, không phải ba lần `sort` rời rạc.
- Giá trị thiếu (`updatedAt` null) cần một quy ước rõ, không để phụ thuộc vào `undefined`.
- Comparator phải có khóa phân định cuối nếu muốn kết quả không phụ thuộc engine.
- Tách dữ liệu khỏi hiển thị: bảng xếp hạng là logic, không phải JSX.

## Ngôn ngữ và độ khó

- Ngôn ngữ: TypeScript (Node 22).
- Độ khó: **Dễ**.
- Thời lượng gợi ý: 2–3 giờ.

## Điều kiện tiên quyết và runtime

- Node.js 22 trở lên, npm (hoặc pnpm).
- TypeScript, `vitest` (hoặc `node:test` với `tsx`).
- Không cần Astro, không cần trình duyệt, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/math-ai-connect`, file `src/pages/plans.astro`.
- URL chính xác: <https://github.com/triet4p/math-ai-connect/blob/master/src/pages/plans.astro>

Hành vi quan sát được trong nguồn:

- `statusOrder` gán `planned: 1`, `researching: 2`, `on-hold: 3`, `done: 4`.
- `priorityOrder` gán `high: 1`, `medium: 2`, `low: 3`.
- `plans.sort(...)` so sánh hiệu số thứ hạng trạng thái; nếu bằng 0 thì so hiệu số thứ hạng ưu tiên; nếu vẫn bằng 0 thì so `updatedAt` giảm dần, với `?? 0` cho giá trị thiếu.
- Sắp xếp diễn ra trực tiếp trên mảng lấy từ `getCollection`, và không có khóa phân định cuối ngoài thời gian.

## Phạm vi bài tập

Xây module `plan-order` xuất:

- Kiểu `Status`, `Priority`, `Plan`.
- `comparePlans(a, b): number`.
- `sortPlans(plans: readonly Plan[]): Plan[]` trả mảng mới.
- `validatePlans(plans): ValidationIssue[]` cho biên dữ liệu.

Không nằm trong phạm vi: Astro content collections, JSX, CSS, gọi API.

## Liên kết

- [SPEC.md](SPEC.md) — thứ tự chính xác, kiểm tra, ví dụ và tiêu chí.
- [GUIDE.md](GUIDE.md) — cách thiết kế comparator và kiểm thử.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn sắp xếp tại chỗ và dựa vào tính ổn định của `Array.prototype.sort`. Bài tập giữ nguyên thứ hạng nhưng yêu cầu **không sửa mảng đầu vào** và thêm khóa `id` cuối để tổng thứ tự. Đây là thiết kế của bài tập, không phải hành vi đã quan sát trong nguồn.
