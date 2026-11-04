# 39 — Cấp quyền có thời hạn và egress

## Mục tiêu

Cài đặt `GrantAuthority`: cấp quyền có thời hạn cho cặp principal/session theo resource **hoặc** zone, thu hồi, liệt kê, và cấp quyền egress có ngân sách tối đa theo provider/model. Mọi thay đổi đi qua một thế hệ chính sách tăng dần; quyết định uỷ quyền trả lý do và thế hệ hiện tại.

## Giá trị

- Quyền là dữ liệu có hạn, có phạm vi, có thế hệ; không phải cờ boolean toàn cục.
- Egress là ngoại lệ nguy hiểm: phải có provider/model/chi phí tối đa, context tin cậy và giá ước tính.
- Học cách tách owner bypass khỏi quyền agent, và vì sao egress không được bypass.
- Học commit nguyên tử: lưu thành công rồi mới đổi state; lỗi lưu làm authority unavailable.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | C# 12 / .NET 8 |
| Độ khó | Khó |
| Điều kiện | `record`, `lock`, `DateTimeOffset`, System.Text.Json; không cần DB |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/my-meta-brain`
- File nguồn: <https://github.com/triet4p/my-meta-brain/blob/main/src/MetaBrain.Core/Security/GrantPolicy.cs>
- Hành vi quan sát được:
  - `EgressGrant(string Provider, string Model, decimal MaximumCostUsd)`.
  - `GrantCreateRequest(PrincipalId, SessionId, ResourceId?, ZoneId?, Operation, ExpiresAtUtc, Egress?)`.
  - `AccessGrant(GrantId, PrincipalId, SessionId, ResourceId?, ZoneId?, Operation, CreatedAtUtc, ExpiresAtUtc, Egress?)`.
  - `GrantPolicyState(int SchemaVersion, long PolicyGeneration, AccessGrant[] Grants)`; `CurrentSchemaVersion = 1`.
  - `ProviderEgressOperation = "provider.egress"`.
  - `Create`: `EnsureOwner`, lock, `EnsureAvailable`, `ExpireGrants`, `ValidateCreateRequest`, tạo GUID `"N"`, `Commit(append)`.
  - `Commit`: nếu generation `long.MaxValue` → unavailable + `IOException`; lưu state mới trước, lỗi lưu → unavailable + ném.
  - `Authorize` thứ tự: expire (lỗi store → `policy_unavailable`), invalid request, unexpected egress, owner bypass cho non-egress, kiểm tra egress, availability, tìm grant.
  - Egress: thiếu/sai provider/model → `egress_context_unknown`; cost null/≤0 → `egress_unpriced`; không trusted → `untrusted_egress_context`; không grant khớp → `egress_not_granted`; có grant nhưng vượt max → `egress_cost_exceeded`; thành công → `grant_allowed` kèm `MaximumCostUsd`.
  - Non-egress: có grant → `grant_allowed`; không → `grant_not_found`.
  - `ScopeMatches`: `grant.ResourceId == request.ResourceId || grant.ZoneId == request.ZoneId`.
  - `HasValidScope`: đúng một trong resource/zone khác null.
  - `IsValidIdentifier`: 1–128, bắt đầu ASCII alphanumeric, sau đó alphanumeric/`.`/`_`/`-`.
  - `IsGrantId`: `Guid.TryParseExact(value, "N")`.
  - `ExpireGrants`: giữ `ExpiresAtUtc > now`; nếu thay đổi thì commit (tăng generation).
  - `InspectAgentAccess`: principal/session `owner/owner` → owner context; id sai → `agent_not_found`.
  - `EnsureOwner`: chỉ owner channel được quản lý grant.

**Phần là thiết kế của bài:** clock/ID/store tiêm được, mã lỗi khi state hỏng, JSON scenario, test không DB, quy ước id chữ thường. Nguồn dùng `DateTimeOffset.UtcNow` và `Guid.NewGuid`; bài tiêm để tất định.

## Hành vi bài tập yêu cầu

- State hợp lệ: schema 1, generation ≥0, grant id 32 hex thường duy nhất, scope XOR, thời gian UTC, expiry > created, egress đúng luật.
- `Create` chỉ owner; request hợp lệ; expiry tương lai; append + commit tăng generation.
- `List`/`Get`/`Revoke` chỉ owner; `Get` id sai trả `null`; `Revoke` id sai/không có trả `false` không commit.
- `Authorize` theo đúng thứ tự và mã lý do; egress không được owner bypass.
- `ExpireGrants` loại grant hết hạn và tăng generation chỉ khi có thay đổi.
- Store lỗi khi commit → authority unavailable; các thao tác quản lý ném `IOException`; `Authorize` trả `policy_unavailable`.
- Mọi quyết định kèm `PolicyGeneration`; egress thành công kèm max cost.
- ID/thời gian tất định khi tiêm; cùng scenario cho cùng output.

## Phạm vi

Trong phạm vi: domain, state validation, create/list/get/revoke, authorize, expiry, egress, store in-memory/JSON, scenario runner.

Ngoài phạm vi: DB thật, mã hóa, xác thực owner, UI, phân tán, rate limit, ký state.

## Fixture offline

- `fixtures/scenario.json`: chuỗi create/authorize/revoke với clock và ID cố định.
- `fixtures/state-valid.json`, `state-invalid-*.json`.
- Không credential, không gọi mạng; chi phí là số thập phân tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng quyết định, state, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế commit/expiry/fault injection.
