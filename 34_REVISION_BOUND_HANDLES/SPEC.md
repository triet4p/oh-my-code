# SPEC 34 — Handle mờ theo revision

## 1. Định dạng handle

```text
h1_<base64url(nonce)>
```

- `nonce`: đúng 16 byte từ `NonceSource.next()`.
- Base64URL không padding (`-`, `_`), 22 ký tự.
- Tổng dài 25.
- Regex: `^h1_[A-Za-z0-9_-]{22}$`.
- Không chứa resource ID/revision; không mã hóa ID; không suy ra được từ handle nếu không có registry.

## 2. Nguồn revision

```python
class RevisionSource:
    def current(self, resource_id: str) -> int | None: ...
```

- Trả số nguyên ≥0 hoặc `None` nếu không tồn tại.
- Trong test, đọc từ `fixtures/revisions.json`.
- Có thể thay đổi giữa các lần gọi để mô phỏng revision mới.

## 3. Registry state

```json
{
  "schema_version": 1,
  "ttl_seconds": 900,
  "handles": {
    "h1_AAECAwQFBgcICQoLDA0ODw": {
      "resource_id": "res-a",
      "revision": 3,
      "issued_at": 0,
      "expires_at": 900,
      "revoked": false
    }
  }
}
```

- `schema_version` phải bằng 1; khác → `UNSUPPORTED_STATE`.
- `ttl_seconds` 1…86400.
- `issued_at`, `expires_at` là số nguyên giây; `expires_at > issued_at`.
- Handle key phải khớp định dạng.
- `resource_id` không rỗng; `revision` ≥0.
- `revoked` bool.

## 4. API

```python
registry = HandleRegistry(revisions, nonce_source, state, clock)
handle = registry.issue("res-a", 3)
bound = registry.resolve(handle)
registry.revoke(handle) -> bool
registry.revoke_resource("res-a") -> int
```

`clock() -> int` giây.

## 5. `issue`

1. `current = revisions.current(resource_id)`.
2. `None` → `RESOURCE_NOT_FOUND`.
3. `expected_revision != current` → `STALE_REVISION`.
4. Nếu có handle chưa revoked, chưa hết hạn, cùng `(resource_id, revision)` → trả handle đó (không cấp mới).
5. Nếu `len(handles) >= max_handles` (mặc định 10000):
   - xóa mọi entry đã revoked hoặc `now >= expires_at`;
   - nếu vẫn đầy → `HANDLE_CAPACITY`.
6. Sinh nonce 16 byte; nếu nguồn trả sai độ dài → `INVALID_NONCE`.
7. Tạo handle; nếu trùng key → thử tối đa 3 lần, sau đó `HANDLE_COLLISION` (không ghi đè handle cũ).
8. `expires_at = now + ttl`; lưu; trả.

Không thu hồi handle cũ khi revision đổi: nó sẽ trả `STALE_REVISION`, hữu ích cho UI.

## 6. `resolve`

Thứ tự:

1. Sai regex → `INVALID_HANDLE`.
2. Không có trong map → `UNKNOWN_HANDLE`.
3. `revoked` → `HANDLE_REVOKED`.
4. `now >= expires_at` → `HANDLE_EXPIRED`.
5. `revisions.current(resource_id)` là `None` → `RESOURCE_NOT_FOUND`.
6. Revision hiện tại khác `entry.revision` → `STALE_REVISION`.
7. Trả `BoundResource(resource_id, revision)`.

Handle không gia hạn TTL khi resolve.

## 7. Thu hồi

- `revoke(handle)`: nếu sai định dạng → `INVALID_HANDLE`; không có → `False`; nếu đã revoked → `True`; nếu đã hết hạn → vẫn đánh dấu revoked? Bài chọn `False` nếu hết hạn (không còn hiệu lực), `True` nếu đánh dấu mới. Ghi rõ.
- Tombstone (`revoked=true`) được giữ đến `expires_at` để phân biệt `HANDLE_REVOKED` với `UNKNOWN_HANDLE`, sau đó dọn khi prune.
- `revoke_resource(id)`: đánh dấu revoked mọi entry chưa revoked và chưa hết hạn; trả số lượng.

## 8. Lỗi

