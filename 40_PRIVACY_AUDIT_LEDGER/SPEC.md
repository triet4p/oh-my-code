# SPEC 40 — Sổ audit riêng tư

## 1. Kiểu

```csharp
public sealed record OperationsAuditEntry(
    long Sequence, DateTimeOffset RecordedAtUtc, string Actor, string Action,
    string Outcome, string? ErrorCode, decimal? CostUsd, string? ResourceId);

public sealed record OperationsDiagnosticEntry(
    long Sequence, DateTimeOffset RecordedAtUtc, string Component,
    string Code, string OwnerMessage, string? ResourceId);

public sealed record OperationsAuditState(
    int SchemaVersion, OperationsAuditEntry[] Audit,
    OperationsDiagnosticEntry[] Diagnostics, int RetentionDays,
    int MaximumRecords, long PurgedThroughSequence,
    long[] PurgedSequences, long NextSequence);
```

Không có trường `Title`, `Body`, `Query`, `Transcript`, `Path`, `Credential`, `Token`, hay `Payload`.

`Empty` = `SchemaVersion=1`, `Audit=[]`, `Diagnostics=[]`, `RetentionDays=30`, `MaximumRecords=500`, `PurgedThroughSequence=0`, `PurgedSequences=[]`, `NextSequence=1`.

## 2. Giới hạn

| Hằng | Giá trị |
|---|---|
| `CurrentSchemaVersion` | 1 |
| `DefaultRetentionDays` | 30 |
| `DefaultMaximumRecords` | 500 |
| `MaximumAuditEntries` | 1000 |
| `MaximumDiagnosticEntries` | 500 |
| `MaximumTombstones` | 8192 |
| `MaximumActorLength` | 16 |
| `MaximumActionLength` | 96 |
| `MaximumOutcomeLength` | 32 |
| `MaximumCodeLength` | 96 |
| `MaximumMessageLength` | 600 |
| `MaximumResourceIdLength` | 128 |
| `MinimumRetentionDays` / `Maximum` | 1 / 3650 |
| `MinimumMaximumRecords` / `Maximum` | 10 / 5000 |
| `MaximumCostUsd` | 1_000_000 |

Token:

- `Actor`: `owner`, `agent`, `service`.
- `Outcome`: `completed`, `refused`, `failed`, `audit_failed`.
- `Action`/`ErrorCode`: `^[a-z][a-z0-9_.-]{0,95}$`.
- `ResourceId`: null hoặc khớp `^[A-Za-z0-9._:-]{1,128}$` (không cho văn bản tự do).
- `Component`: `^[a-z][a-z0-9_.-]{0,15}$`.

## 3. `IsAuditEntryValid`

Đúng khi:

- `Sequence >= 1`.
- `RecordedAtUtc.Offset == 0`.
- `Actor`, `Action`, `Outcome` khớp token và độ dài.
- `ErrorCode` null hoặc khớp token.
- `ResourceId` null hoặc hợp lệ.
- `CostUsd` null hoặc `0 <= cost <= 1_000_000`.

`IsDiagnosticEntryValid`: sequence, UTC, component/code token, `OwnerMessage` 1–600, resource null/hợp lệ.

## 4. Chuẩn hóa state

`ValidateAndNormalizeState(state)`:

1. `null` → `Empty`.
2. Schema != 1, hoặc `Audit`/`Diagnostics`/`PurgedSequences` null → `InvalidDataException("Invalid durable operations audit state.")`.
3. Lọc audit/diagnostic:
   - không null;
   - `Sequence >= 1`;
   - `Sequence > PurgedThroughSequence`;
   - `Sequence` không nằm trong `PurgedSequences`.
4. Sắp theo sequence tăng.
5. Khử trùng sequence: giữ bản đầu tiên sau sắp.
6. Audit lấy **đầu** 1000; diagnostic lấy đầu 500 (khớp nguồn).
7. Chuẩn hóa từng entry:
   - cắt chuỗi về max, không cắt đôi surrogate pair;
   - `RecordedAtUtc.ToUniversalTime()`;
   - entry không còn hợp lệ theo token/chi phí → loại (bài chặt hơn nguồn).
