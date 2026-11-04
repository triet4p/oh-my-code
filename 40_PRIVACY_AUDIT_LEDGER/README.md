# 40 — Sổ audit riêng tư có tombstone

## Mục tiêu

Thiết kế sổ audit hẹp cho một vault: mỗi bản ghi chỉ có chuỗi hành động/outcome/mã lỗi/chi phí/resource ID, không có nội dung; áp retention theo ngày và trần bản ghi; purge theo resource tạo tombstone để bản ghi đã xóa không quay lại sau khi load/restore; chẩn đoán chỉ dùng thông điệp từ bảng hướng dẫn.

## Giá trị

- Audit hữu ích nhưng nguy hiểm nếu chứa nội dung; thiết kế **hẹp theo cấu trúc** là biện pháp bảo vệ.
- Học hai cơ chế xóa khác nhau: watermark cho prefix theo thời gian/trần, tombstone cho xóa không phải prefix.
- Học chuẩn hóa state khi load: lọc theo watermark/tombstone, sắp, khử trùng, cắt biên.
- Học fail-closed khi schema lạ và không rò đường dẫn/khóa trong lỗi lưu.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | C# 12 / .NET 8 |
| Độ khó | Khó |
| Điều kiện | `record`, LINQ, `DateTimeOffset`, System.Text.Json; không DB |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/my-meta-brain`
- File nguồn: <https://github.com/triet4p/my-meta-brain/blob/main/src/MetaBrain.Core/Security/OperationsAudit.cs>
- Hành vi quan sát được:
  - `OperationsAuditEntry(long Sequence, DateTimeOffset RecordedAtUtc, string Actor, string Action, string Outcome, string? ErrorCode, decimal? CostUsd, string? ResourceId)`.
  - Comment: audit *"carries no title, no body, no query, no transcript excerpt, no path, no credential and no token"*.
  - `OperationsDiagnosticEntry(Sequence, RecordedAtUtc, Component, Code, OwnerMessage, ResourceId?)`; `OwnerMessage` do bảng guidance nội bộ viết, không do caller.
  - `OperationsAuditState(SchemaVersion, Audit, Diagnostics, RetentionDays, MaximumRecords, PurgedThroughSequence, PurgedSequences, NextSequence)`.
  - `CurrentSchemaVersion = 1`, `DefaultRetentionDays = 30`, `DefaultMaximumRecords = 500`.
  - Giới hạn: audit 1000, diagnostics 500, tombstone 8192, actor 16, action 96, outcome 32, code 96, message 600, resource 128; retention 1…3650; max records 10…5000.
  - `ValidateAndNormalizeState`: lọc `Sequence > PurgedThroughSequence` và không nằm trong `PurgedSequences`; sắp; take giới hạn; chuẩn hóa chuỗi; `NextSequence = max(NextSequence, highest+1)`.
  - `AppendAudit`: normalize; nếu entry không hợp lệ thì trả state đã normalize (bỏ entry); nếu hợp lệ, `sequence = max(NextSequence, entry.Sequence)`, append, sort, tăng next, `ApplyRetention`.
  - `ApplyRetention`: cutoff `now - RetentionDays`; giữ `RecordedAtUtc >= cutoff`; `TakeLast(MaximumRecords)`; watermark `purgedThrough = lowestKept - 1`; nếu xóa hết thì `purgedThrough = max(NextSequence-1, cũ)`.
  - `RemoveForResources`: xóa entry có `ResourceId` trong tập; sequence bị xóa thành tombstone, distinct/sort/takeLast 8192; sau đó apply retention.
  - `IsBounded`: không null/whitespace và độ dài ≤ max.
  - `CostUsd` null hoặc 0…1.000.000.
  - `OperationsAuditPersistenceException : IOException`, message generic, không lặp path/key/exception.
  - Hằng actor `owner/agent/service`; outcome `completed/refused/failed`; thêm `audit_failed`; code `audit_persistence_failed`.

**Phần là thiết kế của bài:** giới hạn token cho actor/outcome/action, lọc/khử trùng khi load, API trả `Appended`, bảng guidance rút gọn, console selftest. Nguồn chỉ kiểm tra độ dài; bài chặt hơn để audit không bị dùng làm kênh lén.

## Hành vi bài tập yêu cầu

- Record chỉ có 8 trường; không có trường nội dung tự do.
- Actor ∈ {owner, agent, service}; outcome ∈ {completed, refused, failed, audit_failed}; action/error code khớp token.
- Append entry không hợp lệ → không đổi state (ngoài normalize), trả `Appended=false` kèm lý do.
- Sequence do server gán: `max(NextSequence, entry.Sequence)`.
- Retention theo `now - days`, giữ biên `>=`; trần bản ghi áp riêng cho audit và diagnostic; watermark tiến đúng.
- Purge theo resource tạo tombstone; tombstone lọc khi load; giới hạn 8192.
- Diagnostic chỉ nhận mã có trong bảng guidance; mã lạ không thêm.
- State schema khác 1 → `InvalidDataException`; lỗi lưu/đọc → `OperationsAuditPersistenceException` message generic.
- Không log/không lưu title, body, query, transcript, path, credential, token.

## Phạm vi

Trong phạm vi: domain, bounds, normalize, append, retention, purge, diagnostics, persistence wrapper, selftest.

Ngoài phạm vi: mã hóa file, khóa vault, DB, UI, phân tán, nén log, chữ ký.

## Fixture offline

- `fixtures/state-empty.json`, `state-with-gap.json`, `state-purged.json`.
- `fixtures/guidance.json` (bảng message rút gọn).
- `fixtures/forbidden-keys.json` để test schema.
- Không nội dung thật, không credential; thời gian cố định.

## Liên kết

- [SPEC.md](SPEC.md) — schema, chuẩn hóa, retention/purge, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế watermark/tombstone và kiểm chứng.
