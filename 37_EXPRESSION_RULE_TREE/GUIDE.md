# GUIDE 37 — Thiết kế cây quy tắc

## 1. Kiến trúc

```
rules/
├─ nodes.py      # And, Or, Not, Compare
├─ parser.py     # parse/serialize, validate
├─ rule.py       # Rule, hash, id
├─ evaluate.py   # resolve, compare
├─ cli.py
fixtures/
```

`nodes.py` và `evaluate.py` thuần; `rule.py` quản metadata; CLI chỉ nối.

## 2. Node

```python
@dataclass(frozen=True)
class Node:
    type: str
    # ...
```

Có thể dùng class riêng `AndNode`, `OrNode`, `NotNode`, `CompareNode` với `evaluate(report)` và `return_type`. Điều này tránh `if type == ...` rải rác.

## 3. Parser

1. Kiểm tra `dict`.
2. `type` phải là chuỗi thuộc tập.
3. Kiểm tra **đúng** bộ khóa:
   - and/or: `{"type","children"}`;
   - not: `{"type","child"}`;
   - cmp: `{"type","field","op","value"}`.
4. Đệ quy với `depth`, `node_count` (dùng list một phần tử hoặc object mutable).
5. Kiểm tra kiểu trẻ: and/or/not chỉ nhận boolean node.
6. Trả node.

`serialize(node)` trả dict theo cùng khóa; không dùng `dataclasses.asdict` nếu nó thêm trường nội bộ.

## 4. Hash canonical

```python
payload = json.dumps(serialize(root), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
return hashlib.sha1(payload.encode("utf-8")).hexdigest()
```

Không hash metadata: đổi tên rule không đổi id logic. Ghi rõ trong README.

## 5. Field resolution

```python
cur = report
for part in field.split("."):
    if not isinstance(cur, dict): raise TypeMismatch
    if part not in cur: raise FieldMissing(field)
    cur = cur[part]
```

Không dùng `eval`, `getattr`, hay truy cập thuộc tính. Không cho segment bắt đầu `_` để tránh dunder nếu sau này có adapter.

## 6. So sánh

Viết `category(value)`:

```
bool -> "bool" (kiểm tra trước int)
int/float -> "number" nếu isfinite
str -> "string"
None -> "null"
list -> "list"
dict -> "object"
```

`eq`: category bằng nhau và `==`; với list/dict nếu muốn hỗ trợ, so sánh sâu; bài chỉ cmp scalar/list cho `in`, nên `eq` list vẫn có thể so sánh nhưng không khuyến khích.

`lt/...`: category cả hai `number`.

`contains`: string/string hoặc list/scalar (dùng `eq` strict cho từng phần tử).

## 7. Short-circuit

```python
def eval_and(children, report):
    for child in children:
        if not child.evaluate(report):
            return False
    return True
```

Trả `bool`; `Rule.execute` đổi `float(bool)`.

Không đánh giá tất cả rồi `all(...)` nếu muốn short-circuit (Python `all` có short-circuit, nhưng generator vẫn ổn). Viết rõ để người đọc thấy.

## 8. Bẫy thường gặp

- **Hash bằng `repr`**: không ổn định; dùng JSON canonical.
- **Hash cả metadata**: đổi tên làm đổi id; sai hợp đồng.
- **Không sort_keys**: thứ tự khóa phụ thuộc dict; hash đổi.
- **Dùng `json.dumps` mặc định**: có khoảng trắng; vẫn ổn định nhưng khác ví dụ. Chọn compact và ghi rõ.
- **Cho `cmp` làm root**: source yêu cầu OperatorNode; bài giữ.
- **Không kiểm tra purpose**: entity sai kiểu vẫn chạy.
- **Đánh giá hết `and`**: field thiếu ở nhánh sau gây lỗi dù nhánh trước false.
- **Dùng `bool` như number**: `True == 1`; phải tách category.
- **Không chặn NaN**: so sánh lặp lại không nhất quán; chặn.
- **`copy` nông**: sửa bản copy ảnh hưởng gốc.
- **Parse lỗi trả `None`**: luôn ném `ParseError` có đường dẫn node.

## 9. Gỡ lỗi

- In AST canonical và hash cho rule mẫu.
- Test từng node/eval riêng.
- Thử report thiếu field ở nhánh 1 vs nhánh 2.
- Thử `true eq 1` và `1 eq 1.0`.
- Kiểm tra depth/node count bằng rule sinh tự động trong test.
- Kiểm tra `to_entity`/`from_entity` round-trip với `purpose` bị sửa.

## 10. Kiểm chứng

```bash
cd 37_EXPRESSION_RULE_TREE
python -m rules --rule fixtures/rules/rsi.json --report fixtures/reports/pass.json \
  --prefix rsi --now 2026-01-01T00:00:00Z --out /tmp/r.json
python - <<'PY'
import json
d=json.load(open('/tmp/r.json'))
assert d['result']==1.0, d
assert d['hash']=='3c9980daf4e99c2f3c98cb82f8f8ac3d04eea370', d
assert d['rule_id'].startswith('rsi_')
print(d['name'])
PY
```

Test:

```bash
python -m unittest discover -s tests -v
```

## 11. Gợi ý

- Viết parser + hash trước; evaluator sau.
- Dùng một lớp `ParseContext` giữ `depth`, `count`, `path` để báo lỗi.
- Đừng dùng `assert` cho validate runtime.
- Với lỗi, kèm `path` kiểu `root.children[2].field`.
- Giữ `created_at`/`updated_at` ngoài hash.

## 12. Mở rộng

1. Thêm phép số học và node `field` số.
2. Thêm `weighted_sum` cho scoring.
3. Thêm `between`, `matches` (regex có giới hạn).
4. Thêm biên dịch sang biểu thức SQL an toàn với tham số.
5. Thêm version schema và migration AST.
