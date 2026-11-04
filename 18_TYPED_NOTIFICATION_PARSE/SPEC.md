# SPEC — Typed bank notification parse

## Mục tiêu hành vi

Đọc một `PermittedNotificationContent` và trả hoặc `UnsupportedFormat`, hoặc `Parsed` với bốn trường có trạng thái. Không suy đoán trường thiếu, không gán múi giờ, không biến dấu trừ thành “chi phí”, và không nhận định dạng ngoài grammar.

## Kiểu

```kotlin
enum class BankSource { VIETINBANK }
enum class BankDirection { DEBIT, CREDIT, UNKNOWN }
enum class UnresolvedReason { Unreadable, Redacted, Ambiguous }

data class BankStatedMoment(val date: String, val time: String)
// date = "yyyy-MM-dd", time = "HH:mm", không zone, không epoch

sealed interface NotificationField<out T> {
    data class Present<T>(val value: T) : NotificationField<T>
    data class Unresolved(val reason: UnresolvedReason) : NotificationField<Nothing>
    data object Missing : NotificationField<Nothing>
}

data class PermittedNotificationContent(
    val title: String? = null,
    val text: String? = null,
    val bigText: String? = null,
)

sealed interface BankNotificationParse {
    data object UnsupportedFormat : BankNotificationParse
    data class Parsed(
        val bank: BankSource,
        val amountVnd: NotificationField<Long>,
        val direction: BankDirection,
        val occurredAt: NotificationField<BankStatedMoment>,
        val memo: NotificationField<String>,
    ) : BankNotificationParse
}

fun parseBankNotification(content: PermittedNotificationContent): BankNotificationParse
```

## Gom dòng

Từ `title`, `text`, `bigText` (bỏ `null`):

1. Tách theo `\n`.
2. `trim()` từng dòng (loại `\r`).
3. Bỏ dòng rỗng.
4. `distinct()` — giữ lần xuất hiện đầu, bỏ bản trùng **toàn dòng**.
5. Giữ thứ tự.

Ví dụ cùng một dòng `GD: -1,000` trong `title` và `text` → một dòng.

## Nhận diện định dạng

- Attribution: `^VietinBank\b(.*)$`, `RegexOption.IGNORE_CASE`, áp lên từng dòng.
- Nhãn: `^([A-Za-z]{1,4})\s*:\s*(.*)$`.
- `labelOf(line)` trả nhãn uppercase hoặc `null`.
- Nếu **không** có ít nhất một dòng attribution hoặc **không** có ít nhất một dòng nhãn `GD` → `UnsupportedFormat`.
- Có `GD` với giá trị rỗng vẫn là “có nhãn GD”; định dạng được coi là hỗ trợ, số tiền sẽ `Unreadable`.
- Các nhãn khác (`TK`, `SDC`, `ND`, lạ) không làm thay đổi điều kiện hỗ trợ.

## Số tiền

Lấy **tất cả** dòng nhãn `GD`, giá trị sau dấu `:` đã trim.

Với mỗi giá trị không rỗng, parse:

```text
^([+-])?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(\S*)$
```

- Nhóm 1: dấu tùy chọn.
- Nhóm 2: số có dấu phẩy nhóm nghìn hoặc số trơn.
- Nhóm 3: hậu tố, so uppercase phải thuộc `{"", "VND", "VNĐ", "Đ", "₫"}`.
- Bỏ dấu phẩy, parse `Long`; magnitude phải trong `1..999_999_999_999`.
- Dấu: `-` → `DEBIT`, `+` → `CREDIT`, không dấu → `UNKNOWN`.
- So sánh toàn bộ **cặp (direction, magnitude)**.

Kết quả:

| Tình huống | `amountVnd` | `direction` |
|---|---|---|
| Không có giá trị parse được | `Unresolved(Unreadable)` | `UNKNOWN` |
| Các câu khác nhau | `Unresolved(Ambiguous)` | `UNKNOWN` |
| Đúng một câu | `Present(magnitude)` | theo dấu |

“Khác nhau” nghĩa là khác direction hoặc khác magnitude. Hai dòng y hệt đã bị `distinct()` loại.

`1,250,000` hợp lệ; `1.250.000` không; `1,25,000` không; `1 250 000` không; `100 USD` không; `0` không; `-0` không.

## Thời điểm

Lấy phần sau `VietinBank` trên **mọi** dòng attribution:

1. `groupValues[1].trim().removePrefix(":").trim()`.
2. Bỏ giá trị rỗng.
3. Nếu không còn giá trị → `Missing`.
4. Parse `^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})$`.
5. Ngày phải tồn tại thật (không rollover): `31/02` → không parse.
6. Giờ `00..23`, phút `00..59`.
7. Chuyển sang `BankStatedMoment(date = "yyyy-MM-dd", time = "HH:mm")`, **không** đổi múi giờ, không tạo epoch.
8. Nếu không giá trị nào parse được → `Unresolved(Unreadable)`.
9. Nếu các giá trị parse được khác nhau → `Unresolved(Ambiguous)`.
10. Ngược lại `Present`.

Không chấp nhận giây, timezone, `16-10-2026`, `16/10/26`.

## Memo

Lấy tất cả dòng nhãn `ND`, giá trị trim.

