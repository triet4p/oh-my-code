# GUIDE 34 — Thiết kế registry handle

## 1. Kiến trúc

```
handles/
├─ registry.py    # issue, resolve, revoke, prune
├─ state.py       # load/save JSON
├─ errors.py
├─ cli.py
fixtures/
```

`HandleRegistry` nhận `RevisionSource`, `NonceSource`, `clock` — tất cả tiêm được. Không đọc file trực tiếp trong logic.

## 2. Nonce và handle

```python
raw = nonce_source.next()          # phải là bytes, đúng 16
if len(raw) != 16: raise InvalidNonce
handle = "h1_" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
```

Kiểm tra regex khi resolve:
`^h1_[A-Za-z0-9_-]{22}$`. Base64URL 16 byte luôn 22 ký tự; không cần decode lại, nhưng có thể decode để kiểm tra 16 byte.

Không dùng UUID: UUID chứa phiên bản/variant và dài hơn; bài muốn token cố định 128-bit.

## 3. Idempotent issue

Duy trì index phụ `by_pair[(resource_id, revision)] -> handle` hoặc quét map. Với 10.000 handle, quét là chấp nhận được; index giúp O(1).

Khi prune hoặc revoke, cập nhật index. Nếu quên, issue trả handle đã chết.

## 4. Prune

```
if len(handles) >= max:
    for h, e in list(handles.items()):
        if e.revoked or now >= e.expires_at:
            del handles[h]
    if len(handles) >= max: raise Capacity
```

Không xóa handle sống để nhường chỗ: UI đang dùng sẽ bị `UNKNOWN_HANDLE` khó hiểu.

## 5. Resolve

Thứ tự quan trọng cho UX:

- `revoked` trước `expired`: handle đã thu hồi chủ động nên báo revoked dù đã quá hạn? Bài chọn revoked trước; ghi rõ. Nếu muốn expired trước, đổi và cập nhật test.
- `expired` trước `stale`: handle cũ quá hạn thì expired hữu ích hơn.
- `resource missing` trước `stale`.
- `stale` cuối.

## 6. Persistence

`to_dict`/`from_dict`:

- Chỉ lưu dữ liệu cần thiết; không lưu index phụ (dựng lại khi load).
- Validate toàn bộ trước khi nhận; nếu một entry sai → `UNSUPPORTED_STATE`, không sửa state hiện tại.
- Sort key khi ghi để output ổn định (dù JSON object không đảm bảo thứ tự ngữ nghĩa).
- Không lưu clock/nonce.

## 7. Bẫy thường gặp

- **Đưa resource ID vào handle**: phá tính mờ; dù base64 không phải mã hóa.
- **Dùng hash(resource+revision) làm handle**: đoán được nếu biết ID; không phải capability.
- **Không kiểm tra revision khi resolve**: handle cũ vẫn mở resource mới, sai hợp đồng.
- **Gia hạn TTL khi resolve**: handle sống mãi; TTL mất ý nghĩa.
- **Prune xóa tombstone ngay**: không phân biệt revoked/unknown.
- **Revoke rồi issue lại cùng cặp**: handle mới hay cũ? Bài: handle cũ revoked không được tái sử dụng; issue tạo handle mới.
- **Clock âm**: chặn.
- **So sánh `now > expires_at`**: sai biên; phải `>=`.
- **Không giới hạn capacity**: map phình.
- **Log full handle**: token bearer; che 6 ký tự cuối nếu cần debug.

## 8. Gỡ lỗi

- In `len(handles)` và số tombstone.
- Test idempotent: issue 2 lần, so handle và độ dài map.
- Test revision đổi giữa hai lần resolve.
- Test reload: save, tạo registry mới, resolve.
- Test prune với max nhỏ (ví dụ 3) để không phải tạo 10000.
- Kiểm tra regex bằng các chuỗi sai độ dài/ký tự.

## 9. Kiểm chứng

```bash
cd 34_REVISION_BOUND_HANDLES
python -m handles --state fixtures/state.json --revisions fixtures/revisions.json \
  --nonces fixtures/nonces.json issue res-a 3 --now 0
python -m handles --state /tmp/state.json --revisions fixtures/revisions.json resolve h1_AAECAwQFBgcICQoLDA0ODw --now 10
```

Test:

```bash
python -m unittest discover -s tests -v
```

Kiểm tra handle không lộ ID:

```python
assert "res-a" not in handle
assert "3" not in handle[3:]   # không đảm bảo tuyệt đối với base64, nhưng kiểm tra mẫu
```

## 10. Gợi ý

- Viết `NonceSource` giả trả danh sách byte cố định; hết danh sách → lỗi test.
- Tách `validate_state(dict)` để test lỗi load.
- Dùng `dataclass(frozen=True)` cho entry.
- Giữ index `by_pair` cập nhật trong một hàm `_put` duy nhất.
- Đừng dùng `time.time()`; luôn nhận `now`.

## 11. Mở rộng

1. Handle cho cạnh với khóa `(edge_id, revision)`.
2. TTL trượt có giới hạn tuyệt đối.
3. Ký handle bằng HMAC để kiểm tra định dạng không cần store (đổi đánh đổi).
4. Batch resolve.
5. Đồng bộ registry nhiều tiến trình với khóa file.
