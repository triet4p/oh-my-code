# SPEC 59 — Truy hồi theo mục lục thay vì vector

## 1. Mô hình tài liệu

```json
{
  "sections": [
    {"id": "s1", "title": "Giới thiệu", "text": "hệ thống gồm ba phần"},
    {"id": "s2", "title": "Cài đặt", "text": "cài đặt hệ thống bằng lệnh"},
    {"id": "s3", "title": "Vận hành", "text": "vận hành hàng ngày"}
  ]
}
```

- `id` duy nhất, khớp `^[a-z][a-z0-9_-]*$`.
- Thứ tự trong mảng là **thứ tự tài liệu** — dùng cho hoà điểm và dự phòng.
- `title`, `text` là chuỗi; `text` có thể rỗng.

## 2. Giao diện bộ chọn

```text
class SectionSelector(Protocol):
    def select(self, query: str, sections: list[Section], k: int) -> list[str]
```

- Trả danh sách id, **có thể** rỗng, có thể chứa id không tồn tại.
- Không được sửa `sections`.
- `ValidatingSelector` bọc một selector khác và thực hiện kiểm tra (mục 3).

## 3. Kiểm tra và dự phòng

```text
candidates = selector.select(query, sections, k)
valid = []
warnings = []
với mỗi id trong candidates, theo thứ tự:
    nếu id không có trong content_map: warnings.append(f"unknown_id:{id}"); dropped.append(id)
    ngược lại nếu đã có trong valid: warnings.append(f"duplicate_id:{id}")
    ngược lại: valid.append(id)
    nếu len(valid) == k: dừng
nếu valid rỗng:
    valid = hai id đầu theo thứ tự tài liệu (hoặc ít hơn nếu tài liệu ngắn hơn)
    warnings.append("fallback_used")
```

- `valid` giữ **thứ tự bộ chọn** trả về (không sắp lại).
- Nếu tài liệu có 0 mục ⇒ `EmptyDocument`.
- `k` mặc định `3`; `k < 1` ⇒ `InvalidK`.

## 4. `LexicalSelector`

### 4.1 Token hoá

- Chuyển `query`, `title`, `text` về chữ thường (`str.lower()`).
- Tách theo mọi ký tự **không** phải chữ hoặc số Unicode: dùng `re.split` với lớp `[^\w]+` và `re.UNICODE`.
- Bỏ token rỗng; **giữ** trùng trong tài liệu (để tính `tf`), **bỏ** trùng trong truy vấn (mỗi từ khoá tính một lần).

### 4.2 Điểm

Với mỗi mục `s` và truy vấn `q` (tập từ khoá duy nhất):

```text
corpus(t) = title + " " + text của mục
tf(t, s)  = số lần t xuất hiện trong corpus(s)
df(t)     = số mục có tf(t, s) > 0
idf(t)    = ln(1 + N / (1 + df(t)))       với N = số mục
score(s)  = Σ_{t trong q} tf(t, s) * idf(t)
```

Chọn các mục có `score > 0`, sắp `(-score, thứ tự tài liệu)`, cắt `k`.
Nếu không mục nào có `score > 0` ⇒ trả `[]` (để đường dự phòng chạy).

`math.log` tự nhiên.

### 4.3 Ví dụ số

Tài liệu mục 1; truy vấn `"hệ thống"`.

Từ khoá: `["hệ", "thống"]` (hai từ, không trùng).

- `df("hệ") = 2` (s1, s2); `N = 3` ⇒ `idf = ln(1 + 3/3) = ln 2 = 0.6931472`.
- `df("thống") = 2` ⇒ cùng `idf`.
- `tf("hệ", s1) = 1`; `tf("thống", s1) = 1` ⇒ `score(s1) = 1.3862944`.
- `s2`: `tf("hệ") = 1`, `tf("thống") = 1` ⇒ `1.3862944`.
- `s3`: `0`.

Hoà `s1` và `s2` ⇒ thứ tự tài liệu ⇒ `["s1", "s2"]` với `k = 2`.

