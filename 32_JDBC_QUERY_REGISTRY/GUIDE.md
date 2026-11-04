# GUIDE 32 — Thiết kế registry và DAO

## 1. Kiến trúc

```
src/main/java/notes/
├─ QueryRegistry.java
├─ QueryRegistryException.java
├─ BasicDao.java
└─ RegistryPrinter.java
src/test/java/notes/
├─ QueryRegistryTest.java
└─ BasicDaoTest.java
fixtures/
```

Không dùng Maven/Gradle bắt buộc; có thể biên dịch bằng `javac` và chạy `TestMain` với `assert` bật `-ea`. Nếu dùng JUnit, thêm dependency là lựa chọn của bạn.

## 2. Parser

Gợi ý trạng thái:

```java
String currentName = null;
StringBuilder body = new StringBuilder();
boolean seenName = false;
for (line : lines) {
    Matcher m = DIRECTIVE.matcher(line);
    if (m.matches()) {
        flush(currentName, body);      // nếu currentName != null
        currentName = m.group(1);
        validateName(currentName);
        body.setLength(0);
        seenName = true;
    } else if (!seenName && !isBlankOrComment(line)) {
        throw new QueryRegistryException("SQL before first query name");
    } else if (seenName) {
        body.append(line).append('\n');
    }
}
flush(currentName, body);
```

`flush`: nếu body trim rỗng → lỗi; nếu key trùng → lỗi; lưu `body.toString().trim()`.

**Bẫy:** directive phải khớp cả dòng. Dùng `matches()`, không `find()`. Nếu dùng `find()`, dòng SQL chứa `-- name:` sẽ bị cắt.

Directive regex:

```java
Pattern.compile("^--\\s*name:\\s*([A-Za-z][A-Za-z0-9_.-]{0,63})\\s*$", Pattern.CASE_INSENSITIVE)
```

`CASE_INSENSITIVE` áp cho cả key; nếu muốn key phân biệt hoa thường, dùng inline flag chỉ cho `name`: `(?i:name)`. Gợi ý: `^--\\s*(?i:name):\\s*...`.

## 3. Đọc file

- `Files.readAllBytes`, kiểm tra kích thước ≤ 1 MiB.
- Bỏ BOM: nếu 3 byte đầu là `EF BB BF`, bỏ.
- `new String(bytes, StandardCharsets.UTF_8)` — Java thay thế byte sai bằng U+FFFD; nếu muốn chặt, dùng `CharsetDecoder` với `CodingErrorAction.REPORT`. Bài yêu cầu chặt: lỗi `MalformedInputException` bọc trong `QueryRegistryException`.
- `split("\\R", -1)` để giữ dòng cuối.

## 4. DAO

```java
public PreparedStatement getPrepareStatement(String type) throws SQLException {
    if (connection == null) throw new SQLException("Connection null!");
    if (registry == null) throw new SQLException("Query registry not loaded");
    String sql = registry.sqlFor(type);   // ném Unsupported Query Type
    return connection.prepareStatement(sql);
}
```

Overload:

```java
if (mode != Statement.RETURN_GENERATED_KEYS && mode != Statement.NO_GENERATED_KEYS)
    throw new IllegalArgumentException("Unsupported auto-generated keys mode");
...
return connection.prepareStatement(sql, mode);
```

Không gọi `connection.prepareStatement` trước khi validate mode: test sẽ kiểm tra connection không bị chạm.

## 5. Test không cần DB

Có hai cách:

1. **Proxy JDK** cho `Connection`/`PreparedStatement`:
   - `Proxy.newProxyInstance` với `InvocationHandler`;
   - khi method `prepareStatement`, ghi lại `sql`/`mode`, trả một proxy `PreparedStatement`;
   - các method khác trả giá trị mặc định hoặc ném `UnsupportedOperationException`.
2. **Adapter tối giản** quanh `Connection` nếu bạn muốn tránh proxy; nhưng sẽ khác JDK.

Gợi ý dùng proxy; nó cũng dạy cách test code phụ thuộc interface lớn.

Kiểm tra connection null: `dao.setConnection(null)` hoặc không set.

## 6. Bẫy thường gặp

- **Dùng `find()` cho directive**: cắt nhầm SQL.
- **Không flush khối cuối**: mất query cuối.
- **Không kiểm tra khối rỗng**: registry có key với SQL rỗng, lỗi muộn ở DB.
- **Trim mất dấu `;`**: không sai nếu test nhất quán, nhưng phải định nghĩa. Bài giữ `;`.
- **Directive thụt lề**: không khớp `^`; đúng thiết kế.
- **Key trùng sau khi lower**: nếu regex case-insensitive không ảnh hưởng group, key giữ nguyên; trùng chính xác mới lỗi.
- **Registry trả map sửa được**: người dùng đổi SQL; trả `Collections.unmodifiableMap`.
- **Kiểm tra key trước connection**: sai thứ tự so với nguồn.
- **Overload gọi nhầm `prepareStatement(sql)`**: mất auto keys.
- **Nhúng credential**: không làm; đọc từ môi trường nếu mở rộng.

## 7. Gỡ lỗi

- In registry key + độ dài SQL, không in toàn SQL nếu nhạy cảm.
- Test từng fixture lỗi, so message chính xác.
- Kiểm tra `keys()` không sửa được bằng `assertThrows`.
- Kiểm tra `prepareStatement` nhận đúng chuỗi (so cả `;`).
- Chạy với `-ea` để bật assert.

## 8. Kiểm chứng

```bash
cd 32_JDBC_QUERY_REGISTRY
mkdir -p out
javac -encoding UTF-8 -d out $(find src/main/java -name '*.java')
java -cp out notes.RegistryPrinter fixtures/notes.sql
```

Windows PowerShell:

```powershell
javac -encoding UTF-8 -d out (Get-ChildItem -Recurse src/main/java -Filter *.java).FullName
java -cp out notes.RegistryPrinter fixtures/notes.sql
```

Test (nếu có `TestMain`):

```bash
javac -encoding UTF-8 -cp out -d out-test $(find src/test/java -name '*.java')
java -ea -cp "out;out-test" notes.TestMain
```

Trên Unix dùng `:` thay `;` trong classpath.

## 9. Gợi ý

- Viết parser trước, test bằng file; DAO sau.
- Tách `parse(Path)` và `parse(String)` để test không cần đĩa.
- Dùng `LinkedHashMap` cho thứ tự.
- Không dùng `String.split(";")` để tách query: dấu `;` có thể nằm trong chuỗi.
- Với BOM, kiểm tra byte trước khi decode.

## 10. Mở rộng

1. Thêm kiểm tra cú pháp `?` khớp số tham số.
2. Thêm namespace (`notes.find`).
3. Thêm hot reload registry có kiểm tra nguyên tử.
4. Thêm adapter cho named parameters.
5. Thêm test tích hợp với H2 trong bộ nhớ (không bắt buộc).