8. Tombstone: `>0`, distinct, sort, **take last** 8192.
9. `highest` = sequence cuối của audit/diagnostic sau lọc; nếu `highest == long.MaxValue` thì `NextSequence = long.MaxValue`, ngược lại `NextSequence = max(state.NextSequence, highest+1, 1)`. Không để tràn số.
10. `RetentionDays` ngoài 1…3650 → 30; `MaximumRecords` ngoài 10…5000 → 500.
11. `PurgedThroughSequence < 0` → 0.
12. Trả state schema 1.

## 5. Append

```csharp
public static (OperationsAuditState State, bool Appended, string? Reason) AppendAudit(
    OperationsAuditState state, OperationsAuditEntry entry, DateTimeOffset now);
```

1. `normalized = ValidateAndNormalizeState(state)`.
2. Nếu `!IsAuditEntryValid(entry)` → trả `(normalized, false, "invalid_entry")`.
3. Nếu `normalized.NextSequence == long.MaxValue` → `InvalidOperationException("The audit sequence is exhausted.")`.
4. `seq = max(normalized.NextSequence, entry.Sequence)`.
5. Nếu `seq == long.MaxValue` → `InvalidOperationException("The audit sequence is exhausted.")` (không append, không tăng next).
6. Tạo entry với `Sequence=seq`; append; sắp.
7. `NextSequence = seq + 1`.
8. `ApplyRetention(next, now)`.
9. Trả `(retained, true, null)`.

Diagnostic tương tự, nhưng **không nhận message từ caller**:

```csharp
AppendDiagnostic(state, component, code, resourceId, now)
```

- `code` phải có trong `OwnerGuidance`; nếu không → `(normalized, false, "unknown_code")`.
- Message lấy từ bảng, không do caller.
- Nếu `component`/resource sai → false.

## 6. Retention

```csharp
ApplyRetention(state, now)
```

1. Normalize.
2. `cutoff = now.ToUniversalTime().AddDays(-RetentionDays)`.
3. Audit giữ `RecordedAtUtc >= cutoff`, rồi `TakeLast(MaximumRecords)`.
4. Diagnostic giữ tương tự, `TakeLast(MaximumRecords)` riêng.
5. `lowestKept = min(sequence đầu của audit giữ, diagnostic giữ)`; bỏ qua mảng rỗng.
6. Nếu `lowestKept` hữu hạn và `> PurgedThroughSequence` → `purgedThrough = lowestKept - 1`.
7. Nếu không còn gì và trước đó có entry → `purgedThrough = max(NextSequence - 1, purgedThrough)`.
8. Tombstone giữ nguyên.
9. Không tăng `NextSequence` (retention không cấp sequence mới).

`ApplyRetentionChoice(state, days, maxRecords, now)`:

- Validate `days` 1…3650, `maxRecords` 10…5000; sai → `ArgumentOutOfRangeException` với message nêu miền.
- Áp choice rồi retention; trả `(state, removedAudit, removedDiagnostics)` với số đếm `max(0, cũ - mới)`.
- Validate **trước** khi xóa bất cứ thứ gì.

## 7. Purge theo resource

`RemoveForResources(state, IReadOnlyCollection<string> resourceIds, now)`:

1. Normalize.
2. Nếu tập rỗng → trả normalized.
3. Xóa audit/diagnostic có `ResourceId != null` và thuộc tập; ghi sequence vào `removed`.
4. `tombstones = cũ ∪ removed`, distinct, sort, `TakeLast(8192)`.
5. State mới giữ watermark cũ, next cũ; gọi `ApplyRetention`.
6. Trả state.

Tombstone bảo đảm entry đã xóa không quay lại khi load state cũ/restore. Watermark bảo đảm prefix bị retention không quay lại.

## 8. Guidance và lỗi lưu

`OwnerGuidance` là map bất biến `code → message`, message 1–600, do sản phẩm viết:

```json
{
  "vault_locked": "Unlock the vault, then try again.",
  "forbidden": "Only the owner channel may run this operation.",
  "audit_persistence_failed": "The audit trail could not be written. Check storage and try again."
}
```

`OperationsAuditPersistenceException : IOException`:

- Message cố định: `"The private operations state could not be persisted."`.
- Không chứa đường dẫn, khóa, hay message của exception gốc.
- Có thể giữ `InnerException` cho log nội bộ, nhưng `Message` công khai generic.

