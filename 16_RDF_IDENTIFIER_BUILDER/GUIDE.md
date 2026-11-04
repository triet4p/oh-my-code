# GUIDE — RDF identifier builder

## Bước 0 — Môi trường

```bash
mkdir 16_RDF_IDENTIFIER_BUILDER/work && cd 16_RDF_IDENTIFIER_BUILDER/work
uv init . -p 3.12 --lib
uv add --dev pytest
mkdir -p src/paperkg tests
```

`rdflib` chỉ là dev-dependency tùy chọn để parse query; không bắt buộc.

## Bước 1 — Cài `slugify` đúng nguồn

```text
def slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", name)
    words = cleaned.split()
    if not words:
        raise ValueError(f"cannot slugify empty name: {name!r}")
    result = words[0].lower() + "".join(w.capitalize() for w in words[1:])
    ...
    return result
```

Đừng “cải tiến” bằng `casefold`, `unicodedata`, hay thay `-` bằng `_`: bạn sẽ không còn khớp nguồn và test sẽ khác. Nếu muốn transliterate, đó là bài mở rộng riêng.

Kiểm tra `w.capitalize()`: Python hạ toàn bộ chữ còn lại. Vì vậy `LeCun` → `Lecun`. Đây là hành vi gây bất ngờ nhất; hãy viết test riêng.

## Bước 2 — Escape

```text
def escape_literal(text: str) -> str:
    return (text.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t"))
```

Thứ tự bắt buộc: backslash trước. Nếu thay quote trước, backslash của `\"` sẽ bị nhân đôi thành `\\"`.

Kiểm tra bằng cách in `repr(escape_literal('a"b\\c'))`.

## Bước 3 — Validate trước khi build

Viết `__post_init__` cho `PaperInput`:

- `isinstance(x, int) and not isinstance(x, bool)`.
- Trim string và kiểm tra độ dài.
- Chuyển list/tuple thành tuple.
- Kiểm tra enum.
- Từ chối ký tự điều khiển trong title (`ord < 32` trừ? từ chối hết; tab cũng từ chối).
- `evaluates_on` không trùng sau slug: có thể kiểm tra sau khi slug.

Nếu dùng `StrEnum`, người dùng có thể truyền `VenueType.PREPRINT`; string thô `"Preprint"` phải bị từ chối để tránh chèn class.

## Bước 4 — Registry va chạm

Viết helper:

```text
class IriRegistry:
    def __init__(self, known: Mapping[str, str] = {}):
        self._seen = {k: v for k, v in known.items()}
    def add(self, local: str, label: str) -> None:
        previous = self._seen.get(local)
        if previous is None:
            self._seen[local] = label
            return
        if previous != label:
            raise IriCollisionError(local, previous, label)
```

Dùng nhãn đã trim, phân biệt hoa thường. `known_iris` phải được copy, không sửa input.

Khi nào gọi `add`?

- First author, từng co-author.
- Venue.
- Concept, method, proposed benchmark, từng eval benchmark.
- Paper title.
- **Trước** khi tạo dòng triple, để lỗi xảy ra trước khi trả chuỗi nửa vời.

Nếu cùng local + cùng label, `add` không làm gì; nhưng bạn vẫn phải tránh in triple lặp. Dùng một `set` các IRI đã in cho từng loại, hoặc kiểm tra khi lặp.

## Bước 5 — Xây query

Viết theo từng khối, dùng list dòng và `"\n".join`:

1. Prefix.
2. `INSERT DATA {`.
3. Author: first, rồi co-authors (bỏ trùng đúng nhãn).
4. Venue.
5. Concept nếu có.
6. Method nếu có.
7. Proposed benchmark nếu có.
8. Eval benchmarks (bỏ trùng).
9. Paper block.

Khối paper: tạo list predicate, mỗi predicate là `(name, object_literal)`; nối bằng `" ;\n    "`, predicate cuối thêm `" ."`.

Gợi ý:

