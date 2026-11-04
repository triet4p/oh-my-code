# 18 — Typed notification parse: trạng thái thiếu / không đọc được / mơ hồ

## Mục tiêu

Tự viết bộ parse thông báo ngân hàng có kiểu: tách một thông báo thành các trường có trạng thái `Present`, `Unresolved(reason)`, `Missing`; đọc số tiền theo dấu, giữ thời điểm như giờ tường không kèm múi giờ, và không bao giờ biến một định dạng không hỗ trợ thành giao dịch. Bài tập dạy sealed interface, regex có neo, khử trùng lặp, và phân biệt “nguồn không nói” với “đọc không được”.

## Giá trị học được

- Ba trạng thái thiếu/không đọc được/mơ hồ khác nhau về nghiệp vụ, dù UI có thể hiển thị giống nhau.
- `Dấu trừ` là chiều tiền ngân hàng nói, không phải loại chi phí.
- Thời điểm không có múi giờ **không phải** một instant; không tự gán zone.
- Regex phải neo `^...$` để tránh khớp một phần.
- Khử trùng lặp theo **toàn bộ câu** (dấu + số tiền), không chỉ số tiền.
- Trường không có nhãn → `Missing`; có nhãn nhưng rỗng/masking → `Unresolved`.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Kotlin/JVM (không Android).
- Độ khó: **Khó**.
- Thời lượng gợi ý: 6–8 giờ.

## Điều kiện tiên quyết và runtime

- JDK 21, Kotlin 2.x, Gradle (Kotlin DSL), JUnit 5.
- Không cần Android SDK, không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/aegis-f`, file `app/src/main/java/io/github/triet4p/aegisf/notification/BankNotificationParser.kt`.
- URL chính xác: <https://github.com/triet4p/aegis-f/blob/main/app/src/main/java/io/github/triet4p/aegisf/notification/BankNotificationParser.kt>

Hành vi quan sát được trong nguồn:

- `enum class BankSource { VIETINBANK }`; `enum class BankDirection { DEBIT, CREDIT, UNKNOWN }`.
- `data class BankStatedMoment(date: String, time: String)`: ngày `YYYY-MM-DD`, giờ `HH:mm`, **không** kèm zone/epoch.
- `enum class UnresolvedReason { Unreadable, Redacted, Ambiguous }`.
- `sealed interface NotificationField<out T>` với `Present<T>(value)`, `Unresolved(reason)`, `Missing`.
- `sealed interface BankNotificationParse` với `UnsupportedFormat` và `Parsed(bank, amountVnd, direction, occurredAt, memo)`.
- `parseBankNotification(content)`:
  - Gộp `title`, `text`, `bigText` thành danh sách dòng: tách `\n`, trim, bỏ rỗng, `distinct()`.
  - Nếu không có dòng bắt đầu `VietinBank` hoặc không có dòng nhãn `GD` → `UnsupportedFormat`.
  - Regex attribution `^VietinBank\b(.*)$` (IGNORE_CASE).
  - Nhãn `^([A-Za-z]{1,4})\s*:\s*(.*)$`; `GD` là số tiền, `ND` là memo; `TK`, `SDC` được nhận diện để loại trừ.
  - Số tiền: regex `^([+-])?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(\S*)$`; hậu tố hợp lệ `""`, `VND`, `VNĐ`, `Đ`, `₫`; dùng `VndMoney.parseManualAmount`; magnitude không âm; dấu xác định DEBIT/CREDIT.
  - Nhiều giá trị khác nhau → `Ambiguous`; không parse được → `Unreadable`.
  - Thời điểm: `dd/MM/yyyy HH:mm`, kiểm tra `ManualDateTime.dateError/timeError`; giữ `BankStatedMoment`; không tạo epoch.
  - Memo: `ND`; mask/placeholder → `Redacted`; khác nhau → `Ambiguous`; thiếu → `Missing`.
- Nguồn phụ thuộc các lớp Android/khác (`PermittedNotificationContent`, `VndMoney`, `ManualDateTime`) không nằm trong file.

## Phạm vi bài tập

Xây thư viện Kotlin/JVM:

- Các kiểu trên, không phụ thuộc Android.
- `parseBankNotification(content: PermittedNotificationContent): BankNotificationParse`.
- `VndMoney` tối giản (parse số nguyên dương).
- `ManualDateTime` tối giản (validate ngày/giờ, không đổi múi giờ).
- Bộ test JUnit 5 với fixture.

Không nằm trong phạm vi: đọc notification Android, quyền truy cập, lưu DB, chuyển sang expense/income, nhiều ngân hàng, đa tiền tệ.

## Liên kết

- [SPEC.md](SPEC.md) — grammar, trạng thái, ví dụ chính xác.
- [GUIDE.md](GUIDE.md) — sealed interface, regex, calendar, test.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập giữ grammar và mô hình trạng thái, nhưng tự định nghĩa `carriesUsableContent`, giới hạn số tiền, và validate lịch đầy đủ. Nguồn gọi các hàm chưa thấy trong file; các định nghĩa đó là của bài tập, không phải hành vi đã quan sát.
