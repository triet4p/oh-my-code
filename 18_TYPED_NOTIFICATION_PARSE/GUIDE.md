# GUIDE — Typed bank notification parse

## Bước 0 — Project Kotlin/JVM

```bash
mkdir 18_TYPED_NOTIFICATION_PARSE/work && cd 18_TYPED_NOTIFICATION_PARSE/work
gradle init --type kotlin-library --dsl kotlin
```

Hoặc tạo tay:

```text
build.gradle.kts
settings.gradle.kts
src/main/kotlin/banknotify/Types.kt
src/main/kotlin/banknotify/Parser.kt
src/test/kotlin/banknotify/ParserTest.kt
```

`build.gradle.kts` cần plugin `kotlin("jvm")`, `kotlin("plugin.serialization")` không cần, và:

```kotlin
dependencies {
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.0")
}
tasks.test { useJUnitPlatform() }
```

Không thêm Android.

## Bước 1 — Thiết kế kiểu trước

Viết `Types.kt`:

- `sealed interface NotificationField<out T>` với `out` để `NotificationField<Long>` dùng được như `NotificationField<Number>` nếu cần.
- `Present<T>`, `Unresolved` (không generic), `Missing` (`data object`).
- `BankStatedMoment` là `data class` với hai string; không thêm `Instant`.
- `Parsed` là `data class`; `UnsupportedFormat` là `data object`.

Tại sao `data object`? Equality và `toString` ổn định, không tạo nhiều instance.

## Bước 2 — Gom dòng

```text
private fun PermittedNotificationContent.postedLines(): List<String> =
    listOfNotNull(title, text, bigText)
        .flatMap { it.split('\n') }
        .map { it.trim() }
        .filter { it.isNotEmpty() }
        .distinct()
```

`trim()` xử lý `\r` từ CRLF. `distinct()` giữ thứ tự lần đầu.

Không dùng `split(Regex("\\R"))` nếu muốn bám nguồn; `\n` + trim là đủ. Nếu dùng, ghi rõ.

## Bước 3 — Regex

```text
private val ATTRIBUTION = Regex("^VietinBank\\b(.*)$", RegexOption.IGNORE_CASE)
private val LABELLED = Regex("^([A-Za-z]{1,4})\\s*:\\s*(.*)$")
```

`matchEntire` hay `matches` để neo hai đầu. Nếu dùng `find`, `^...$` vẫn neo nhưng dễ nhầm với multiline; dùng `matchEntire`.

`labelOf`: `LABELLED.matchEntire(line)?.groupValues?.get(1)?.uppercase()`.

`IGNORE_CASE` chỉ áp cho attribution; nhãn `[A-Za-z]` đã bao cả hai, sau đó uppercase.

## Bước 4 — Số tiền

Tách giá trị:

```text
private fun labelledValues(lines: List<String>, label: String): List<String> =
    lines.mapNotNull { line ->
        val m = LABELLED.matchEntire(line) ?: return@mapNotNull null
        if (m.groupValues[1].uppercase() != label) return@mapNotNull null
        m.groupValues[2].trim()
    }
```

Parse:

```text
private val AMOUNT = Regex("^([+-])?\\s*(\\d{1,3}(?:,\\d{3})+|\\d+)\\s*(\\S*)$")
```

- `matchEntire`.
- Suffix `groupValues[3].uppercase()` trong set. Lưu ý `₫` uppercase vẫn là `₫`; `Đ` uppercase là `Đ`.
- `groupValues[2].replace(",", "").toLongOrNull()`.
- Kiểm tra `1..999_999_999_999`.
- Direction.

So sánh câu: dùng `data class StatedAmount(direction, magnitude)` và `distinct()`.

Thứ tự xử lý: lọc giá trị rỗng → parse → nếu danh sách parse rỗng thì `Unreadable`; nếu distinct >1 thì `Ambiguous`; còn lại `Present`.

Một cái bẫy: `values` có thể chứa `""` nếu dòng `GD:`; `statedAmount("")` trả `null`, đừng ném.

## Bước 5 — Ngày giờ

Dùng `java.time.LocalDate` với `DateTimeFormatter` strict:

```text
private val MOMENT = Regex("^(\\d{2})/(\\d{2})/(\\d{4})\\s+(\\d{2}):(\\d{2})$")
```

Sau khi khớp, tạo chuỗi `"yyyy-MM-dd"` và `"HH:mm"`, rồi:

```text
try {
    LocalDate.parse(dateText)   // ISO_LOCAL_DATE, strict
    LocalTime.parse(timeText)   // HH:mm
} catch (e: DateTimeParseException) { return null }
```

