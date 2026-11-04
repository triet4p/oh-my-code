# SPEC 37 — Rule engine dạng cây

## 1. AST

```json
{
  "type": "and",
  "children": [
    {"type": "cmp", "field": "metrics.rsi14", "op": "lt", "value": 30},
    {"type": "cmp", "field": "metrics.close", "op": "gt", "value": 10},
    {"type": "not", "child": {"type": "cmp", "field": "trend", "op": "eq", "value": "up"}}
  ]
}
```

Node:

| Type | Trường | Con | Return type |
|---|---|---|---|
| `and` | `children` 2–8 | boolean | `boolean` |
| `or` | `children` 2–8 | boolean | `boolean` |
| `not` | `child` đúng 1 | boolean | `boolean` |
| `cmp` | `field`, `op`, `value` | không | `boolean` |

`cmp.op` ∈ `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`, `contains`.

Root phải là `and`/`or`/`not`. `cmp` làm root → `ROOT_NOT_OPERATOR`.

Trường lạ trong node → `UNKNOWN_FIELD` (để canonical hash không bị ảnh hưởng bởi dữ liệu thừa).

## 2. Giới hạn

- Độ sâu ≤32 (root depth 1).
- Tổng node ≤256.
- `field` khớp `^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*){0,7}$`.
- `value` cho `cmp`: scalar JSON hoặc list ≤100 phần tử; string ≤1024; number hữu hạn.
- `eq`/`ne`/`in`/`contains` chấp nhận scalar; `lt/le/gt/ge` chỉ number.
- `in` yêu cầu `value` là list.
- `contains` yêu cầu field là string (value string) hoặc list (value scalar).

## 3. `Rule`

```python
class Rule:
    root: Node
    rule_id: str | None
    name: str
    description: str
    status: "ready" | "deprecated"
    created_at: datetime
    updated_at: datetime
```

- Khởi tạo root không phải operator → `TypeError("The root of a rule must be an instance of OperatorNode.")` (giữ thông điệp tinh thần nguồn).
- `purpose` property = `root.return_type` (`"boolean"`).
- `execute(report)`:
  - status `deprecated` → `0.0`, không đọc report.
  - ngược lại `float(root.evaluate(report))`; true → `1.0`, false → `0.0`.
- `copy()` deepcopy độc lập.
- `to_entity()`:
  - `root` là AST JSON canonical (cùng cấu trúc input).
  - `purpose`, `status`, `created_at`, `updated_at`, `metrics`.
- `from_entity(data)`:
  - thiếu `root`/`root` rỗng → `ValueError("Rule data is missing the logic tree 'root'.")`.
  - parse lỗi → `ValueError` bọc `ParseError`, nêu `rule_id`.
  - nếu `purpose` có và khác `root.return_type` → `TypeError` nêu cả hai.
  - status lạ → `ValueError`.
- `get_hash()`: SHA-1 của `json.dumps(root_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`, hex lowercase.
- `auto_id_name(prefix)`:
  - `prefix` khớp `^[a-z][a-z0-9_]{0,15}$`;
  - `rule_id = f"{prefix}_{hash}"`;
  - `name = f"{prefix.upper()} {hash[:10]}...."`.

## 4. Đánh giá

Report là dict JSON. Truy cập field bằng cách tách `.` và đi theo dict.

- Key không tồn tại → `FIELD_MISSING` kèm đường dẫn.
- Key tồn tại nhưng giá trị `None`: hợp lệ; chỉ so sánh với `null`.
- `and`: đánh giá trái sang phải, dừng ở false đầu tiên → `0.0`; tất cả true → `1.0`.
- `or`: dừng ở true đầu tiên → `1.0`; tất cả false → `0.0`.
- `not`: đảo boolean.
- Trẻ của `and/or/not` phải trả boolean; parser đã kiểm tra kiểu tĩnh, nên không có number ở đây.

Short-circuit là bắt buộc: nhánh sau có thể tham chiếu field thiếu mà không lỗi nếu nhánh trước quyết định.

## 5. So sánh

Phân loại giá trị: `number` (int/float, **không** bool, hữu hạn), `string`, `bool`, `null`, `list`, `object`.

- `eq`/`ne`: cùng loại và bằng/khác. `1 != true`; `1 == 1.0` (cùng number).
- `lt/le/gt/ge`: cả hai number; sai kiểu → `TYPE_MISMATCH`.
- `in`: field scalar; value list; so sánh strict với từng phần tử.
- `contains`:
  - field string + value string: `value in field`;
  - field list + value scalar: `value` có trong list theo strict;
  - khác → `TYPE_MISMATCH`.

