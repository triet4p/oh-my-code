# GUIDE 39 — Thiết kế GrantAuthority

## 1. Kiến trúc

```
Grants/
├─ Grants.csproj
├─ Domain.cs          # record, enum, reason constants
├─ GrantAuthority.cs
├─ Stores.cs          # InMemoryGrantStore, FaultingGrantStore
├─ Scenario.cs        # đọc JSON, chạy bước
└─ Program.cs         # selftest / scenario
fixtures/
```

Không cần NuGet. `System.Text.Json` có sẵn trong .NET 8.

## 2. Đồng bộ

Dùng một `lock (_gate)` cho toàn bộ state và store. Không `async` trong khóa. Source dùng `lock`; bài giữ để đơn giản và đúng.

Không gọi `clock()`/`newGrantId()` bên trong khi đã có lock? Có thể, nhưng hàm tiêm phải nhanh và không tái nhập authority. Ghi rõ.

## 3. Copy và bất biến

- Records là immutable, nhưng `AccessGrant[]` mutable. Khi load, clone mảng; khi commit, tạo mảng mới (`Append`/`Where`), không sửa mảng cũ.
- `List` trả `Array.AsReadOnly(clone)`.
- `Get` trả record (immutable).
- Store nhận state; nếu store giữ reference, authority không sửa mảng đó nữa.

## 4. Commit

```
if generation == long.MaxValue: available=false; throw IOException
next = new State(1, generation+1, grants)
try { store.Save(next); state = next; }
catch { available=false; throw; }
```

Không đặt `state = next` trước `Save`; nếu Save lỗi, state cũ vẫn là sự thật (dù authority unavailable).

## 5. Expiry

```
live = grants.Where(g => g.ExpiresAtUtc > now).ToArray()
if live.Length != grants.Length: Commit(live)
```

- Dùng `>`: grant hết hạn đúng `now` bị loại.
- Nếu không có grant nào hết hạn, không commit, generation không đổi.
- `Authorize` gọi expiry mỗi lần; chi phí O(n) chấp nhận cho bài.

## 6. Thứ tự Authorize

Viết đúng thứ tự; đừng gộp điều kiện. Ví dụ:

- Nếu kiểm tra `!_available` trước `invalid_request`, reason khác.
- Nếu owner bypass trước unexpected egress, owner có thể gửi egress context cho operation thường và được cho qua — sai.
- Nếu egress kiểm tra grant trước `IsTrusted`, context giả có thể nhận reason khác.

## 7. Scope

`HasValidScope` dùng XOR. Viết:

```csharp
bool r = IsValidIdentifier(resourceId);
bool z = IsValidIdentifier(zoneId);
return r != z;
```

Nếu viết `(resourceId is null) != (zoneId is null)` sẽ chấp nhận chuỗi rỗng? `IsValidIdentifier("")` false, nhưng null check khác. Dùng hàm valid.

`ScopeMatches` dùng OR; chú ý grant ResourceId null: biểu thức `grant.ResourceId is not null && ...` phải có, nếu không `null == null` có thể khớp request resource null.

## 8. Egress

- `EgressContext` phải phân biệt trusted/untrusted. Scenario JSON chỉ nên cho `trusted` qua factory, không cho set trực tiếp nếu constructor private.
- Kiểm tra provider/model bằng `IsValidIdentifier`, không chỉ khác rỗng.
- Cost là `decimal`; so sánh chính xác. `EstimatedCostUsd <= 0` bao gồm null.
- Khi nhiều grant egress cùng provider/model, chọn grant đầu tiên có max đủ; nếu không, `egress_cost_exceeded`. Thứ tự grant là thứ tự append (state). Không sort.
- Egress không owner bypass.

## 9. Store lỗi

`FaultingGrantStore`:

- `FailOnSaveAfter(n)` ném `IOException` ở lần save thứ n+1.
- `FailOnLoad()` ném khi khởi tạo.
- Ghi nhận số lần save.

Kiểm tra:

1. Create thành công → save 1.
2. Create lỗi save → authority unavailable; `List` ném; `Authorize` trả `policy_unavailable`.
3. Expiry lỗi save trong Authorize → `policy_unavailable`.

**Bẫy:** sau khi `_available=false`, `Create` gọi `EnsureAvailable` và ném trước khi validate; `Authorize` không gọi `EnsureAvailable` mà kiểm tra cờ sau các bước khác.

## 10. State JSON

Dùng `JsonSerializerOptions`:

```csharp
new JsonSerializerOptions {
  PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
  WriteIndented = true
}
```

`DateTimeOffset` serialize ISO; state validation yêu cầu offset zero, nên fixture dùng `Z`.

Enum `PrincipalKind` không nằm trong state; scenario parse chuỗi `"owner"`/`"agent"`.

## 11. Bẫy thường gặp

- **Commit trước Save**: state mới dù lưu lỗi.
- **Expiry không commit**: grant hết hạn vẫn trong state, generation không đổi.
- **Expiry commit cả khi không đổi**: generation tăng vô ích; test sẽ bắt.
- **Scope XOR sai**: dùng null check thay valid check.
- **Scope match AND**: zone grant không áp cho resource; sai hợp đồng.
- **Owner bypass egress**: lỗ hổng chi phí.
- **Kiểm tra untrusted sau khi tìm grant**: reason sai, và có thể lộ thông tin grant.
- **Không clone mảng khi load/list**: sửa ngoài ảnh hưởng state.
- **Generation `long.MaxValue`**: kiểm tra trước khi tạo state mới.
- **Guid chữ hoa**: canonical id khác; validate chặt.
- **`DateTimeOffset` offset khác 0 trong state**: chấp nhận sẽ làm so sánh khó; từ chối.

## 12. Kiểm chứng

```bash
cd 39_GRANTS
dotnet build
dotnet run --project Grants -- selftest
```

Nếu tách project test:

```bash
dotnet run --project Tests
```

Kịch bản:

```bash
dotnet run --project Grants -- scenario fixtures/scenario.json
```

`selftest` phải exit 0; in số case đã chạy.

Kiểm tra state invalid:

```bash
dotnet run --project Grants -- validate-state fixtures/state-invalid-offset.json
```

## 13. Gợi ý

- Viết Domain + state validation trước; test load.
- Viết expiry/commit; test generation.
- Viết non-egress authorize; sau đó egress.
- Viết fault store cuối.
- Dùng `Check.That(condition, message)` trong test console thay vì NuGet.
- Không dùng `DateTimeOffset.Now`; luôn `clock()`.

## 14. Mở rộng

1. Lưu state mã hóa.
2. Nhiều owner/tenant.
3. Ngân sách egress theo cửa sổ thời gian.
4. Audit mọi decision.
5. Ký state và kiểm tra chữ ký khi load.