1. `stated = values.filter { it.isNotEmpty() }`.
2. Nếu `stated.isEmpty()` → `Missing` (kể cả khi có dòng `ND:` rỗng).
3. `meaningful = stated.filter { carriesUsableContent(it) }.distinct()`.
4. Nếu `meaningful.isEmpty()` → `Unresolved(Redacted)`.
5. Nếu `meaningful.size > 1` → `Unresolved(Ambiguous)`.
6. Ngược lại `Present(meaningful.single())`.

`carriesUsableContent(text)`:

- Chuẩn hóa bằng cách xóa các ký tự `.`, `*`, `x`, `X`, `-`, `_`, khoảng trắng.
- Nếu kết quả rỗng → không dùng được (redacted).
- Nếu text chứa `redacted` (không phân biệt hoa thường) → không dùng được.
- Ngược lại dùng được.

Ví dụ: `"........"`, `"****"`, `"xxxx"`, `"---"`, `"Redacted"` → redacted. `"Coffee"` → dùng được. `"x"` đơn lẻ → bị coi là redacted (ký tự x bị xóa).

## Ví dụ then chốt

Input:

```text
title: "VietinBank: 16/10/2026 07:38"
text:  "TK: 123456789\nGD: -1,250,000 VND\nSDC: 5,000,000\nND: ........"
```

Kết quả:

```kotlin
BankNotificationParse.Parsed(
    bank = BankSource.VIETINBANK,
    amountVnd = NotificationField.Present(1_250_000L),
    direction = BankDirection.DEBIT,
    occurredAt = NotificationField.Present(BankStatedMoment("2026-10-16", "07:38")),
    memo = NotificationField.Unresolved(UnresolvedReason.Redacted),
)
```

Các trường hợp khác:

| Input rút gọn | Kết quả |
|---|---|
| Không có `VietinBank` | `UnsupportedFormat` |
| Có `VietinBank` nhưng không có `GD` | `UnsupportedFormat` |
| `GD: -1,000` và `GD: -2,000` | amount `Ambiguous`, direction `UNKNOWN` |
| `GD: 1,000` và `GD: 1,000` (khác field) | một `Present(1000)`, direction `UNKNOWN` |
| `GD: 1.250.000` | `Unreadable` |
| `GD: 0` | `Unreadable` |
| `GD: 100 USD` | `Unreadable` |
| `GD: +250,000` | `Present(250000)`, `CREDIT` |
| Không có `ND` | memo `Missing` |
| `ND: Redacted` | memo `Redacted` |
| `ND: Coffee` và `ND: Tea` | memo `Ambiguous` |
| `VietinBank` không kèm giờ | occurredAt `Missing` |
| `VietinBank: 30/02/2026 10:00` | occurredAt `Unreadable` |
| `VietinBank: 16/10/2026 24:00` | occurredAt `Unreadable` |
| Hai attribution khác giờ | occurredAt `Ambiguous` |

## Bất biến

- `Parsed` chỉ xuất hiện khi có attribution và ít nhất một nhãn `GD`.
- `direction` chỉ do dấu của số tiền quyết định; không suy từ memo.
- `amountVnd` không bao giờ âm.
- `occurredAt` không bao giờ là epoch/millis.
- `memo` không bao giờ chứa chuỗi masking.
- Không có exception cho dữ liệu hình dạng hợp lệ; mọi “không đọc được” nằm trong `Unresolved`.
- Với cùng input, kết quả bằng nhau (`data class` equality).

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `title`, `text`, `bigText` đều null | `UnsupportedFormat` |
| Dòng có `\r\n` | trim loại `\r`, parse bình thường |
| `vietinbank` chữ thường | attribution khớp (IGNORE_CASE) |
| `gd:` chữ thường | nhãn uppercase `GD`, khớp |
| `GDX: 100` | nhãn `GDX`, không phải `GD` |
| `GD : 100` | khoảng trắng trước `:` được phép |
| `GD:100` | khớp |
| `GD: 1,000,000.50` | hậu tố `.50` không hợp lệ → `Unreadable` |
| `GD: - 1,000 VND` | dấu rồi khoảng trắng, hợp lệ |
| `GD: 1,000VND` | hợp lệ |
| `GD: 1,000 vnđ` | hợp lệ (uppercase) |
| `ND:` rỗng | `Missing` |
| `ND: . . .` | `Redacted` |
| `ND: xXx` | `Redacted` |
| Hai dòng `GD` giống hệt khác field | dedupe, một câu |
| Dòng `TK:`/`SDC:` | bị bỏ qua, không thành amount/memo |

## Tiêu chí nghiệm thu

1. Ví dụ then chốt khớp từng trường.
2. Bảng trường hợp khác có test tương ứng (ít nhất 12 ca).
3. Không có test nào khẳng định `Parsed` cho input thiếu `GD`.
4. Test dedupe xuyên field.
5. Test ngày không rollover (`30/02`, `31/04`).
6. Test `24:00` bị từ chối.
7. Test dấu `+`/`-`/không dấu.
8. Test memo redacted và ambiguous.
9. `./gradlew test` xanh.

## Non-goals

- Android NotificationListenerService, quyền, redaction đầu vào.
- Chuyển `BankDirection` sang expense/income.
- Nhiều ngân hàng/định dạng.
- Đa tiền tệ, tỷ giá.
- Lưu DB hoặc hiển thị UI.
- Suy ra múi giờ hoặc epoch.
