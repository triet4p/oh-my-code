# SPEC 53 — Cổng nhà cung cấp có che thông tin

## 1. Vault và token

### 1.1 File

`fixtures/vault.txt`, mỗi dòng `TYPE|value`:

```text
PERSON|Nguyen Van A
PERSON|Tran B
EMAIL|a@example.com
EMAIL|b@example.com
ID|123456789
```

- `TYPE` thuộc `PERSON`, `EMAIL`, `ID`.
- `value` không rỗng, không chứa `|`.
- Thứ tự dòng quyết định số hiệu token.

### 1.2 Token

| Chế độ | Token cho dòng thứ `n` cùng `TYPE` |
|---|---|
| `INDEXED` | `[[TYPE_n]]` với `n` bắt đầu từ 1 theo thứ tự file |
| `BLANK` | `[[TYPE]]` cho mọi dòng cùng `TYPE` |

Ví dụ vault trên: `PERSON|Nguyen Van A` → `[[PERSON_1]]`; `EMAIL|b@example.com` → `[[EMAIL_2]]` (INDEXED) hoặc `[[EMAIL]]` (BLANK).

## 2. Che văn bản

```text
mask(text) -> MaskedText(value: String, tokens: List<String>)
```

Thuật toán:

1. Sắp các mục vault theo `(độ dài value giảm dần, chỉ số dòng tăng dần)`.
2. Quét `text` từ trái sang phải; tại mỗi vị trí, thử khớp mục đầu tiên trong danh sách đã sắp; nếu khớp, ghi token và nhảy qua độ dài khớp; nếu không, chép một ký tự và tiến 1.
3. So khớp **phân biệt hoa thường**, theo codepoint, không chuẩn hoá Unicode.

Hệ quả: mục dài hơn thắng khi cùng điểm bắt đầu; không có thay thế chồng lấn.

`tokens` là danh sách token **theo thứ tự xuất hiện**, có thể trùng (mỗi lần xuất hiện một phần tử).

### 2.1 Ví dụ

`vault` ở 1.1, chế độ `INDEXED`, `text = "Nguyen Van A gửi email tới a@example.com"`:

```text
masked  = "[[PERSON_1]] gửi email tới [[EMAIL_1]]"
tokens  = ["[[PERSON_1]]", "[[EMAIL_1]]"]
```

Chế độ `BLANK`, cùng text:

```text
masked  = "[[PERSON]] gửi email tới [[EMAIL]]"
```

### 2.2 Chồng lấn

Vault có `PERSON|Nguyen Van A` và `PERSON|Nguyen Van An`; text `"Nguyen Van An"` ⇒ khớp mục dài hơn ⇒ token của `Nguyen Van An`, phần còn lại không bị cắt.

## 3. Quét phản hồi

```text
scan(rawResponse: String) -> List<Leak>
```

`Leak(type: String, index: Int, token: String)` — **không** chứa giá trị gốc.

Một `Leak` được ghi khi `value` của mục vault xuất hiện **nguyên vẹn** trong `rawResponse`. Quét theo cùng thứ tự ưu tiên (dài trước) và không tính chồng lấn hai lần trên cùng một đoạn.

- Token `[[PERSON_1]]` **không** bị coi là rò dù chứa chữ `PERSON`.
- Nếu `rawResponse` chứa cả `a@example.com` và `b@example.com` ⇒ hai `Leak`.

## 4. Cổng

```kotlin
class MaskedGateway(
    private val adapter: ProviderAdapter,
    private val boundary: MaskingBoundary,
    private val policy: MaskingPolicy
) {
    fun complete(prompt: String): MaskedResponse
    fun cacheKeyFor(masked: MaskedText, modelId: String): String
}
```

Ràng buộc cấu trúc (kiểm tra bằng đọc mã và bằng reflection trong bộ tự kiểm tra):

- `adapter` là `private val`, **không** có getter công khai, không xuất hiện trong bất kỳ kiểu trả về nào.
- `MaskedGateway` là `class` (không `open`), không expose `ProviderAdapter`.
- Không có phương thức `rawComplete`, `unsafeComplete`, hay tương đương.

### 4.1 `complete`

```text
1. masked = boundary.mask(prompt)
2. key = cacheKeyFor(masked, policy.modelId)
3. nếu cache có key: trả bản đã lưu
4. raw = adapter.complete(masked.value)
5. leaks = boundary.scan(raw)
6. nếu leaks không rỗng: ném MaskingBlockedException(leaks)   // KHÔNG cache
7. response = MaskedResponse(boundary.mask(raw).value, key)
8. cache[key] = response; trả response
```

