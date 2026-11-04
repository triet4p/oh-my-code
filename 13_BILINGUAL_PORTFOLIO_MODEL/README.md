# 13 — Bilingual portfolio model: song ngữ có kiểm tra cấu trúc

## Mục tiêu

Tự thiết kế mô hình dữ liệu portfolio hai ngôn ngữ Việt/Anh: cùng một cấu trúc, khác giá trị. Viết validator kiểm tra không thiếu khóa, không lệch số phần tử, các trường định danh (repo, năm, giai đoạn) khớp nhau, và nội dung từng ngôn ngữ hợp lệ. Bài tập rèn kiểu TypeScript, kiểm tra runtime, và cách tách “dịch nội dung” khỏi “thay đổi cấu trúc”.

## Giá trị học được

- TypeScript bắt lỗi cấu trúc lúc biên dịch, nhưng không bắt lỗi parity giữa hai object cùng kiểu.
- `satisfies` giữ literal type trong khi vẫn kiểm tra hình dạng.
- Dữ liệu song ngữ có hai loại ràng buộc: **cấu trúc** (cùng khóa) và **định danh** (cùng thực thể).
- Bản dịch được phép khác độ dài chuỗi, nhưng không được khác số mục.
- Đường dẫn lỗi (`vi.projects[2].repo`) quan trọng hơn thông điệp chung.

## Ngôn ngữ và độ khó

- Ngôn ngữ: TypeScript, Node 22.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Node.js 22+, TypeScript, `vitest`.
- Không cần React, không cần trình duyệt, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/triet4p.github.io`, file `src/App.tsx`, nhánh `dev`.
- URL chính xác: <https://github.com/triet4p/triet4p.github.io/blob/dev/src/App.tsx>

Hành vi quan sát được trong nguồn:

- Một hằng `portfolioData` với hai khóa `vi` và `en`.
- Mỗi ngôn ngữ có `labels` (`experience`, `projects`, `skills`, `education`, `awards`, `footer`), `profile` (name, title, location, email, phone, linkedin, github, summary), `education`, `experience`, `skills`, `projects`, `awards`.
- `education[]`: `school`, `period`, `major`, `details[]`.
- `experience[]`: `company`, `role`, `period`, `description[]`.
- `skills`: object ánh xạ tên nhóm → mảng công nghệ.
- `projects[]`: `name`, `type`, `period`, `repo`, `tech[]`, `description`, `features[]`.
- `awards[]`: `title`, `year`.
- Dữ liệu được viết lặp lại cho hai ngôn ngữ; nguồn không có validator parity, không có kiểu tường minh cho toàn bộ object, và không kiểm tra tính nhất quán giữa `vi` và `en`.

## Phạm vi bài tập

Xây package `portfolio-model`:

- Kiểu `Locale`, `LocaleContent`, `PortfolioContent`, các item type.
- `validatePortfolio(input: unknown): ValidationIssue[]`.
- `pickLocale(content, locale): LocaleContent`.
- `assertPortfolio(content): asserts content is PortfolioContent`.
- Dữ liệu mẫu tối thiểu trong test.

Không nằm trong phạm vi: React component, CSS, i18n library, routing, SEO, dịch máy.

## Liên kết

- [SPEC.md](SPEC.md) — kiểu, quy tắc parity, mã lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế kiểu, validator, bẫy.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn chỉ là dữ liệu; bài tập thêm kiểu, validator, và quy tắc parity. Các quy tắc “cùng số phần tử”, “repo/năm/giai đoạn khớp” là thiết kế của bài tập, không phải hành vi đã quan sát.
