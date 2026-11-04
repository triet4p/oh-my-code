# SPEC — Bilingual portfolio model

## Mục tiêu hành vi

Một object portfolio chứa đúng hai ngôn ngữ `vi` và `en`. Mỗi ngôn ngữ có cùng bộ khóa và cùng số phần tử ở các mảng nội dung; các trường định danh không phụ thuộc ngôn ngữ phải khớp. Validator trả danh sách lỗi có đường dẫn; dữ liệu hợp lệ có thể được dùng để render.

## Kiểu

```ts
export type Locale = "vi" | "en";

export interface Labels {
  experience: string;
  projects: string;
  skills: string;
  education: string;
  awards: string;
  footer: string;
}

export interface Profile {
  name: string;
  title: string;
  location: string;
  email: string;
  phone: string;
  linkedin: string;
  github: string;
  summary: string;
}

export interface EducationItem {
  school: string;
  period: string;
  major: string;
  details: string[];
}

export interface ExperienceItem {
  company: string;
  role: string;
  period: string;
  description: string[];
}

export interface ProjectItem {
  name: string;
  type: string;
  period: string;
  repo: string;
  tech: string[];
  description: string;
  features: string[];
}

export interface AwardItem {
  title: string;
  year: string;
}

export interface LocaleContent {
  labels: Labels;
  profile: Profile;
  education: EducationItem[];
  experience: ExperienceItem[];
  skills: Record<string, string[]>;
  projects: ProjectItem[];
  awards: AwardItem[];
}

export interface PortfolioContent {
  vi: LocaleContent;
  en: LocaleContent;
}

export interface ValidationIssue {
  path: string;
  code: string;
  message: string;
}
```

## API

| Hàm | Hợp đồng |
|---|---|
| `validatePortfolio(input: unknown)` | Trả mảng issue đã sắp theo `(path, code)`; rỗng nếu hợp lệ. Không ném với dữ liệu sai. |
| `pickLocale(content, locale)` | Trả `content[locale]`; ném `RangeError` nếu locale ngoài `vi`/`en`. |
| `assertPortfolio(content)` | Gọi validator; nếu có issue, ném `PortfolioValidationError` chứa issues. |

## Quy tắc cấu trúc

### Cấp gốc

- `input` phải là object không null, không mảng.
- Phải có đúng hai khóa `vi`, `en`; thiếu → `missing-locale`; thừa khóa khác → `unexpected-key`.
- Mỗi locale phải là object.

### Bên trong mỗi locale

Bộ khóa bắt buộc, không thừa, không thiếu:

| Khóa | Kiểu |
|---|---|
| `labels` | object 6 khóa chuỗi |
| `profile` | object 8 khóa chuỗi |
| `education` | mảng `EducationItem` |
| `experience` | mảng `ExperienceItem` |
| `skills` | object: khóa chuỗi không rỗng → mảng chuỗi |
| `projects` | mảng `ProjectItem` |
| `awards` | mảng `AwardItem` |

Khóa lạ ở bất kỳ object nào → `unexpected-key`. Thiếu → `missing-key`.

### Chuỗi

- Các trường chuỗi bắt buộc phải là string, không rỗng sau `trim`; giá trị được trim khi lưu? Validator không biến đổi; chỉ báo lỗi. `pickLocale` trả nguyên bản.
- `details`, `description`, `features`, `tech`: mảng string; mỗi phần tử không rỗng sau trim; không dedupe (trùng là lỗi `duplicate-item`? Xem dưới).
- `summary` ít nhất 20 ký tự (bài tập đặt ngưỡng để tránh placeholder).
- `email`: khớp `^[^\s@]+@[^\s@]+\.[^\s@]+$`.
- `linkedin`, `github`, `repo`: phải bắt đầu `https://`.
- `phone`: chỉ chữ số, `+`, khoảng trắng, `-`; ít nhất 8 chữ số.
- `year`: 4 chữ số.
- `period`: không rỗng; không kiểm tra định dạng.

## Parity giữa `vi` và `en`

Hai locale phải mô tả cùng thực thể:

1. **Cùng số phần tử** cho `education`, `experience`, `projects`, `awards`; lệch → `parity-length` tại `en.<mảng>`.
2. **Cùng bộ khóa** cho `labels` và `profile`; lệch → `parity-keys`.
3. **Cùng bộ nhóm kỹ năng** (khóa của `skills`); lệch → `parity-skills`. Số công nghệ trong một nhóm được phép khác (bản dịch có thể gộp/tách? Không — bài tập yêu cầu **cùng số lượng** để tránh lệch nội dung; xem dưới).
4. Trường định danh khớp theo chỉ số:

    - `education[i].period`
    - `experience[i].period`
    - `projects[i].repo`
    - `awards[i].year`

    Lệch → `parity-identity` tại `vi.<mảng>[i].<trường>`.
