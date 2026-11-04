# 37 — Cây quy tắc biểu thức

## Mục tiêu

Xây dựng engine quy tắc dạng cây: node logic `and/or/not` và node so sánh `cmp`, root bắt buộc là toán tử, tuần tự hóa/giải tuần tự ổn định, kiểm tra `purpose` khớp kiểu trả về, hash SHA-1 của riêng cây để nhận diện quy tắc bất biến, và trạng thái `deprecated` trả 0.

## Giá trị

- Quy tắc nghiệp vụ nên là **dữ liệu có cấu trúc**, không phải chuỗi `eval`.
- Hash trên phần logic (không metadata) cho phép nhận diện cùng một quy tắc dù đổi tên.
- Học short-circuit và hệ quả của nó với field thiếu.
- Học so sánh kiểu chặt: `true` không bằng `1`, chuỗi không so được với số.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình–khó |
| Điều kiện | Đệ quy, JSON canonical, kiểu dữ liệu Python |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/itapia`
- File nguồn: <https://github.com/triet4p/itapia/blob/main/backend/shared/itapia_common/rules/rule.py>
- Hành vi quan sát được:
  - `if not isinstance(root, OperatorNode): raise TypeError("The root of a rule must be an instance of OperatorNode.")`
  - `purpose` trả `self.root.return_type`.
  - `execute`: nếu `RuleStatus.DEPRECATED` → `0.0`; ngược lại `self.root.evaluate(report)`.
  - `to_entity` dùng `serialize_tree(self.root)`; `from_entity` dùng `parse_tree`, kiểm tra `purpose_from_data != root_node.return_type` → `TypeError`.
  - Thiếu root: `ValueError("Rule data is missing the logic tree 'root'.")`.
  - `get_hash`: `sha1(json.dumps(self.to_entity().root.model_dump()))`.
  - `auto_id_name(prefix)`: `rule_id = f"{prefix}_{hash}"`, `name = f"{prefix.upper()} {hash[:10]}...."`.
  - `copy` dùng `deepcopy`.

**Phần là thiết kế của bài:** bộ node cụ thể, canonical hash (sort/compact), giới hạn độ sâu/số node, short-circuit, so sánh strict, CLI/fixture. Nguồn dùng Pydantic và `json.dumps` mặc định; bài định nghĩa canonical rõ ràng.

## Hành vi bài tập yêu cầu

- Root là `and`/`or`/`not`; `cmp` làm root bị từ chối.
- `and/or` có 2–8 con boolean; `not` đúng 1; `cmp` không có con.
- Field dạng đường dẫn dict, tối đa 8 segment, không segment bắt đầu `_`.
- `execute` trả `1.0`/`0.0`; deprecated trả `0.0` mà không đọc report.
- Short-circuit trái sang phải.
- Hash SHA-1 trên JSON canonical của root, không gồm metadata.
- `auto_id_name` đặt id/tên theo prefix + hash.
- `from_entity` kiểm tra root/purpose/status; round-trip giữ AST.

## Phạm vi

Trong phạm vi: AST, parser, evaluate, hash, id, entity, CLI.

Ngoài phạm vi: phép số học, biến, hàm, regex, UI, lưu DB, biên dịch SQL.

## Fixture offline

- `fixtures/rules/rsi.json`, `deprecated.json`, `bad-root.json`, `purpose-mismatch.json`, `deep.json`.
- `fixtures/reports/pass.json`, `fail-shortcircuit.json`, `missing.json`, `type-mismatch.json`.
- `fixtures/expected/`.
- Không mạng, không dữ liệu thật; số liệu tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — AST, giới hạn, ngữ nghĩa, ví dụ hash.
- [GUIDE.md](GUIDE.md) — parser/evaluator và kiểm chứng.
