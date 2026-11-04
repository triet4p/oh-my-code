# SPEC 33 — Projection chỉ mục

## 1. Đầu vào

`manifest.json`:

```json
{ "format_version": 3 }
```

`records.jsonl`, mỗi dòng một object:

```json
{
  "resource_id": "res-a",
  "revision": 1,
  "schema_version": 1,
  "zone_id": "z1",
  "kind": "memory_item",
  "state": "active",
  "linked_resource_ids": ["res-b"],
  "title": "Alpha",
  "body": "alpha body"
}
```

Ràng buộc:

| Trường | Ràng buộc |
|---|---|
| `resource_id` | 1–128 byte UTF-8, không ký tự điều khiển |
| `revision` | số nguyên 0…2^63−1 |
| `schema_version` | số nguyên 1…2^31−1 |
| `zone_id` | 1–64 ký tự, không điều khiển |
| `kind` | chuỗi; xem ánh xạ |
| `state` | 1–128 ký tự, không điều khiển |
| `linked_resource_ids` | mảng ≤512, mỗi phần tử hợp lệ như `resource_id`, không trùng trong mảng |
| `title` | chuỗi ≤512 ký tự |
| `body` | chuỗi ≤1 MiB UTF-8 |

Tổng số record ≤ `100000`. Dòng trắng bị bỏ; dòng không parse được → `INVALID_RECORD` kèm số dòng.

## 2. Ánh xạ kind

| Input | Row kind |
|---|---|
| `memory_item` | `memory_item` |
| `registered_source` | `registered_source` |
| `relation` | `relation` |
| `lifecycle` | `lifecycle` |
| `retained_revision` | `retained_revision` |
| `preserved_source_snapshot` | `preserved_source_snapshot` |
| `feedback` | `feedback` |
| `proposal` | `proposal` |
| bất kỳ chuỗi khác | `unknown` |

Không đoán loại gần giống. Kind lạ vẫn tạo row `unknown`, không làm hỏng lô.

## 3. Row

```json
{
  "resource_id": "res-a",
  "zone_id": "z1",
  "revision": 1,
  "canonical_schema_version": 1,
  "record_kind": "memory_item",
  "state": "active",
  "linked_resource_ids": ["res-b"]
}
```

- Giữ thứ tự `linked_resource_ids` như đầu vào.
- Không thêm `title`, `body`, `tokens`, `score`, hay thời gian.
- Sắp xếp toàn bộ row theo `(resource_id, revision)` Unicode tăng dần.
- Trùng `(resource_id, revision)` → `DUPLICATE_REVISION`, dừng.

## 4. Digest canonical

Chuỗi canonical gồm các dòng, mỗi record một dòng, sắp theo `(resource_id, revision)`:

```json
{
  "body_sha256": "<sha256 hex của body UTF-8>",
  "kind": "<kind đã ánh xạ>",
  "linked_resource_ids": ["…"],
  "resource_id": "…",
  "revision": 1,
  "schema_version": 1,
  "state": "…",
  "zone_id": "…"
}
```

Quy tắc serialize: `json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`. Nối các dòng bằng `\n`, thêm `\n` cuối (kể cả 0 record → chuỗi rỗng, không có newline). `canonical_digest = sha256(chuỗi.encode("utf-8")).hexdigest()`.

Body không xuất hiện trong output; chỉ hash của nó tham gia digest.

## 5. Snapshot

```json
{
  "schema_version": 3,
  "canonical_digest": "f5544d167c2c54035c7cb0d5ad20d4dc81e7d20d3a8219d8f110a673473b9ac2",
  "row_count": 3,
  "rows": [ … ]
}
```

- `row_count` = tổng row, không phải `len(rows)`.
- `rows` = tối đa 512 dòng đầu của danh sách đã sắp.
- `schema_version` = 3.
- Không có khóa `tokens`/`title`/`body` ở bất kỳ đâu.

## 6. Tokenizer và tìm kiếm

Token hóa `title + " " + body`:

1. Unicode NFKC, lower.
2. Tách theo cụm chữ/số Unicode (`re.findall(r"[^\W_]+", text, re.UNICODE)`).
3. Bỏ stopword: `a, an, and, are, as, at, be, by, for, in, is, of, on, or, the, to, with`.
4. Giữ token dài 1–64; bỏ token toàn số? **Không**, giữ số.
5. Tập token duy nhất, không cần sắp cho scoring; sắp khi debug.

