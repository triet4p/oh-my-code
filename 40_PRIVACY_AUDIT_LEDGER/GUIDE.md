# GUIDE 40 — Thiết kế audit hẹp

## 1. Kiến trúc

```
OperationsAudit/
├─ OperationsAudit.csproj
├─ Domain.cs          # record, constants
├─ Normalize.cs       # validate + normalize
├─ Retention.cs       # append, retention, purge
├─ Guidance.cs
├─ Persistence.cs     # exception + store interface
└─ Program.cs         # selftest
fixtures/
```

Không NuGet; .NET 8.

## 2. Vì sao hẹp

Mọi trường tự do đều có thể bị dùng để lén dữ liệu: `action = "read /home/user/secret"`, `errorCode = token`, `resourceId` chứa JSON. Vì vậy:

- actor/outcome là token cố định;
- action/error code/component chỉ `[a-z0-9_.-]`;
- resource ID bị giới hạn độ dài/ký tự;
- diagnostic message **không** do caller truyền.

Không có trường `details`, `context`, `payload` dù tiện.

## 3. Record và mảng

Dùng record immutable, nhưng mảng vẫn mutable. Khi normalize/append, tạo mảng mới. Không sửa mảng của state đầu vào.

`ValidateAndNormalizeState` nên trả state mới; không mutate tham số.

## 4. Normalize

Thứ tự quan trọng:

1. Schema check **trước** khi đọc mảng (fail closed).
2. Lọc purge/tombstone.
3. Sort + dedupe sequence.
4. Cap 1000/500.
5. Truncate/UTC.
6. Drop entry không còn hợp lệ.
7. Tombstone normalize.
8. NextSequence.

Nếu truncate trước sort, không ảnh hưởng sequence; nhưng nếu drop sau cap, có thể còn < cap. Chấp nhận.

### Truncate an toàn

`value[..max]` có thể cắt đôi surrogate. Viết:

```csharp
static string Truncate(string value, int max) {
    if (value.Length <= max) return value;
    var cut = max;
    if (cut > 0 && char.IsHighSurrogate(value[cut - 1])) cut--;
    return value[..cut];
}
```

Đây là **gợi ý**, không phải toàn bộ lời giải.

## 5. Append

```
norm = Normalize(state)
if !Valid(entry): return (norm,false,"invalid_entry")
if norm.NextSequence == long.MaxValue: throw
seq = max(norm.NextSequence, entry.Sequence)
next = entry with { Sequence=seq }
state2 = norm with { Audit = sorted(append), NextSequence=seq+1 }
return (ApplyRetention(state2, now), true, null)
```

**Bẫy:** nếu cộng `seq + 1` khi `seq == long.MaxValue` sẽ tràn. Kiểm tra trước.

## 6. Retention watermark

Ví dụ minh họa:

- Audit seq 1,2,3; maxRecords 2 → giữ 2,3; lowest 2; purgedThrough 1.
- Audit rỗng, diagnostic seq 100 (do audit bị purge hết) → lowest 100; purgedThrough 99. Điều này cũng che audit 1..99; đúng vì chúng đã bị xóa.
- Cả hai rỗng nhưng `NextSequence=50` → purgedThrough 49.

Không dùng `TakeLast` trước khi lọc cutoff; phải lọc thời gian trước.

## 7. Tombstone

- Chỉ purge theo resource, không theo sequence lẻ (nếu cần, thêm API).
- `PurgedSequences` là mảng sequence đã xóa không phải prefix.
- Khi load, lọc cả watermark và tombstone.
- Giới hạn 8192: dùng `TakeLast`, nghĩa là tombstone **mới nhất** được giữ. Tombstone cũ rơi khỏi cửa sổ có thể không chặn restore của state rất cũ; nếu muốn chặt hơn, tăng giới hạn hoặc lưu theo khoảng. Ghi rõ.

## 8. Diagnostic

`OwnerGuidance` là `IReadOnlyDictionary<string,string>` khởi tạo một lần; không cho sửa. `AppendDiagnostic` tra cứu trước khi tạo entry. Nếu code lạ → false, không lưu message mặc định chứa input.

Message không được chứa resource ID, path, hay nội dung; test quét.

## 9. Persistence

```csharp
public interface IOperationsAuditStore {
    OperationsAuditState Load();
    void Save(OperationsAuditState state);
}
```

Bọc lỗi:

```csharp
try { store.Save(state); }
catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException) {
    throw new OperationsAuditPersistenceException(ex);
}
```

Constructor exception **không** đưa `ex.Message` vào message công khai; chỉ giữ inner cho log. Test:

```csharp
Assert(!exception.Message.Contains("/secret/path"));
Assert(!exception.Message.Contains("key"));
```

## 10. Bẫy thường gặp

- **Thêm trường `Details`**: phá mục tiêu.
- **Cho caller truyền OwnerMessage**: rò dữ liệu.
- **Không kiểm tra token**: audit thành kênh tự do.
- **Quên lọc tombstone khi load**: entry đã purge quay lại.
- **Watermark không cập nhật khi xóa hết**: restore phục hồi.
- **`TakeLast` trước cutoff**: giữ entry quá cũ.
- **Tràn sequence**: `seq+1` wrap.
- **Truncate cắt surrogate**: JSON lỗi.
- **Exception chứa path**: rò thông tin nội bộ.
- **Schema lạ trả Empty**: che hỏng dữ liệu; phải ném.
- **Purge xóa cả entry không có resource**: chỉ xóa khi `ResourceId` thuộc tập.
- **Diagnostic dùng chung trần với audit**: bài áp riêng.

## 11. Gỡ lỗi

- In `purgedThrough`, tombstone, next.
- Test append sai: so state trước/sau (ngoài normalize) và next.
- Test load state cũ: chèn entry sequence bị purge, xác nhận biến mất.
- Test 8192 tombstone: sinh 9000, kiểm tra độ dài và sequence cuối.
- Test `now` đúng cutoff: entry `>=` được giữ.
- Quét JSON bằng hàm đệ quy tìm khóa cấm.

## 12. Kiểm chứng

```bash
cd 40_PRIVACY_AUDIT_LEDGER
dotnet build
dotnet run --project OperationsAudit -- selftest
```

Selftest in số case và exit 0/1. Nếu tách project test:

```bash
dotnet run --project Tests
```

Kiểm tra state:

```bash
dotnet run --project OperationsAudit -- normalize fixtures/state-with-gap.json
```

## 13. Gợi ý

- Viết Domain + `IsAuditEntryValid` trước.
- Viết normalize với test bảng (schema, purge, tombstone, duplicate).
- Viết retention với 3-4 entry; kiểm tra watermark.
- Viết purge; test load lại.
- Viết diagnostic/guidance cuối.
- Dùng `Check.That` trong console, không cần NuGet.

## 14. Mở rộng

1. Hash chain để phát hiện sửa audit.
2. Mã hóa state bằng khóa vault.
3. Nén entry cũ.
4. API đọc audit có phân trang, vẫn không lộ nội dung.
5. Chính sách retention theo loại entry.
