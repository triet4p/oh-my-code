# GUIDE 53 — Cổng nhà cung cấp có che thông tin

## 1. Tính chất cần đạt, không phải tính năng

Bài này không hỏi "che có đúng không" (dễ), mà hỏi ba tính chất khó hơn:

1. **Không có đường vòng**: không thể lấy adapter, không thể gọi nhà cung cấp mà bỏ qua che.
2. **Che hoặc chặn**: không có nhánh "trả nguyên bản".
3. **Khoá cache không mang giá trị**: hai giá trị khác nhau che giống nhau ⇒ cùng khoá.

Mỗi tính chất cần một ca kiểm tra riêng, và cả ba đều có thể bị phá bởi một dòng code "tiện tay".

## 2. Thiết kế Kotlin

```text
src/
├── Vault.kt          # data class VaultEntry(type, value, index); load()
├── Masking.kt        # MaskMode, MaskingPolicy, MaskedText, MaskingBoundary
├── Gateway.kt        # ProviderAdapter, MaskedResponse, MaskedGateway
├── SelfCheck.kt      # 12+ ca, in PASS/FAIL
└── Main.kt           # đọc vault, chạy SelfCheck, exit code
```

### 2.1 Đóng kín bằng từ khoá, không bằng quy ước

```kotlin
class MaskedGateway(
    private val adapter: ProviderAdapter,
    private val boundary: MaskingBoundary,
    private val policy: MaskingPolicy
)
```

Ba điểm:

- `private val` trong primary constructor tạo **field private, không getter** — đây chính là điều SPEC yêu cầu.
- `class` không `open`: không subclass để lộ.
- Không khai báo `val maskedAdapter get() = adapter`.

Nếu bạn cần test adapter, hãy truyền một adapter **đếm** từ ngoài và giữ tham chiếu ở phía test, không lấy từ gateway.

## 3. Thứ tự cài đặt

### Bước 1 — Masking

Viết `mask(text: String): MaskedText`.

Cách làm gợi ý (không phải lời giải đầy đủ):

1. Sắp `entries` một lần khi dựng boundary: `sortedWith(compareByDescending<VaultEntry> { it.value.length }.thenBy { it.index })`.
2. Duyệt `i` từ 0; với mỗi entry thử `text.startsWith(entry.value, i)`; entry đầu tiên khớp thì ghi token, `i += entry.value.length`; nếu không khớp entry nào, `append(text[i]); i++`.

Đừng dùng `text.replace(value, token)` lặp qua vault: nó thay **mọi** vị trí cùng lúc và có thể thay vào trong token vừa sinh nếu giá trị là chuỗi con của tên loại. Ví dụ vault có `EMAIL` là giá trị (không hợp lệ theo SPEC nhưng dễ xảy ra khi mở rộng) sẽ phá token `[[EMAIL_1]]`.

### Bước 2 — Scan

Duyệt cùng danh sách đã sắp; với mỗi entry, `indexOf` lặp để tìm mọi vị trí, nhưng bỏ qua nếu vị trí nằm trong một đoạn đã khớp bởi entry dài hơn. Một cách rẻ: duyệt giống `mask` nhưng thay vì ghi token thì ghi `Leak` khi khớp.

Quan trọng: `Leak` chứa `(type, index, token)`, **không** chứa `value`. Nếu bạn để `data class Leak(val value: String, ...)` rồi in ra trong exception, bạn vừa làm rò đúng thứ mình đang bảo vệ.

### Bước 3 — Khoá cache

```kotlin
fun cacheKeyFor(masked: MaskedText, modelId: String): String {
    val digest = MessageDigest.getInstance("SHA-256")
    val bytes = digest.digest("${policy.version}|$modelId|${masked.value}".toByteArray(Charsets.UTF_8))
    return bytes.joinToString("") { "%02x".format(it) }
}
```

`"%02x".format(it)` với `Byte` âm cần cẩn thận: dùng `it.toInt() and 0xff` hoặc `"%02x".format(it.toInt() and 0xff)`. Nếu không, bạn nhận chuỗi dài hơn 64 ký tự.

### Bước 4 — Complete

Giữ thứ tự 1–8 của SPEC. Điểm dễ sai: **bước 7 che cả phản hồi**. Nhiều cài đặt chỉ che prompt rồi trả nguyên phản hồi — đó là lỗi bảo mật, không phải lỗi thẩm mỹ.

Nếu bạn cache **trước** khi scan, phản hồi rò sẽ nằm trong cache và lần sau được trả mà không bị chặn. SPEC cấm; test 7.8 bắt.

