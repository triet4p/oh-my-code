# 33 — Chiếu chỉ mục tìm kiếm riêng tư

## Mục tiêu

Xây dựng projection chỉ mục từ các bản ghi canonical: mỗi dòng chỉ mang định danh, revision, zone, loại, trạng thái và liên kết; không mang title/body/token. Kèm digest để phát hiện thế hệ mới, mẫu tối đa 512 dòng, và tìm kiếm trong tiến trình chỉ trả metadata.

## Giá trị

- Chỉ mục là **dẫn xuất có thể dựng lại**, canonical là nguồn sự thật duy nhất.
- Học cách giới hạn bộ nhớ/wire: token không bao giờ ra khỏi tiến trình.
- Học digest ổn định để biết “chỉ mục này có còn khớp canonical không”.
- Học fail-closed khi định dạng mới hơn phiên bản đọc được.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | JSONL, SHA-256, hiểu projection/dẫn xuất |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/my-meta-brain`
- File nguồn: <https://github.com/triet4p/my-meta-brain/blob/main/src/MetaBrain.Core/Index/PrivateIndex.cs>
- Hành vi quan sát được:
  - `PrivateIndexRecordKind` gồm `Unknown = 0`, `MemoryItem = 1`, `RegisteredSource = 2`, `Relation = 3`, `Lifecycle = 4`, `RetainedRevision = 5`, `PreservedSourceSnapshot = 6`, `Feedback = 7`, `Proposal = 8`.
  - `PrivateIndexRow(ResourceId, ZoneId, Revision, CanonicalSchemaVersion, RecordKind, State, LinkedResourceIds)`.
  - `SearchIndexDocument(..., string[] Tokens, OccurredAtUtc, RecordedAtUtc, Publication, Project, Environment, Version)`.
  - Quote: *"Token sets never cross the wire: the service scores them in process and only serves ranked hits with metadata."*
  - `PrivateIndexSnapshot(int SchemaVersion, string CanonicalDigest, int RowCount, PrivateIndexRow[] Rows)`; `Rows` là mẫu có giới hạn theo thứ tự resource-ID.
  - `PrivateIndexFormat.CurrentVersion = 3`; `RequireSupported` ném khi version khác.
  - `MaximumIndexedRows = 100_000`, `MaximumSnapshotRows = 512`, `MaximumLinkedIds = 512`.
  - `MaximumDocumentCodeUnits` tính từ giới hạn title/body/applicability của canonical.

**Phần là thiết kế của bài:** định dạng JSONL, công thức digest, tokenizer/stopword, scoring, CLI, fixture. Nguồn dùng C#/AEAD; bài không mã hóa file, nhưng giữ nguyên nguyên tắc không xuất token.

## Hành vi bài tập yêu cầu

- Đọc manifest + records; manifest version khác `3` → lỗi `UNSUPPORTED_FORMAT`, không trả dòng nào.
- Mỗi record sinh tối đa một row; khóa `(resource_id, revision)` duy nhất.
- Row chỉ chứa 7 trường metadata; không `title`, `body`, `tokens`.
- `row_count` là tổng thật; `rows` là 512 dòng đầu theo `(resource_id, revision)`.
- `canonical_digest` là SHA-256 của chuỗi canonical ổn định, có body hash nhưng không có body.
- Tìm kiếm chấm điểm trong bộ nhớ; hit chỉ gồm `resource_id`, `revision`, `score`.
- Không dùng thời gian, không phụ thuộc thứ tự file; sắp xếp tất định.

## Phạm vi

Trong phạm vi: loader, chuẩn hóa kind, row projection, digest, sample, token search, CLI.

Ngoài phạm vi: mã hóa at-rest, AEAD, token bucket, posting list, stemming thật, zone đồng bộ, rebuild từ DB.

## Fixture offline

- `fixtures/canonical/manifest.json` — `{"format_version": 3}`.
- `fixtures/canonical/records.jsonl` — 3 bản ghi tổng hợp, có body “secret” để test không rò.
- `fixtures/invalid/version-4.json`, `duplicate.jsonl`, `too-many-links.jsonl`.
- `fixtures/expected/snapshot.json`.

Không dữ liệu thật, không token người dùng, không mạng.

## Liên kết

- [SPEC.md](SPEC.md) — schema, digest, search, ví dụ có hash.
- [GUIDE.md](GUIDE.md) — thiết kế projection và kiểm chứng.
