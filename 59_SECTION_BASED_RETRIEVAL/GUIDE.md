# GUIDE 59 — Truy hồi theo mục lục thay vì vector

## 1. Vì sao "theo mục" lại đáng làm

Vector search trả về đoạn văn rời rạc; người đọc mất ngữ cảnh. Chọn theo mục:

- giữ được cấu trúc tài liệu (tiêu đề, thứ tự);
- giải thích được ("vì sao mục này") bằng từ khoá;
- rẻ và không cần embedding.

Cái giá: nếu mục quá lớn, bạn phải cắt — và cắt là chỗ dễ sai nhất trong bài này.

## 2. Cấu trúc

```text
src/
├── doc.py       # Section, Document, load
├── selectors.py # LexicalSelector, ValidatingSelector, Protocol
├── context.py   # assemble(valid_ids, doc, budget) -> (context, used, truncated)
└── __main__.py
```

## 3. Thứ tự cài đặt

### Bước 1 — Tài liệu và kiểm tra

`load(path)` đọc JSON, kiểm tra id duy nhất + regex, giữ thứ tự. Trả `Document` với `content_map: dict[id, Section]` **và** `order: list[id]` — hai thứ này phải cùng nguồn, nếu không thứ tự dự phòng sẽ lệch.

### Bước 2 — Token hoá

```python
def tokenize(text):
    return [t for t in re.split(r"[^\w]+", text.lower(), flags=re.UNICODE) if t]
```

`\w` trong Python bao gồm chữ có dấu tiếng Việt (khi chuỗi là `str` Unicode). Kiểm tra bằng `tokenize("hệ thống")` ⇒ `["hệ","thống"]`.

Nếu bạn dùng `[a-z0-9]+`, tiếng Việt sẽ vỡ — đây là lỗi rất dễ mắc.

### Bước 3 — IDF và điểm

Tính `df` bằng cách duyệt mọi mục một lần, dùng `set` token của mỗi mục. Cẩn thận: `tf` cần **đếm**, `df` cần **có/không**.

`idf = math.log(1 + N/(1+df))`. Với `N=3, df=2` → `ln 2`. Nếu bạn dùng `log10` hoặc thiếu `1 +`, điểm sẽ khác SPEC.

Sắp `(-score, order_index)`; chỉ giữ `score > 0`.

### Bước 4 — Kiểm tra id

`ValidatingSelector` nhận selector bất kỳ. Đừng để selector tự kiểm tra: mục đích là một lớp duy nhất chịu trách nhiệm, để mọi selector (kể cả mô hình) được bảo vệ như nhau.

Dừng khi đủ `k` id hợp lệ — điều này có nghĩa id rác phía sau không sinh cảnh báo. SPEC chấp nhận; hãy ghi rõ.

### Bước 5 — Lắp ngữ cảnh

Bám đúng vòng lặp SPEC 5. Điểm cần chú ý:

- `block` dùng `title` **và** `text`; header luôn là `"## " + title + "\n\n"`.
- Ngân sách áp cho **nội dung**, marker cộng thêm.
- `used.append(id)` chỉ khi `còn > 0`; nếu `còn == 0`, mục đó không vào `refs`.

Kiểm tra: `len(context) <= 40018` với mọi đầu vào.

## 4. Cạm bẫy

- **`refs` tính từ `valid` thay vì `used`**: khi cắt, hai danh sách khác nhau. Test 8.5 bắt.
- **Cắt sau khi đã cộng marker**: vượt ngân sách.
- **Cắt giữa ký tự UTF-16 của emoji**: Python cắt theo codepoint nên an toàn với `str`; nhưng nếu bạn encode sang bytes rồi cắt, emoji vỡ. Luôn cắt trên `str`.
- **`re.split` với `[^a-z]`**: mất tiếng Việt.
- **Dự phòng trả `valid` cũ**: nếu selector trả rỗng nhưng bạn quên reset, kết quả cũ rò sang.
- **Không thêm `fallback_used`**: người vận hành không biết ngữ cảnh là đoán.
- **Sắp lại `valid` theo điểm sau khi kiểm tra**: mất thứ tự mô hình/selector chọn — có thể là hành vi mong muốn, nhưng phải ghi rõ.
- **`k` lớn hơn số mục**: trả ít hơn `k`, không lỗi.
- **Tài liệu 1 mục**: dự phòng trả 1 phần tử, không được giả định luôn có 2.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `tokenize_vi` | `"hệ thống"` ⇒ 2 token |
| `idf` | `ln 2` với N=3, df=2 |
| `lexical_example` | 4.3 ⇒ `["s1","s2"]` |
| `fallback` | query rỗng ⇒ `["s1","s2"]` + warning |
| `invalid_ids` | `dropped_ids`, `warnings`, `valid` cuối |
| `truncate` | mục 7: `40 018`, marker, `refs` |
| `refs_used` | mỗi id trong `refs` có `"## "+title` trong context |
| `empty_doc` | `EmptyDocument` |
| `k_zero` | `InvalidK` |
| `determinism` | hai lần byte-identical |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src ask --fixture fixtures/doc_small.json --query "hệ thống" --k 2
python -m src ask --fixture fixtures/doc_long.json --query "a" --k 2 | python -c "import json,sys; d=json.load(sys.stdin); print(len(d['context']), d['truncated'], d['refs'])"
```

Lệnh thứ ba phải cho `refs = ["s1","s2"]`. Lệnh thứ tư in `40018 True ['s1', 's2']`.

Kiểm tra `refs` khớp ngữ cảnh bằng một script nhỏ: với mỗi id trong `refs`, tìm `"## " + doc.title[id]` trong `context` và khẳng định có.

## 7. Gợi ý

- Viết `assemble` như hàm thuần nhận `valid_ids` (không nhận selector) — test cắt độc lập với chấm điểm.
- Viết `idf_table(sections, query_terms)` trả dict để in ra khi debug.
- Với truncation, test bằng `len` trước, rồi mới so nội dung; nếu `len` sai, đừng đọc diff.
- Dùng `str.find` để kiểm tra header thay vì so cả chuỗi lớn.

## 8. Mở rộng

- **Chọn theo mô hình**: cắm một selector gọi mô hình cục bộ; so với lexical trên 20 truy vấn, ghi lại trường hợp mô hình chọn id không tồn tại.
- **Ngân sách theo token**: thay ký tự bằng ước lượng token (chia 4) và so hành vi cắt.
- **Mục lồng nhau**: biểu diễn cây; chọn mục lá nhưng lắp ngữ cảnh kèm tiêu đề cha.
- **Đa ngôn ngữ**: token hoá theo `\w` giữ được tiếng Việt; thêm chuẩn hoá NFC để tránh hai dạng Unicode của cùng một từ.
- **Đánh giá**: tạo 20 cặp (query, mục đúng) và đo recall@k của lexical; đó là baseline bạn có thể vượt bằng mô hình.
