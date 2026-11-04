# SPEC 39 — GrantAuthority

## 1. Kiểu

```csharp
public enum PrincipalKind { Owner, Agent }

public sealed record AuthenticatedContext(PrincipalKind Kind, string PrincipalId, string SessionId);

public sealed record EgressGrant(string Provider, string Model, decimal MaximumCostUsd);

public sealed record GrantCreateRequest(
    string PrincipalId, string SessionId, string? ResourceId, string? ZoneId,
    string Operation, DateTimeOffset ExpiresAtUtc, EgressGrant? Egress);

public sealed record AccessGrant(
    string GrantId, string PrincipalId, string SessionId, string? ResourceId, string? ZoneId,
    string Operation, DateTimeOffset CreatedAtUtc, DateTimeOffset ExpiresAtUtc, EgressGrant? Egress);

public sealed record GrantPolicyState(int SchemaVersion, long PolicyGeneration, AccessGrant[] Grants);

public sealed record AccessRequest(
    string? ResourceId, string? ZoneId, string Operation, EgressContext? EgressContext = null);

public sealed record AuthorizationDecision(
    bool Allowed, string Reason, long PolicyGeneration, decimal? MaximumCostUsd = null);

public sealed class EgressContext
{
    private EgressContext(string provider, string model, decimal? estimatedCostUsd, bool isTrusted);
    public string Provider { get; }
    public string Model { get; }
    public decimal? EstimatedCostUsd { get; }
    public bool IsTrusted { get; }
    public static EgressContext FromTrustedProviderCall(string provider, string model, decimal? estimatedCostUsd);
    public static EgressContext FromUntrustedRequest(string provider, string model, decimal? estimatedCostUsd);
}
```

Constructor là private; chỉ hai factory tạo được context. Scenario JSON ánh xạ `trusted` boolean qua factory tương ứng, không cho set `IsTrusted` trực tiếp.

## 2. State hợp lệ

`GrantPolicyState`:

- `SchemaVersion == 1`.
- `PolicyGeneration >= 0`.
- `Grants != null`.
- Mỗi grant:
  - `GrantId` khớp `^[0-9a-f]{32}$` và duy nhất.
  - `PrincipalId`, `SessionId`, `Operation` hợp lệ.
  - Đúng một trong `ResourceId`/`ZoneId` khác null; giá trị khác null phải hợp lệ.
  - `CreatedAtUtc.Offset == TimeSpan.Zero`, `ExpiresAtUtc.Offset == TimeSpan.Zero`.
  - `ExpiresAtUtc > CreatedAtUtc`.
  - Nếu `Operation == "provider.egress"`: `Egress != null`, provider/model hợp lệ, `MaximumCostUsd > 0`.
  - Ngược lại: `Egress == null`.

State sai → `InvalidDataException("Invalid durable grant policy state.")` hoặc `"Invalid durable grant record."` khi load. `GrantPolicyState.Empty = new(1, 0, Array.Empty<AccessGrant>())`.

## 3. Quản lý

```csharp
GrantAuthority(IGrantStore store, Func<DateTimeOffset> clock, Func<string> newGrantId)
long PolicyGeneration { get; }
AccessGrant Create(AuthenticatedContext actor, GrantCreateRequest request)
IReadOnlyList<AccessGrant> List(AuthenticatedContext actor)
AccessGrant? Get(AuthenticatedContext actor, string grantId)
bool Revoke(AuthenticatedContext actor, string grantId)
AuthorizationDecision InspectAgentAccess(AuthenticatedContext actor, string principalId, string sessionId, AccessRequest request)
AuthorizationDecision Authorize(AuthenticatedContext context, AccessRequest request)
```

- `EnsureOwner` trước mọi thao tác quản lý; không owner → `UnauthorizedAccessException`.
- `EnsureAvailable` sau owner (trừ `Get` với id sai: trả `null` trước).
- Mọi thay đổi thành công gọi `Commit`, tăng generation đúng 1.
- `List` trả snapshot chỉ đọc; sửa mảng trả về không ảnh hưởng state.
- `Revoke` id sai định dạng/không tồn tại → `false`, không commit.
- `Get` id sai định dạng → `null`.