NaN/Infinity trong report → `TYPE_MISMATCH` khi tham gia so sánh số; với `eq` cũng coi là không hợp lệ.

## 6. Ví dụ cụ thể

Rule `fixtures/rules/rsi.json` như AST mục 1. Canonical JSON:

```json
{"children":[{"field":"metrics.rsi14","op":"lt","type":"cmp","value":30},{"field":"metrics.close","op":"gt","type":"cmp","value":10},{"child":{"field":"trend","op":"eq","type":"cmp","value":"up"},"type":"not"}],"type":"and"}
```

- `get_hash()` = `3c9980daf4e99c2f3c98cb82f8f8ac3d04eea370`.
- `auto_id_name("rsi")` → id `rsi_3c9980daf4e99c2f3c98cb82f8f8ac3d04eea370`, name `RSI 3c9980daf4....`.

Report A:

```json
{"metrics": {"rsi14": 25, "close": 12.5}, "trend": "down"}
```

- rsi 25 < 30 → true; close 12.5 > 10 → true; trend "down" eq "up" → false, not → true.
- `execute` → `1.0`.

Report B: rsi 55 → `and` dừng ngay, trả `0.0`; không cần `close`/`trend`.

Report C: thiếu `metrics` → `FIELD_MISSING: metrics.rsi14`.

Report D: `rsi14 = "25"` → `TYPE_MISMATCH`.

Report E: `trend="up"` → `0.0`.

Deprecated: cùng report C nhưng status deprecated → `0.0`, không lỗi.

## 7. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Root `cmp` | `ROOT_NOT_OPERATOR` |
| 2 | `and` 1 con | `ARITY` |
| 3 | `and` 9 con | `ARITY` |
| 4 | `not` 2 con | `ARITY` |
| 5 | `cmp` có children | `UNKNOWN_FIELD` hoặc `ARITY` |
| 6 | Op lạ | `UNKNOWN_OP` |
| 7 | Field `a..b` | `INVALID_FIELD` |
| 8 | Field bắt đầu `_` | `INVALID_FIELD` |
| 9 | Depth 33 | `DEPTH_LIMIT` |
| 10 | 257 node | `NODE_LIMIT` |
| 11 | `in` value không list | `INVALID_VALUE` |
| 12 | `lt` value string | `TYPE_MISMATCH` khi eval/parse value |
| 13 | Report không phải dict | `INVALID_REPORT` |
| 14 | Missing field ở nhánh bị short-circuit | không lỗi |
| 15 | Missing field ở nhánh được đánh giá | `FIELD_MISSING` |
| 16 | null eq null | true |
| 17 | `true eq 1` | false |
| 18 | `1 eq 1.0` | true |
| 19 | `"abc" contains "b"` | true |
| 20 | `[1,2] contains 2` | true |
| 21 | `[1] contains "1"` | false |
| 22 | Purpose entity `"number"` | TypeError |
| 23 | Entity thiếu root | ValueError |
| 24 | Hash đổi khi đổi 30→29 | có |
| 25 | Copy rồi sửa root bản copy | bản gốc không đổi |

## 8. Output CLI

```json
{
  "rule_id": "rsi_3c9980daf4e99c2f3c98cb82f8f8ac3d04eea370",
  "name": "RSI 3c9980daf4....",
  "purpose": "boolean",
  "hash": "3c9980daf4e99c2f3c98cb82f8f8ac3d04eea370",
  "status": "ready",
  "result": 1.0
}
```

## 9. Tiêu chí chấp nhận

- [ ] Hash ví dụ khớp.
- [ ] Report A-E cho đúng kết quả/lỗi.
- [ ] Short-circuit không đánh giá nhánh sau.
- [ ] Deprecated trả 0.0 kể cả report thiếu.
- [ ] Purpose mismatch ném TypeError.
- [ ] Thiếu root ném ValueError đúng thông điệp.
- [ ] Parse → serialize → parse cho AST giống nhau.
- [ ] Copy độc lập.
- [ ] Cùng rule + report cho cùng output.

## 10. Non-goals

- Không có phép toán số học (`+`, `*`), biến, hàm.
- Không có Pydantic; parser tự viết.
- Không có UI, không lưu DB.
- Không đánh giá trên dữ liệu thời gian thực.