`LocalDate.parse("2026-02-30")` ném (strict), khác JavaScript. `LocalTime.parse("24:00")` ném.

Không dùng `SimpleDateFormat` (lenient mặc định, dễ rollover).

Đừng chuyển sang `Instant`; đó là quyết định của lớp lưu trữ sau khi người dùng xác nhận, không phải parser.

## Bước 6 — Memo

```text
private fun carriesUsableContent(text: String): Boolean {
    if (text.contains("redacted", ignoreCase = true)) return false
    val stripped = text.filterNot { it in ".*xX-_ \t" }
    return stripped.isNotEmpty()
}
```

Có thể dùng regex `[.*xX\\-_\\s]`. Kiểm tra `"x"` đơn lẻ → rỗng → redacted, đúng SPEC.

Thứ tự: kiểm tra “redacted” trước hay sau khi xóa cũng được; nếu chuỗi `"redacted"` bị xóa một phần? Không, chữ cái còn lại. Kiểm tra trước rõ hơn.

## Bước 7 — Hàm parse

```text
fun parseBankNotification(content: PermittedNotificationContent): BankNotificationParse {
    val lines = content.postedLines()
    val hasAttribution = lines.any { ATTRIBUTION.containsMatchIn(it) }
    val hasGd = lines.any { labelOf(it) == "GD" }
    if (!hasAttribution || !hasGd) return UnsupportedFormat
    ...
}
```

`containsMatchIn` với regex có `^`/`$` hoạt động trên toàn chuỗi? `containsMatchIn` tìm khớp con; với `^...$` và không MULTILINE, nó khớp toàn chuỗi. An toàn hơn: `ATTRIBUTION.matchEntire(it) != null`.

Sau đó tính từng trường và trả `Parsed`.

## Bước 8 — Test

Dùng `kotlin.test` + JUnit 5:

- Helper `parse(title, text, bigText)`.
- So sánh `Parsed` bằng `assertEquals` (data class).
- Với `Present`, so `value`.
- Với `Unresolved`, so `reason`.
- Với `Missing`, so object.

Các ca tối thiểu: 12 ca trong bảng SPEC + ví dụ chính + dedupe + ngày + memo.

Một cái bẫy: Kotlin không có `assertInstanceOf` mặc định; dùng `assertIs<NotificationField.Present<Long>>(field)` (kotlin.test) rồi `assertEquals`.

## Bước 9 — Kiểm chứng độc lập

```bash
./gradlew test
./gradlew build
```

Nếu dùng `gradle init` có application plugin, có thể thêm `main` in kết quả parse một fixture; nhưng test là đủ.

Kiểm tra ngày:

```bash
./gradlew test --tests "*rejectsImpossibleDate*"
```

## Bước 10 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `Parsed` cho thông báo khác ngân hàng | Chỉ kiểm tra có `GD`, quên attribution. |
| `GD:` rỗng làm `UnsupportedFormat` | `labelOf` yêu cầu value không rỗng; sửa regex/logic. |
| `1,000` parse thành 1 | Dùng `split(",")[0]` thay vì bỏ dấu phẩy. |
| `+1,000` ra `UNKNOWN` | Quên nhóm dấu. |
| `100 USD` lọt | Không kiểm tra suffix. |
| 31/02 lọt | `SimpleDateFormat` lenient. |
| 24:00 lọt | Dùng regex giờ `\d{2}` mà không parse `LocalTime`. |
| Memo `"........"` thành Present | Thiếu redaction. |
| Memo `ND:` thành Redacted | Bạn lọc rỗng trước khi quyết định Missing. |
| Dedupe sai | Dùng `toSet()` không giữ thứ tự hoặc không distinct. |
| Hai dòng tiền giống nhau thành Ambiguous | So sánh chuỗi thay vì cặp (direction, magnitude). |
| `₫` bị từ chối | Uppercase/lowercase mismatch. |

## Bước 11 — Mở rộng

- Thêm ngân hàng thứ hai với grammar riêng, vẫn `UnsupportedFormat` cho phần còn lại.
- Thêm `currency` và từ chối phi VND rõ ràng hơn.
- Thêm `rawLine` provenance cho từng trường.
- Thêm chuyển `BankDirection` sang ledger **sau** xác nhận người dùng.
- Thêm property-based test cho số tiền.

## Tự đánh giá

1. Vì sao `Missing` khác `Unresolved(Redacted)`?
2. Vì sao không lưu epoch từ parser?
3. Vì sao phải so cặp (direction, magnitude) khi phát hiện mơ hồ?
4. Vì sao `LocalDate` strict quan trọng hơn regex?