- Bước 7 che cả phản hồi trước khi trả: người gọi không bao giờ nhận giá trị gốc.
- `MaskingBlockedException.message` chỉ nêu `"blocked: EMAIL#1"` (loại + số hiệu), **không** nêu giá trị.
- Nếu adapter ném ngoại lệ, không cache, ngoại lệ truyền nguyên.

### 4.2 `cacheKeyFor`

```text
key = sha256Hex("${policy.version}|${modelId}|${masked.value}")
```

Chỉ ba thành phần. **Không** có prompt gốc, không có vault, không có timestamp, không có giá trị bị che.

Hệ quả bắt buộc: hai prompt khác nhau nhưng che ra cùng `masked.value` (ví dụ chế độ `BLANK` với hai email khác nhau) phải cho **cùng** khoá.

### 4.3 `MaskingPolicy`

```text
data class MaskingPolicy(
    val mode: MaskMode,        // INDEXED | BLANK
    val version: String,       // ví dụ "v1"
    val modelId: String        // ví dụ "toy-model"
)
```

## 5. Ví dụ số

Vault 1.1, `policy = (INDEXED, "v1", "toy-model")`.

| Ca | Prompt | `masked.value` | Ghi chú |
|---|---|---|---|
| A | `"Nguyen Van A gửi email tới a@example.com"` | `"[[PERSON_1]] gửi email tới [[EMAIL_1]]"` | hai token |
| B | `"Tran B"` | `"[[PERSON_2]]"` | số hiệu theo vault, không theo lần gặp |
| C | `"Nguyen Van A và Nguyen Van A"` | `"[[PERSON_1]] và [[PERSON_1]]"` | lặp token |

| Ca | Phản hồi từ adapter | Kết quả |
|---|---|---|
| D | `"Giá là 10"` | trả `MaskedResponse("Giá là 10", key)` |
| E | `"Liên hệ a@example.com"` | ném `MaskingBlockedException` với `EMAIL#1` |
| F | `"Token [[EMAIL_1]] không phải rò"` | trả bình thường |

Khoá cache:

- Với A ở `INDEXED`: `key_A = sha256("v1|toy-model|[[PERSON_1]] gửi email tới [[EMAIL_1]]")`.
- Ở `BLANK`, prompt `"a@example.com"` và `"b@example.com"` đều che thành `"[[EMAIL]]"` ⇒ **cùng khoá**.
- Đổi `version` sang `"v2"` ⇒ khoá khác.

Bộ tự kiểm tra không cần in hex cụ thể; nó khẳng định **quan hệ** bằng nhau/khác nhau và độ dài 64 ký tự hex.

## 6. Kiểm tra hợp lệ

| Điều kiện | Lỗi |
|---|---|
| dòng vault sai định dạng hoặc `TYPE` lạ | `InvalidVault(line)` |
| vault rỗng | `EmptyVault` |
| `version` rỗng | `InvalidPolicy` |
| `text` null (nếu dùng Java interop) | `NullInput` |
| `scan` phát hiện rò | `MaskingBlockedException` (không phải `IllegalStateException`) |

## 7. Tiêu chí chấp nhận

1. Bộ tự kiểm tra in `PASS` cho tối thiểu 12 ca, gồm A–F, chồng lấn 2.2, khoá cache bằng nhau/khác nhau, và ca adapter ném ngoại lệ.
2. `mask` cho A, B, C đúng từng ký tự như bảng 5.
3. `scan` phát hiện đúng E; F không bị chặn.
4. `MaskingBlockedException.message` không chứa `a@example.com` (kiểm tra bằng `contains`).
5. Không có cách nào lấy `raw` từ gateway: bộ tự kiểm tra dùng reflection liệt kê thành viên công khai và khẳng định không có getter trả `ProviderAdapter`, không có hàm tên chứa `raw`.
6. Khoá cache: A và A ⇒ bằng; A với `version = "v2"` ⇒ khác; BLANK với hai email khác nhau ⇒ bằng; độ dài 64, chỉ ký tự hex.
7. Complete gọi adapter **một lần** cho mỗi khoá chưa có (đếm trong adapter giả).
8. Khi bị chặn, cache không có mục mới (kiểm tra `cacheSize` qua hàm chỉ đọc).
9. `kotlinc ... && java -jar ...` chạy được, mã thoát `0`, không cần mạng.

## 8. Non-goals

- Không gọi mạng; không SDK; không xử lý ảnh/âm thanh.
- Không phát hiện thực thể bằng ML; chỉ khớp vault.
- Không TTL/giới hạn kích thước cache thật; không đa luồng.