## 4. `Create`

1. `EnsureOwner`.
2. Lock.
3. `EnsureAvailable`.
4. `now = clock().ToUniversalTime()`; `ExpireGrants(now)`.
5. Validate request:
   - principal/session/operation hợp lệ;
   - đúng một resource/zone và hợp lệ;
   - `ExpiresAtUtc > now`;
   - egress đúng luật như state.
   - Sai → `ArgumentException("Invalid grant request.")`.
6. GrantId = `newGrantId()`; phải khớp 32 hex thường và không trùng; nếu không → `InvalidOperationException`.
7. `CreatedAtUtc = now`; `ExpiresAtUtc = request.ExpiresAtUtc.ToUniversalTime()`.
8. Commit append; trả grant.

`ExpireGrants` chạy trước validate; nếu có grant hết hạn, generation tăng ngay cả khi request sau đó sai. Ghi chú hành vi này.

## 5. `Authorize` — thứ tự bắt buộc

1. Lock.
2. `ExpireGrants(now)` trong `try`:
   - lỗi store thuộc `IOException`, `UnauthorizedAccessException`, `SecurityException` → `_available = false`; trả `Deny("policy_unavailable")`.
3. Nếu request không hợp lệ (`HasValidAccessScope` + operation) → `Deny("invalid_request")`.
4. Nếu `Operation != "provider.egress"` và `EgressContext != null` → `Deny("unexpected_egress_context")`.
5. Nếu `Operation != "provider.egress"` và context.Kind == Owner → `Allow("owner_bypass")`.
6. Nếu operation là egress:
   1. `EgressContext == null` hoặc provider/model không hợp lệ → `Deny("egress_context_unknown")`.
   2. `EstimatedCostUsd is null or <= 0` → `Deny("egress_unpriced")`.
   3. `!IsTrusted` → `Deny("untrusted_egress_context")`.
7. Nếu `!_available` → `Deny("policy_unavailable")`.
8. `candidates = grants` khớp principal/session/operation và `ScopeMatches`.
9. Non-egress: `candidates.Any()` → `Allow("grant_allowed")`, ngược lại `Deny("grant_not_found")`.
10. Egress:
    - Duyệt candidates có `Egress.Provider == context.Provider` và `Model == context.Model`.
    - Không có candidate khớp provider/model → `Deny("egress_not_granted")`.
    - Có khớp nhưng mọi `MaximumCostUsd < EstimatedCostUsd` → `Deny("egress_cost_exceeded")`.
    - Ngược lại → `Allow("grant_allowed", maxCost)` của grant đầu tiên đủ chi phí.
11. Mọi decision dùng generation hiện tại **sau** expiry.

## 6. Phạm vi

`HasValidScope(resource, zone)` (dùng cho grant):

```
valid(resource) XOR valid(zone) == true
và mỗi giá trị null hoặc hợp lệ
```

`HasValidAccessScope(resource, zone)` (dùng cho request):

```
(resource != null || zone != null)
và mỗi giá trị null hoặc hợp lệ
```

`ScopeMatches(grant, request)`:

```
grant.ResourceId != null && grant.ResourceId == request.ResourceId
|| grant.ZoneId != null && grant.ZoneId == request.ZoneId
```

Đây là OR có chủ đích: grant theo zone áp cho mọi resource trong zone; grant theo resource khớp resource đó.

## 7. Lý do

| Reason | Nghĩa |
|---|---|
| `owner_bypass` | owner, non-egress, request hợp lệ |
| `grant_allowed` | có grant khớp |
| `grant_not_found` | không grant non-egress khớp |
| `egress_not_granted` | không grant egress khớp provider/model |
| `egress_cost_exceeded` | có grant nhưng max < cost |
| `egress_context_unknown` | thiếu/sai provider/model |
| `egress_unpriced` | cost null/≤0 |
| `untrusted_egress_context` | context không tin cậy |
| `unexpected_egress_context` | non-egress nhưng có egress |
| `invalid_request` | scope/operation sai |
| `policy_unavailable` | store/generation lỗi |
| `agent_not_found` | InspectAgentAccess id sai |

