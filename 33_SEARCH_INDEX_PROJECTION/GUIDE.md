# GUIDE 33 — Thiết kế projection

## 1. Kiến trúc

```
index_projection/
├─ models.py     # CanonicalRecord, Row, Snapshot
├─ loader.py     # manifest + JSONL
├─ project.py    # row, digest, sample
├─ search.py     # tokenize + in-memory scoring
├─ cli.py
fixtures/
```

`project` không đọc file; nhận list record. `loader` chịu I/O. `search` nhận list record đã validate.

## 2. Dữ liệu

```python
@dataclass(frozen=True)
class CanonicalRecord:
    resource_id: str
    revision: int
    schema_version: int
    zone_id: str
    kind: str                 # đã ánh xạ
    state: str
    linked: tuple[str, ...]
    title: str
    body: str

@dataclass(frozen=True)
class Row:
    resource_id: str
    zone_id: str
    revision: int
    canonical_schema_version: int
    record_kind: str
    state: str
    linked_resource_ids: tuple[str, ...]
```

Giữ body trong `CanonicalRecord` để hash, nhưng không đưa vào `Row` hay output.

## 3. Thứ tự và digest

1. Validate từng record, gắn số dòng để báo lỗi.
2. Sắp theo `(resource_id, revision)`.
3. Kiểm tra trùng cặp.
4. Tạo row theo thứ tự đã sắp.
5. Digest trên **cùng thứ tự**, dùng body hash.

`json.dumps` với `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`. Nếu bạn đổi `ensure_ascii`, digest đổi; ghi rõ trong README nếu chọn khác.

Chuỗi rỗng cho 0 record: không thêm `\n`.

## 4. Mẫu giới hạn

```python
rows_sample = rows[:512]
```

Không cắt trước khi sắp; không cắt sau khi đã lọc. `row_count = len(rows)`.

Nếu muốn tránh giữ 100k row trong bộ nhớ, có thể dùng heap 512; nhưng digest vẫn cần duyệt đủ. Bài chấp nhận giữ list.

## 5. Tokenizer

```python
text = unicodedata.normalize("NFKC", title + " " + body).lower()
tokens = {t for t in re.findall(r"[^\W_]+", text, re.UNICODE)
          if t not in STOPWORDS and 1 <= len(t) <= 64}
```

`[^\W_]` bao gồm chữ và số Unicode, loại `_`. Với tiếng Việt, token giữ dấu; query cũng vậy.

Không cần sắp token cho scoring; nhưng nếu output debug, sắp để ổn định.

## 6. Scoring

```
q = tokenize(query)
for rec in records if kind == "memory_item":
    score = len(q & doc_tokens(rec))
sort by (-score, resource_id, revision)
take 20
```

Điểm là số token khớp, không chuẩn hóa. Nếu muốn BM25/IDF, đó là mở rộng; đừng trộn vào bài cơ bản.

## 7. Bẫy thường gặp

- **Đưa token vào row**: rò dữ liệu; row chỉ metadata.
- **Digest trên thứ tự file**: đảo file sẽ đổi digest sai. Luôn sắp.
- **Digest không gồm body**: đổi body không phát hiện được; bài yêu cầu body hash.
- **Xuất body hash như body**: hash an toàn hơn nhưng vẫn là metadata; chấp nhận trong digest, không cần output.
- **`row_count = len(sample)`**: sai khi >512.
- **Cắt mẫu trước sắp**: mẫu không phải “512 nhỏ nhất”.
- **Kind lạ làm lỗi cả lô**: bài yêu cầu `unknown`.
- **Trùng link**: nên lỗi để canonical sạch.
- **Search trả cả record**: rò; chỉ trả ba trường.
- **`lower()` không NFKC**: `ﬁ` và `fi` khác; chuẩn hóa trước.
- **Stopword loại nhầm `a` trong tên**: chấp nhận; đơn giản.

## 8. Gỡ lỗi

- In `row_count`, `len(rows)`, digest.
- Kiểm tra JSON bằng hàm đệ quy tìm khóa cấm.
- Đảo dòng fixture, so digest.
- Sửa một body, xác nhận digest đổi nhưng row không đổi.
- Kiểm tra 513 record: `rows` dài 512, `row_count` 513.
- Query `alpha`, `body`, rỗng, toàn stopword.

## 9. Kiểm chứng

```bash
cd 33_SEARCH_INDEX_PROJECTION
python -m index_projection --manifest fixtures/canonical/manifest.json \
  --records fixtures/canonical/records.jsonl --out /tmp/s.json
python - <<'PY'
import json
s=json.load(open('/tmp/s.json'))
assert s['row_count']==3, s
assert s['canonical_digest']=='f5544d167c2c54035c7cb0d5ad20d4dc81e7d20d3a8219d8f110a673473b9ac2'
def keys(o):
    if isinstance(o,dict):
        for k,v in o.items(): yield k; yield from keys(v)
    elif isinstance(o,list):
        for v in o: yield from keys(v)
assert not ({'tokens','title','body'} & set(keys(s))), list(keys(s))
print('ok')
PY
```

Search:

```bash
python -m index_projection --manifest fixtures/canonical/manifest.json \
  --records fixtures/canonical/records.jsonl --query alpha
```

## 10. Gợi ý

- Viết validate + project trước; search sau.
- Dùng `dataclasses.asdict` nhưng loại `title/body` bằng cách không đưa vào Row.
- `hashlib.sha256` trên chuỗi UTF-8; không dùng `repr`.
- Test digest bằng fixture cố định; đừng tự sinh expected trong test.
- Với lỗi dòng, luôn kèm số dòng 1-based.

## 11. Mở rộng

1. Dùng heap để giữ 512 row nhỏ nhất mà không giữ toàn bộ.
2. Thêm zone filter, digest chỉ trên zone đã chọn.
3. Thêm token bucket/posting list.
4. Thêm mã hóa at-rest; giữ nguyên schema output.
5. Thêm rebuild incrementally khi canonical thêm record.