5. `projects[i].tech` phải cùng số lượng và cùng tập giá trị (không phân biệt thứ tự? Chọn: cùng tập, thứ tự được phép khác). Lệch → `parity-tech`.
6. `skills[category]` phải cùng số lượng phần tử; giá trị có thể dịch? Tên công nghệ thường giữ nguyên, nhưng bài tập chỉ yêu cầu cùng số lượng. Lệch → `parity-skill-count`.

### Vì sao không so khớp chuỗi đã dịch?

`name`, `title`, `summary`, `description` được phép khác hoàn toàn. Chỉ các trường định danh và số lượng bị ràng buộc. Đây là ranh giới quan trọng: parity cấu trúc, không phải parity ngôn ngữ.

## Mã lỗi

| Code | Khi nào |
|---|---|
| `not-an-object` | giá trị không phải object |
| `missing-locale` | thiếu `vi`/`en` |
| `unexpected-key` | khóa lạ |
| `missing-key` | thiếu khóa bắt buộc |
| `invalid-type` | sai kiểu |
| `empty-string` | chuỗi rỗng/trim rỗng |
| `string-too-short` | `summary < 20` |
| `invalid-email` | email sai |
| `invalid-url` | URL không bắt đầu `https://` |
| `invalid-phone` | phone sai ký tự/số chữ số |
| `invalid-year` | year không phải 4 chữ số |
| `duplicate-repo` | hai project cùng repo trong một locale |
| `duplicate-skill` | một nhóm kỹ năng có phần tử trùng |
| `duplicate-tech` | một project có phần tử `tech` trùng |
| `parity-length` | số phần tử lệch |
| `parity-keys` | bộ khóa lệch |
| `parity-skills` | bộ nhóm kỹ năng lệch |
| `parity-identity` | trường định danh lệch |
| `parity-tech` | tập tech lệch |
| `parity-skill-count` | số công nghệ trong nhóm lệch |

## Ví dụ

Hợp lệ tối thiểu: mỗi locale có 1 education, 1 experience, 1 project, 1 award, 1 nhóm skill; `repo` giống nhau, `period` giống nhau, `year` giống nhau.

Lỗi:

| Dữ liệu | Issue |
|---|---|
| thiếu `en` | `missing-locale` tại `en` |
| `vi.skills` có nhóm `"AI"`, `en.skills` không có | `parity-skills` tại `en.skills` |
| `vi.projects` có 2, `en.projects` có 1 | `parity-length` tại `en.projects` |
| `vi.projects[0].repo = "https://a"`, `en.projects[0].repo = "https://b"` | `parity-identity` tại `vi.projects[0].repo` |
| `vi.projects[0].tech = ["Python"]`, `en` có `["Python","Rust"]` | `parity-tech` |
| `vi.profile.email = "a@"` | `invalid-email` |
| `en.labels.extra = "x"` | `unexpected-key` |
| `vi.education[0].school = "  "` | `empty-string` |
| `vi.awards[0].year = "24"` | `invalid-year` |
| hai project cùng repo | `duplicate-repo` |

## Tính xác định

- Issue sắp theo `path` (so sánh chuỗi) rồi `code`.
- Không phụ thuộc thứ tự khóa của object đầu vào.
- Không đọc thời gian/locale hệ thống.
- Không tự sửa dữ liệu.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `null` | `not-an-object` tại `$` |
| Mảng ở gốc | `not-an-object` |
| `vi` là `null` | `not-an-object` tại `vi` |
| Locale có khóa `zh` | `unexpected-key` |
| `skills` rỗng | hợp lệ nếu hai bên cùng rỗng |
| Mảng rỗng ở cả hai | hợp lệ (cùng 0) |
| Tech trùng thứ tự khác | hợp lệ (so tập) |
| Tech trùng giá trị | `duplicate-tech` |
| `summary` đúng 20 ký tự | hợp lệ |
| URL `http://` | `invalid-url` |
| `phone` có chữ | `invalid-phone` |

## Tiêu chí nghiệm thu

1. Dữ liệu mẫu hợp lệ qua `validatePortfolio` không issue.
2. Mỗi mã lỗi trong bảng có ít nhất một test.
3. `parity-length`, `parity-keys`, `parity-skills`, `parity-identity`, `parity-tech` được kiểm tra độc lập.
4. Issue sắp xếp ổn định; đảo thứ tự khóa input không đổi kết quả.
5. `assertPortfolio` ném lỗi chứa đúng issues.
6. `pickLocale` trả đúng object và ném với locale lạ.
7. `tsc --noEmit` sạch; `vitest run` xanh.

## Non-goals

- React, CSS, routing, SEO.
- Dịch máy hoặc kiểm tra ngữ nghĩa bản dịch.
- Kiểm tra độ dài tối đa của CV.
- Sinh PDF.
- So khớp tên công ty/trường giữa hai ngôn ngữ.