## 8. Ví dụ cụ thể

Clock: `2026-01-01T00:00:00Z`. ID: `00000000000000000000000000000001`, `...02`.

1. Owner tạo grant `agent-a/s1`, resource `r1`, operation `document.read`, hết hạn `+1h`.
   - State generation 0 → 1; grant id `...01`.
2. Agent `agent-a/s1` authorize `document.read` resource `r1` → `Allowed=true`, `grant_allowed`, generation 1.
3. Cùng agent authorize zone `z1` → `grant_not_found`.
4. Owner authorize `document.read` resource `r1` → `owner_bypass`.
5. Owner tạo egress grant `agent-a/s1`, zone `z1`, operation `provider.egress`, provider `openai`, model `m1`, max `2.5`, hết hạn `+1h`. Generation 2.
6. Agent egress trusted provider `openai` model `m1` cost `1.5`, zone `z1` → allowed, max `2.5`.
7. cost `3.0` → `egress_cost_exceeded`.
8. provider `other` → `egress_not_granted`.
9. untrusted cost `1` → `untrusted_egress_context`.
10. cost `0` → `egress_unpriced`.
11. non-egress `document.read` + egress context → `unexpected_egress_context`.
12. Tại `+2h`, agent authorize grant 1 → expiry commit generation 3; `grant_not_found`.
13. Revoke grant 2 → `true`; authorize egress → `egress_not_granted`.
14. Store lỗi khi save lúc create → `IOException`; sau đó `List` ném `IOException`; **agent** `Authorize` non-egress trả `policy_unavailable`.

## 9. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Grant resource và zone cùng set | `ArgumentException` |
| 2 | Grant không set cả hai | `ArgumentException` |
| 3 | Request không set cả hai | `invalid_request` |
| 4 | Request set cả hai | hợp lệ; match OR |
| 5 | Operation egress không có Egress | `ArgumentException` |
| 6 | Operation thường có Egress | `ArgumentException` |
| 7 | MaxCost 0/âm | `ArgumentException` |
| 8 | Expiry đúng `now` | `ArgumentException` (phải >) |
| 9 | Expiry offset +07 | hợp lệ; lưu UTC |
| 10 | State offset +07 | `InvalidDataException` |
| 11 | Grant id chữ hoa | `InvalidDataException` |
| 12 | Id trùng | `InvalidDataException` |
| 13 | Generation `long.MaxValue` + create | `IOException`, unavailable |
| 14 | Store lỗi lúc expire trong Authorize | `policy_unavailable` |
| 15 | Store lỗi lúc create | ném, unavailable |
| 16 | Owner egress không grant | `egress_not_granted` |
| 17 | Owner non-egress scope không grant | `owner_bypass` |
| 18 | Request invalid + owner | `invalid_request` (không bypass) |
| 19 | Inspect `owner/owner` | dùng owner context |
| 20 | Inspect id sai | `agent_not_found` |
| 21 | Revoke id sai | `false`, generation không đổi |
| 22 | Get id sai | `null` |
| 23 | Grant hết hạn đúng `now` | bị loại (`>` giữ) |
| 24 | Egress cost null | `egress_unpriced` |
| 25 | Owner gọi List khi unavailable | `IOException` |

## 10. Tiêu chí chấp nhận

- [ ] 14 bước ví dụ khớp reason/generation/allowed/max.
- [ ] Thứ tự `Authorize` đúng: unexpected egress trước owner bypass.
- [ ] Owner không bypass egress.
- [ ] Expiry tăng generation chỉ khi có grant bị loại.
- [ ] Commit tăng đúng 1; lỗi store không đổi state cũ.
- [ ] State invalid bị từ chối khi load.
- [ ] Scope XOR cho grant, OR khi match.
- [ ] Store fault → unavailable, `Authorize` trả `policy_unavailable`.
- [ ] Cùng clock/ID cho cùng kết quả.

## 11. Non-goals

- Không DB thật, không mã hóa state.
- Không xác thực owner; actor do caller cung cấp.
- Không rate limit/ngân sách theo thời gian.
- Không phân tán/nhiều writer.
- Không UI.
