# 53 — Cổng nhà cung cấp có che thông tin

## Mục tiêu

Cài đúng **một** cửa ngõ cho mọi lời gọi nhà cung cấp: che prompt trước khi gửi, quét phản hồi trước khi trả, chặn nếu phát hiện rò, và khoá cache **không mang giá trị gốc**.

1. `MaskingBoundary` thay giá trị nhạy cảm bằng token ổn định (`[[PERSON_1]]`) theo kiểu che đã chọn.
2. `MaskedGateway.complete(prompt)` là đường duy nhất; adapter bên trong là `private` và **không** có getter.
3. Quét phản hồi: có giá trị gốc chưa che ⇒ ném `MaskingBlockedException`, **không** cache, không trả một phần.
4. `cacheKeyFor(...)` chỉ phụ thuộc `policyVersion`, `modelId` và **văn bản đã che**.
5. Chạy bộ tự kiểm tra bằng Kotlin thuần, không phụ thuộc thư viện test.

## Giá trị

- "Không có đường vòng" là thuộc tính kiến trúc, không phải quy ước: nếu adapter có getter công khai, mọi lời hứa về che dữ liệu đều vô nghĩa. Bài tập kiểm tra điều này bằng reflection/compile.
- Khoá cache là nơi rò dữ liệu tinh vi: nếu khoá băm cả prompt gốc, bạn vừa lưu dấu vết giá trị nhạy cảm trong bộ nhớ dài hạn.
- Kiểm tra phản hồi (không chỉ prompt) là bước nhiều hệ thống bỏ qua: mô hình có thể lặp lại dữ liệu đã thấy trong huấn luyện hoặc trong ngữ cảnh.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Kotlin/JVM, chỉ thư viện chuẩn (`java.security.MessageDigest`) |
| Độ khó | Trung bình–Khó |
| Điều kiện | Kotlin cơ bản, `private`, `data class`, băm SHA-256, chạy `kotlinc`/`java` |
| Runtime | JDK 17+ và `kotlinc` 1.9+; không Gradle, không mạng, không GPU |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/aegis-f` (nhánh `main`; REST payload ghi `"archived": true`)
- File nguồn: <https://github.com/triet4p/aegis-f/blob/main/app/src/main/java/io/github/triet4p/aegisf/privacy/MaskedHostedGateway.kt>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Lớp bọc quanh adapter cộng `MaskedPromptBoundary`, có `scan(rawResponse, httpStatus)` và ném `MaskingBlockedException`.
  - Nguyên tắc: *"Mask or block is the rule … There is intentionally no raw passthrough: the wrapped adapter is private and never exposed"*.
  - `cacheKeyFor(...)` chỉ mang "identity giá trị-trống".
- Giới hạn bằng chứng: đọc 70 dòng đầu; không quan sát được toàn bộ `MaskedPromptBoundary`, chính sách che, hay hình dạng adapter.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: một lớp bọc duy nhất; adapter private, không lộ; `scan` phản hồi và ném `MaskingBlockedException`; khoá cache không mang giá trị gốc; nguyên tắc "che hoặc chặn".

Phần **do bài tập định nghĩa**:

- Định dạng vault, thuật toán thay thế (khớp dài nhất trước, token theo thứ tự vault).
- Hai chế độ che: `INDEXED` (token có số) và `BLANK` (mọi giá trị cùng loại về một token) — để chứng minh "value-blank identity".
- Thành phần khoá cache và phiên bản chính sách.
- Hành vi khi rò: ném lỗi, không cache, không trả một phần; thông điệp lỗi **không** chứa giá trị gốc.
- Định dạng fixture, bộ tự kiểm tra, mã thoát.

Nguồn **không** bao gồm: HTTP client, nhà cung cấp thật, hay chính sách che cụ thể của sản phẩm.

## Phạm vi

Trong phạm vi:

- Vault ≤ 20 giá trị, ba loại (`PERSON`, `EMAIL`, `ID`).
- `ProviderAdapter` là interface một phương thức `complete(masked: String): String`; cài đặt mẫu trả chuỗi từ fixture (có thể cố ý rò).
- Bộ tự kiểm tra chạy bằng `main`, in `PASS`/`FAIL` cho từng ca, mã thoát `1` nếu có `FAIL`.

Ngoài phạm vi:

- Không gọi mạng, không SDK nhà cung cấp, không xử lý hình ảnh.
- Không che xác suất/phát hiện thực thể bằng ML; chỉ khớp chuỗi từ vault.
- Không có TTL/giới hạn kích thước cache thật (dùng `MutableMap` trong bộ nhớ).

## Cảnh báo production

- Khớp chuỗi theo vault chỉ bắt được giá trị **đã biết**. Một tên chưa có trong vault sẽ lọt; sản phẩm thật cần bộ phát hiện thực thể và chính sách mặc định.
- `BLANK` làm giảm rò qua cache nhưng tăng khả năng cache trả sai ngữ cảnh (hai prompt khác nhau cùng khoá). Bài tập chỉ dùng để chứng minh tính chất, không khuyến nghị cho production.
- Không log prompt/response; thông điệp lỗi cũng phải không chứa giá trị gốc — đây là điểm dễ vi phạm nhất khi thêm debug.
- Băm SHA-256 không mã hoá: khoá cache vẫn có thể bị đối chiếu nếu đầu vào đủ nhỏ. Đừng coi khoá là "an toàn".

## Fixture offline

- `fixtures/vault.txt` — mỗi dòng `TYPE|value`, thứ tự quyết định số token.
- `fixtures/cases.txt` — không bắt buộc; bộ tự kiểm tra có thể nhúng chuỗi.
- Không có URL ngoài, không biến môi trường, không khoá API.

## Liên kết

- [SPEC.md](SPEC.md) — thuật toán che, quét, khoá cache, ví dụ chuỗi chính xác, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế cửa ngõ kín, bẫy rò qua lỗi/log, cách kiểm chứng.