Mỗi bản ghi có `SearchIndexDocument` chỉ tồn tại trong bộ nhớ, gồm `resource_id`, `revision`, `tokens`. Không serialize nó.

`search(query)`:

- Token hóa query cùng quy tắc.
- Chỉ xét record `kind == memory_item`.
- `score = |query_tokens ∩ doc_tokens|` (số token khớp).
- Bỏ score 0.
- Sắp `score` giảm, rồi `resource_id` tăng, rồi `revision` tăng.
- Trả tối đa 20 hit: `{resource_id, revision, score}`.
- Không trả token, title, body.

## 7. Ví dụ cụ thể

Records:

1. `res-a`, rev 1, zone `z1`, schema 1, kind `memory_item`, state `active`, linked `["res-b"]`, title `Alpha`, body `alpha body`.
2. `res-b`, rev 2, zone `z2`, schema 1, kind `registered_source`, state `active`, linked `[]`, title `Beta`, body `beta body`.
3. `res-c`, rev 1, zone `z1`, schema 1, kind `mystery`, state `archived`, linked `[]`, title `Gamma`, body `gamma body`.

Snapshot:

- `row_count = 3`.
- `record_kind` lần lượt `memory_item`, `registered_source`, `unknown`.
- `canonical_digest = f5544d167c2c54035c7cb0d5ad20d4dc81e7d20d3a8219d8f110a673473b9ac2`.
- `rows` đủ 3 (dưới 512).
- Không có chuỗi `alpha body`, `Beta`, hay `tokens` trong JSON.

Query `alpha`:

```json
[
  { "resource_id": "res-a", "revision": 1, "score": 1 }
]
```

Query `body`:

- `res-a` score 1; `res-b` không xét vì không phải `memory_item`; `res-c` không xét.
- Kết quả chỉ `res-a`.

Query `alpha beta`:

- `res-a` score 1 (chỉ alpha), `res-b` bị loại theo kind.
- Kết quả `res-a`.

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | 0 record | digest = sha256(""), row_count 0, rows [] |
| 2 | 513 record | rows 512, row_count 513 |
| 3 | 100001 record | `ROW_LIMIT` |
| 4 | Version 4 | `UNSUPPORTED_FORMAT`, không row |
| 5 | Duplicate `(id, rev)` | `DUPLICATE_REVISION` |
| 6 | Cùng id khác revision | hai row |
| 7 | Kind lạ | `unknown` |
| 8 | Linked 513 | `TOO_MANY_LINKS` |
| 9 | Linked trùng | `DUPLICATE_LINK` |
| 10 | Body đổi, metadata không đổi | digest đổi, row không đổi |
| 11 | Revision đổi | thứ tự và digest đổi |
| 12 | Thứ tự file đảo | snapshot giống hệt |
| 13 | Resource ID có chữ hoa | giữ nguyên, sắp theo Unicode |
| 14 | Body chứa token trùng | token set loại trùng |
| 15 | Query rỗng | hits [] |
| 16 | Query toàn stopword | hits [] |
| 17 | Query `RES` | lower, khớp `res` |
| 18 | Kind `Memory_Item` | `unknown` (phân biệt hoa thường) |
| 19 | Body > 1 MiB | `BODY_TOO_LARGE` |
| 20 | Dòng JSON hỏng | `INVALID_RECORD`, nêu số dòng |

## 9. Tiêu chí chấp nhận

- [ ] Snapshot fixture khớp digest ở mục 7.
- [ ] `row_count` đúng khi >512.
- [ ] Không output nào chứa `tokens`, `title`, `body` (kiểm tra bằng walk JSON).
- [ ] Đảo thứ tự record cho cùng snapshot.
- [ ] Version 4 fail-closed với 0 row.
- [ ] Search chỉ trả metadata và đúng thứ hạng.
- [ ] Trùng `(id, revision)` bị chặn.
- [ ] Chạy hai lần cho byte output giống nhau.

## 10. Non-goals

- Không mã hóa chỉ mục, không AEAD, không khóa.
- Không token bucket/posting list/merge.
- Không stemming ngôn ngữ tự nhiên.
- Không đồng bộ zone, không rebuild từ DB.