Truy vấn `"không có từ này"` ⇒ mọi điểm `0` ⇒ `[]` ⇒ dự phòng ⇒ `["s1", "s2"]` + `warnings = ["fallback_used"]`.

## 5. Lắp ngữ cảnh

```text
BUDGET = 40_000
MARKER = "\n...(truncated)..."

context = ""
used = []
truncated = False
với mỗi id trong valid, theo thứ tự:
    block = "## " + title + "\n\n" + text + "\n\n"
    nếu len(context) + len(block) <= BUDGET:
        context += block; used.append(id)
    ngược lại:
        còn = BUDGET - len(context)
        nếu còn > 0:
            context += block[:còn]; used.append(id)
        truncated = True
        break
nếu truncated: context += MARKER
```

- `refs = used` — **đúng** các mục đã dùng, kể cả mục bị cắt một phần.
- `len(context) <= BUDGET + len(MARKER)`; `len(MARKER) = 18`.
- Nếu `valid` rỗng (không thể xảy ra sau dự phòng, trừ khi tài liệu rỗng — đã lỗi) thì `context = ""`.

Tiêu đề được lặp lại trong ngữ cảnh để người đọc biết nguồn.

## 6. Đầu ra

```json
{
  "context": "## Giới thiệu\n\nhệ thống gồm ba phần\n\n## Cài đặt\n\ncài đặt hệ thống bằng lệnh\n\n",
  "dropped_ids": [],
  "refs": ["s1", "s2"],
  "truncated": false,
  "warnings": []
}
```

- `dropped_ids` là id bị loại vì không tồn tại (giữ thứ tự xuất hiện).
- `warnings` theo thứ tự phát sinh.
- `refs` là danh sách id đã dùng, cùng thứ tự trong ngữ cảnh.

## 7. Ví dụ cắt

`fixtures/doc_long.json`: `s1.title = "A"`, `s1.text` dài 20 000 ký tự `"a"`; `s2.title = "B"`, `s2.text` dài 20 000 ký tự `"a"`.

- `block(s1) = "## A\n\n" + 20 000 ký tự + "\n\n"` → độ dài `6 + 20 000 + 2 = 20 008`.
- `block(s2)` cùng độ dài (tiêu đề `B` một ký tự).
- Sau `s1`: `20 008`. Thêm `s2` sẽ thành `40 016 > 40 000` ⇒ còn `40 000 - 20 008 = 19 992` ký tự của `block(s2)`.
- `block(s2)[:19992]` gồm header `"## B\n\n"` (6 ký tự) + `19 986` ký tự `"a"`.
- Tổng nội dung: `20 008 + 19 992 = 40 000`; cộng `MARKER` (18) ⇒ `40 018`.
- `refs = ["s1", "s2"]`, `truncated = true`.

## 8. Tiêu chí chấp nhận

1. Ví dụ 4.3 cho `["s1","s2"]`; `idf` và `score` khớp `1e-7`.
2. Truy vấn không khớp ⇒ `["s1","s2"]` + `warnings == ["fallback_used"]`.
3. Selector giả trả `["zzz","s2","s2","s3"]` với `k=3` ⇒ `dropped_ids = ["zzz"]`, `warnings` chứa `unknown_id:zzz` và `duplicate_id:s2`, `valid` cuối là `["s2","s3"]`.
4. Ví dụ 7: `len(context) == 40 018`, kết thúc bằng marker, `refs == ["s1","s2"]`.
5. `refs` luôn bằng tập id có block (kể cả phần) trong `context`; test so bằng cách tìm `"## " + title` trong context.
6. `context` không bao giờ vượt `40 018` ký tự.
7. Tài liệu 1 mục + selector rỗng ⇒ dự phòng `[s1]` (một phần tử), không lỗi.
8. Tài liệu rỗng ⇒ `EmptyDocument`, không có output.
9. `k = 0` ⇒ `InvalidK`.
10. Cùng fixture ⇒ cùng output byte-identical.

## 9. Non-goals

- Không embedding, không vector store, không mô hình.
- Không sinh câu trả lời; không đánh giá câu trả lời.
- Không tách PDF/HTML; đầu vào là JSON đã có mục.
- Không mục lồng nhau.