## 9. Ví dụ cụ thể

State rỗng; now `2026-01-31T00:00:00Z`.

1. Append 4 audit entry (sequence tự 1…4), resource lần lượt `r1,r2,r3,r4`, thời gian 1–4/1.
2. `RemoveForResources(["r2"], now)`:
   - audit còn seq 1,3,4; tombstone `[2]`.
3. `ApplyRetentionChoice(state, 30, 2, now)`:
   - cutoff `2026-01-01T00:00:00Z`; giữ cả 3.
   - trần 2 → giữ seq 3,4; `lowestKept=3`; `purgedThrough=2`.
   - removed audit 1 (seq1; seq2 đã bị purge trước).
4. Load một state cũ có seq 1/2 → bị lọc bởi `purgedThrough=2`; seq2 còn bị tombstone.
5. Append entry với `Sequence=10` → server gán 10; `NextSequence=11`.
6. Append entry mới (Sequence=0) → gán 11; `NextSequence=12`.
7. Append diagnostic `component="vault"`, `code="vault_locked"` → message từ bảng; sequence 12.
8. Append diagnostic code `"secret_leak"` → không thêm, reason `unknown_code`.

JSON audit mẫu:

```json
{
  "sequence": 1,
  "recordedAtUtc": "2026-01-01T00:00:00+00:00",
  "actor": "owner",
  "action": "note.read",
  "outcome": "completed",
  "errorCode": null,
  "costUsd": null,
  "resourceId": "r1"
}
```

Không có khóa nào ngoài 8 trường trên.

## 10. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Actor rỗng | append false |
| 2 | Actor `"root"` | append false |
| 3 | Outcome lạ | append false |
| 4 | Action chữ hoa | append false |
| 5 | Action 97 ký tự | append false |
| 6 | ErrorCode null | hợp lệ |
| 7 | Cost -0.01 / 1_000_000.01 | append false |
| 8 | Cost 0 / 1_000_000 | hợp lệ |
| 9 | Resource 129 ký tự | append false |
| 10 | Offset +07 | append false |
| 11 | Sequence 0 | append false |
| 12 | Sequence 10 với next 3 | gán 10, next 11 |
| 13 | Sequence 5 sau next 11 | gán 11, next 12 |
| 14 | NextSequence `long.MaxValue` | `InvalidOperationException` |
| 14b | Entry.Sequence `long.MaxValue` với next nhỏ | `InvalidOperationException` |
| 15 | Trùng sequence khi load | giữ bản đầu |
| 16 | Tombstone 9000 | giữ 8192 cuối |
| 17 | State schema 2 | `InvalidDataException` |
| 18 | Retention days 0/3651 | `ArgumentOutOfRangeException` |
| 19 | Max records 9/5001 | `ArgumentOutOfRangeException` |
| 20 | Purge tập rỗng | không đổi |
| 21 | Purge resource không có | không đổi |
| 22 | Xóa hết do cutoff | `purgedThrough = next-1` |
| 23 | Entry đúng cutoff | được giữ (`>=`) |
| 24 | Diagnostic code lạ | không thêm |
| 25 | Message caller cố truyền | API không cho |
| 26 | Exception lưu chứa path | Message công khai không chứa |

## 11. Tiêu chí chấp nhận

- [ ] 26 trường hợp biên khớp.
- [ ] JSON audit chỉ có 8 khóa; test quét khóa cấm.
- [ ] Append sai không tăng next, không đổi audit.
- [ ] Append đúng tăng next đúng.
- [ ] Retention watermark đúng; entry cũ không quay lại sau load.
- [ ] Purge tạo tombstone; tombstone lọc khi load.
- [ ] Diagnostic chỉ nhận message từ bảng.
- [ ] Schema lạ ném lỗi, không trả state rỗng.
- [ ] Exception lưu không lộ path/key/inner message.
- [ ] Cùng state + now cho cùng output.

## 12. Non-goals

- Không mã hóa file, không quản lý khóa.
- Không DB, không phân tán.
- Không UI, không biểu đồ.
- Không chữ ký/hash chain audit.
- Không ghi log hệ điều hành.
