# 34 — Handle mờ gắn với revision

## Mục tiêu

Thiết kế registry handle mờ cho phía trình duyệt: handle là token ngẫu nhiên 128-bit, không chứa resource ID hay revision; server ánh xạ handle → (resource, revision), từ chối handle cũ khi resource đã sang revision mới, hết hạn hoặc bị thu hồi.

## Giá trị

- Trình duyệt không bao giờ thấy ID lưu trữ (RDF, graph name, khóa DB).
- Handle là **capability ngắn hạn**, không phải ID; đổi revision làm handle cũ vô hiệu.
- Học cách phân biệt `unknown`, `expired`, `revoked`, `stale`: bốn lỗi khác nhau, bốn phản ứng UI khác nhau.
- Học cấp phát idempotent, giới hạn dung lượng và thu hồi theo tài nguyên.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | Base64URL, bộ sinh nonce tiêm được, hiểu TTL |
| Thời lượng gợi ý | 4–6 giờ |

## Nguồn gốc

- Repo: `triet4p/projecta`
- File nguồn: <https://github.com/triet4p/projecta/blob/main/apps/api/src/projecta_api/graph_projection.py>
- Hành vi quan sát được:
  - `ProjectionVersion = Literal["s8.graph.v1"]`.
  - `NODE_TYPES` gồm 15 loại (`Project`, `Note`, `Requirement`, `Decision`, `Task`, `Risk`, …); `RELATION_TYPES` gồm 13 loại (`implements`, `blocks`, `dependsOn`, `evidenceFor`, `provenanceFor`, …).
  - Có `LifecycleState`, `ProvenanceState`, `ReviewReceiptStatus`.
  - Quote: *"The browser receives labels and revision-bound opaque handles only … deliberately independent from RDF, graph names, and Semantic Core storage identifiers."*
- **Phần là thiết kế của bài:** định dạng `h1_<base64url(16 byte)>`, registry lưu mapping, TTL, thu hồi, mã lỗi, persistence JSON, CLI. Nguồn chỉ mô tả hợp đồng projection; bài hiện thực hóa handle.

## Hành vi bài tập yêu cầu

- Handle khớp `^h1_[A-Za-z0-9_-]{22}$`; 16 byte nonce; không base64 padding.
- Handle không chứa resource ID, revision, zone hay bất kỳ ID lưu trữ nào.
- `issue(resource_id, expected_revision, now)`:
  - resource không tồn tại → `RESOURCE_NOT_FOUND`;
  - `expected_revision` khác revision hiện tại → `STALE_REVISION`;
  - đã có handle còn hiệu lực cho cùng cặp → trả lại handle đó;
  - hết chỗ → dọn handle hết hạn/đã thu hồi; vẫn hết → `HANDLE_CAPACITY`.
- `resolve(handle, now)`:
  - sai định dạng → `INVALID_HANDLE`;
  - không có → `UNKNOWN_HANDLE`;
  - đã thu hồi → `HANDLE_REVOKED`;
  - hết hạn → `HANDLE_EXPIRED`;
  - resource biến mất → `RESOURCE_NOT_FOUND`;
  - revision hiện tại khác revision gắn → `STALE_REVISION`;
  - còn lại trả `(resource_id, revision)`.
- Handle hết hạn đúng tại `now >= expires_at`.
- Thu hồi idempotent; thu hồi theo resource thu hồi mọi handle chưa hết hạn.
- State lưu/đọc JSON; reload giữ nguyên handle còn hiệu lực.
- Không log full handle ở mức INFO.

## Phạm vi

Trong phạm vi: sinh handle, registry, TTL, revision check, thu hồi, persistence, CLI.

Ngoài phạm vi: HTTP API, quyền truy cập, mã hóa, chống replay ngoài TTL, handle cho cạnh/edge (chỉ node), đa tiến trình.

## Fixture offline

- `fixtures/revisions.json`: `{"res-a": 3, "res-b": 7}`.
- `fixtures/nonces.json`: chuỗi 16 byte hex cố định.
- `fixtures/state.json`: registry rỗng hoặc có handle mẫu.
- `fixtures/expected/`.
- Không chứa handle thật hay secret; nonce tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — định dạng, state machine, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế registry và kiểm chứng.