```text
lines.append(f'  :{paper_iri} a :Paper ;')
lines.append(f'    :title "{escape_literal(paper.title)}" ;')
lines.append(f'    :year "{paper.year}"^^xsd:gYear ;')
lines.append(f'    :hasFirstAuthor :{first} ;')
if co: lines.append(f'    :hasCoAuthor {", ".join(":"+x for x in co)} ;')
...
lines[-1] = lines[-1].removesuffix(" ;") + " ."
```

`removesuffix` an toàn hơn `rstrip(" ;")` vì không ăn dấu cách/`;` của nội dung (dù nội dung đã escape).

Kiểm tra không có predicate rỗng: `:hasCoAuthor` với chuỗi rỗng sẽ tạo cú pháp sai.

## Bước 6 — Thứ tự và tính tất định

- Không lặp trên `set` để in; dùng list đã chuẩn hóa.
- `co_authors` giữ thứ tự; nếu bạn muốn sắp, phải ghi rõ và test.
- `known_iris` không ảnh hưởng thứ tự output, chỉ ảnh hưởng lỗi.
- Cùng input → cùng chuỗi byte-for-byte.

## Bước 7 — Test

1. **Slug**: bảng SPEC, gồm `"Yann LeCun"`, `"LongMemEval"`, `"GPT-4"`, `"  "`, `"Émile Zola"`.
2. **Escape**: từng ký tự và kết hợp; kiểm tra backslash trước.
3. **Validate**: year bool/float, venue string, title rỗng, quá dài, ký tự điều khiển.
4. **Query**: so khớp toàn chuỗi với ví dụ; dùng triple-quoted string và `textwrap.dedent` cẩn thận.
5. **Va chạm**: trong paper, với known, cùng nhãn.
6. **Tùy chọn**: parse bằng `rdflib.plugins.sparql.prepareQuery` hoặc `Graph.update(query)` trên graph rỗng (không cần Fuseki).
7. **Idempotent**: chạy query hai lần trên cùng graph (nếu dùng rdflib) → số triple không đổi.

Một cái bẫy snapshot: khoảng trắng cuối dòng. Dùng editor hiển thị whitespace hoặc so `repr`.

## Bước 8 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from paperkg import PaperInput, VenueType, build_insert_query
p = PaperInput("Example New Memory Paper", 2026, "Jane Doe",
               ("John Smith",), "graph attention retrieval",
               None, ("LongMemEval",), "agentic memory",
               "arXiv preprint", VenueType.PREPRINT)
print(build_insert_query(p))
PY
```

So với khối trong SPEC.

Nếu có rdflib:

```bash
uv run --with rdflib python - <<'PY'
from rdflib import Graph
from paperkg import ...
q = build_insert_query(p)
g = Graph(); g.update(q); g.update(q)
print(len(g))
PY
```

Số triple ổn định sau hai lần update.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `yannLecun` thành `yannLeCun` | Bạn tự viết capitalize giữ chữ hoa. |
| Quote bị escape sai | Thay quote trước backslash. |
| Xuống dòng thật trong literal | Không escape `\n`. |
| `:hasCoAuthor ;` | Danh sách rỗng nhưng vẫn in predicate. |
| Query lỗi cú pháp ở predicate cuối | Còn `;` trước `}`. |
| Va chạm không báo | Registry chỉ kiểm tra author, bỏ qua benchmark. |
| Triple lặp | Không dedupe khi cùng nhãn. |
| Venue tùy ý lọt | Nhận string thay vì enum. |
| Thứ tự output đổi | Lặp trên set. |
| Non-ASCII mất âm thầm | Đúng hành vi nguồn; phải ghi cảnh báo. |

## Bước 10 — Mở rộng

- Thêm `slugify_unicode` dùng transliteration, giữ API cũ.
- Thêm kiểm tra SHACL.
- Thêm chế độ sinh Turtle thay vì SPARQL.
- Thêm `dry_run` in diff với graph hiện có.
- Thêm registry bền vững đọc từ file.

## Tự đánh giá

1. Vì sao `Yann LeCun` thành `yannLecun`, không phải `yannLeCun`?
2. Vì sao phải kiểm tra va chạm dù RDF là set-based?
3. Vì sao `venue_type` phải là enum?
4. Vì sao escape backslash trước quote?