| Mã | Nghĩa |
|---|---|
| `INVALID_HANDLE` | sai định dạng |
| `UNKNOWN_HANDLE` | không tồn tại |
| `HANDLE_REVOKED` | đã thu hồi |
| `HANDLE_EXPIRED` | quá TTL |
| `STALE_REVISION` | revision đã đổi hoặc issue sai revision |
| `RESOURCE_NOT_FOUND` | resource không còn |
| `HANDLE_CAPACITY` | registry đầy |
| `INVALID_NONCE` | nguồn nonce sai độ dài |
| `HANDLE_COLLISION` | trùng sau 3 lần |
| `UNSUPPORTED_STATE` | schema state khác |

## 9. Ví dụ cụ thể

Revisions: `res-a=3`, `res-b=7`. Nonce thứ nhất `00…0f`, thứ hai `10…1f`.

1. `issue("res-a", 3, now=0)` → `h1_AAECAwQFBgcICQoLDA0ODw`; expires 900.
2. `resolve(handle, now=10)` → `("res-a", 3)`.
3. `issue("res-a", 3, now=11)` → cùng handle (idempotent).
4. `issue("res-a", 2, now=12)` → `STALE_REVISION`.
5. Đổi revision `res-a=4`.
6. `resolve(handle, now=13)` → `STALE_REVISION`.
7. `issue("res-a", 4, now=20)` → `h1_EBESExQVFhcYGRobHB0eHw`; expires 920.
8. `revoke(handle2, now=30)` → `True`; `resolve(handle2)` → `HANDLE_REVOKED`.
9. `resolve(handle1, now=900)` → `HANDLE_EXPIRED`.
10. `resolve("h1_short")` → `INVALID_HANDLE`.
11. `resolve("h1_AAAAAAAAAAAAAAAAAAAAAA")` → `UNKNOWN_HANDLE`.
12. `issue("res-z", 0)` → `RESOURCE_NOT_FOUND`.

## 10. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Nonce 15/17 byte | `INVALID_NONCE` |
| 2 | Nonce trùng 3 lần | `HANDLE_COLLISION` |
| 3 | Nonce trùng lần 2 rồi khác | dùng nonce khác |
| 4 | `now < 0` | `INVALID_CLOCK` |
| 5 | `now = expires_at - 1` | còn hiệu lực |
| 6 | `now = expires_at` | hết hạn |
| 7 | Handle hết hạn rồi resolve | không gia hạn |
| 8 | Revoke handle hết hạn | `False` |
| 9 | Revoke hai lần | lần hai `True` |
| 10 | Revoke resource | thu hồi đúng số |
| 11 | 10000 handle sống | issue thứ 10001 `HANDLE_CAPACITY` |
| 12 | Có 1 handle hết hạn | prune rồi cấp được |
| 13 | Reload state | handle còn hạn resolve được |
| 14 | State version 2 | `UNSUPPORTED_STATE` |
| 15 | Handle key sai định dạng trong state | `UNSUPPORTED_STATE` |
| 16 | Resource ID chứa handle | không ảnh hưởng; handle vẫn ngẫu nhiên |
| 17 | Label trùng | ngoài phạm vi registry |
| 18 | Revision 0 | hợp lệ |

## 11. Tiêu chí chấp nhận

- [ ] 12 bước ví dụ cho đúng handle và lỗi.
- [ ] Handle mẫu đúng regex và không chứa `res-a`.
- [ ] Issue lặp trả cùng handle, không tăng map.
- [ ] Đổi revision làm resolve cũ trả `STALE_REVISION`.
- [ ] `now >= expires_at` trả `HANDLE_EXPIRED`.
- [ ] Revoke/resource revoke đúng, tombstone giữ đến hạn.
- [ ] Reload state giữ hành vi.
- [ ] Với 10001 handle sống, lỗi rõ; không đuổi handle sống.
- [ ] Không log full handle.

## 12. Non-goals

- Không phải cơ chế xác thực; handle là bearer token nội bộ.
- Không mã hóa state; không chống đọc file registry.
- Không hỗ trợ handle cho cạnh, batch resolve, hay phân tán nhiều node.
- Không chống replay trong TTL; đó là việc của authorization.