### Bước 5 — Bộ tự kiểm tra

Viết một `check(name, block)` nhận lambda trả `Boolean`, in `PASS name` hoặc `FAIL name`, đếm fail. `main` trả `exitProcess(if (fails == 0) 0 else 1)`.

12 ca tối thiểu: A, B, C, chồng lấn, D, E, F, khoá bằng, khoá khác version, BLANK cùng khoá, adapter ném ngoại lệ, reflection không lộ adapter.

## 4. Cạm bẫy

- **`replace` toàn cục**: thay cả trong token hoặc thay chồng lấn.
- **Sắp theo thứ tự file thay vì độ dài**: `"Nguyen Van A"` sẽ khớp trước `"Nguyen Van An"` nếu nó đứng trước, để lại `"n"` thừa.
- **So khớp không phân biệt hoa thường**: làm tăng phủ nhưng phá tính tất định của ví dụ; SPEC chọn phân biệt.
- **Token dựa trên lần xuất hiện**: cùng một người ở hai vị trí sẽ ra hai token khác nhau ⇒ khoá cache không ổn định. SPEC gán theo vault.
- **Đưa `prompt` gốc vào khoá**: rò qua bộ nhớ cache và phá tính "value-blank".
- **Đưa timestamp vào khoá**: cache vô dụng.
- **`Exception` thay vì `MaskingBlockedException`**: người gọi không phân biệt được "bị chặn" với "lỗi mạng", và có thể retry rồi vô tình gửi lại dữ liệu.
- **Log `raw` trong catch**: rò nghiêm trọng. Chỉ log `leaks.size` và token.
- **`private val` nhưng có `internal` getter**: reflection test sẽ thấy.

## 5. Kiểm thử

| Ca | Khẳng định |
|---|---|
| A/B/C | chuỗi che đúng từng ký tự |
| overlap | `Nguyen Van An` chọn mục dài |
| D | trả `MaskedResponse`, `cacheSize` tăng |
| E | ném `MaskingBlockedException`, thông điệp không chứa email, `cacheSize` không đổi |
| F | token không bị coi là rò |
| key_same | hai lần A ⇒ cùng khoá |
| key_version | đổi `version` ⇒ khác khoá |
| key_blank | hai email khác nhau ⇒ cùng khoá (BLANK) |
| key_shape | 64 ký tự hex |
| adapter_throws | ngoại lệ truyền ra, không cache |
| no_leak_api | reflection: không thành viên công khai nào trả `ProviderAdapter`, không tên chứa `raw` |

## 6. Kiểm chứng độc lập

```bash
javac -version 2>&1 | head -1   # hoặc: java -version
kotlinc -version                # >= 1.9
kotlinc src -include-runtime -d build/gateway.jar
java -jar build/gateway.jar fixtures/vault.txt; echo "exit=$?"
```

Kỳ vọng: in 12 dòng `PASS` và `exit=0`. Nếu có `FAIL`, đọc tên ca rồi đối chiếu SPEC.

Kiểm tra nhanh không lộ adapter (grep):

```bash
grep -n "fun .*adapter\|val adapter" src/*.kt
```

Chỉ được thấy dòng khai báo `private val adapter`.

## 7. Gợi ý

- Viết `tokenFor(entry)` một lần, dùng cho cả `mask` và `scan` (scan cần token để báo lỗi).
- Viết `Leak.toString()` chỉ in `"TYPE#index"`; đừng dựa vào `data class` mặc định nếu nó chứa trường nhạy cảm.
- Với reflection, kiểm tra cả `MaskedGateway::class.declaredMemberProperties` và `javaClass.methods.map { it.returnType }`.
- Dùng `buildString` thay vì nối chuỗi trong vòng lặp — dễ đọc và nhanh hơn.

## 8. Mở rộng

- **Che theo từ điển động**: thêm giá trị mới vào vault trong runtime và kiểm tra token cũ không đổi (ổn định theo index).
- **Chính sách theo loại**: `EMAIL` → BLANK, `PERSON` → INDEXED; kiểm tra khoá cache theo từng loại.
- **TTL cache**: thêm `clock` tiêm được để test hết hạn mà không `sleep`.
- **Đếm rò**: thay vì chặn, trả `MaskedResponse` kèm cờ `blocked` trong môi trường đo lường — nhưng phải nằm sau cờ biên dịch, không phải đường mặc định.
- **So sánh với regex**: cài bản dùng regex với alternation sắp theo độ dài; so hành vi và tốc độ trên 10.000 ký tự.
