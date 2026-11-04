# SPEC — RDF identifier builder

## Mục tiêu hành vi

Từ một `PaperInput` hợp lệ, sinh một lệnh SPARQL `INSERT DATA` xác định, an toàn cú pháp, idempotent theo IRI, và từ chối dữ liệu có thể gây va chạm định danh hoặc chèn cú pháp.

## API

```python
PREFIX = "http://example.triet4p.org/paper-kg#"

class VenueType(StrEnum):
    PREPRINT = "Preprint"
    CONFERENCE = "Conference"
    JOURNAL = "Journal"

class IriCollisionError(ValueError): ...
class ValidationError(ValueError): ...

@dataclass(frozen=True, slots=True)
class PaperInput:
    title: str
    year: int
    first_author: str
    co_authors: tuple[str, ...] = ()
    method_name: str | None = None
    proposes_benchmark: str | None = None
    evaluates_on: tuple[str, ...] = ()
    concept: str | None = None
    venue_name: str = "arXiv preprint"
    venue_type: VenueType = VenueType.PREPRINT

def slugify(name: str) -> str: ...
def escape_literal(text: str) -> str: ...
def build_insert_query(
    paper: PaperInput,
    *,
    known_iris: Mapping[str, str] | None = None,
) -> str: ...
```

`known_iris` ánh xạ `local_name -> nhãn gốc đã biết`; dùng để phát hiện va chạm với dữ liệu đã có.

## `slugify`

Thuật toán bắt buộc (tương thích nguồn):

1. `name` phải là `str`; nếu không → `TypeError`.
2. Xóa mọi ký tự **không** thuộc `[a-zA-Z0-9 ]` (ASCII; dấu tiếng Việt và Unicode bị bỏ).
3. `split()` theo khoảng trắng (gộp nhiều khoảng trắng, bỏ đầu/cuối).
4. Nếu danh sách rỗng → `ValueError`.
5. Kết quả: `words[0].lower()` + nối `w.capitalize()` của các từ sau.
6. Kiểm tra kết quả khớp `^[a-z][A-Za-z0-9]*$`; nếu không → `ValueError` (thực tế chỉ có thể xảy ra với đầu vào lạ).

Hệ quả cần nhớ:

- `str.capitalize()` **hạ** các chữ còn lại: `"LeCun"` → `"Lecun"`, nên `"Yann LeCun"` → `yannLecun`.
- Từ đơn CamelCase bị hạ toàn bộ: `"LongMemEval"` → `longmemeval`; `"GPT4"` → `gpt4`.
- Dấu gạch nối bị xóa, không thay bằng gạch dưới: `"GPT-4"` → `gpt4`.
- `"Émile Zola"` → `mileZola`; mất thông tin `É`. Ghi cảnh báo trong README của bài làm; không tự transliterate.
- Chuỗi chỉ có ký tự bị xóa → `ValueError`.

## `escape_literal`

Trả chuỗi an toàn để đặt giữa hai dấu `"` trong SPARQL. Thứ tự thay thế:

1. `\` → `\\`
2. `"` → `\"`
3. `\n` → `\n` (hai ký tự: backslash + n)
4. `\r` → `\r`
5. `\t` → `\t`

Không escape `'` (literal dùng nháy kép). Không escape `{`, `}`, `<`, `>` vì chúng nằm trong literal.

Ví dụ:

| Đầu vào | Đầu ra |
|---|---|
| `He said "hi"` | `He said \"hi\"` |
| `a\b` | `a\\b` |
| `line1\nline2` | `line1\nline2` (literal backslash-n, không xuống dòng) |
| `tab\there` | `tab\there` |

## Validate `PaperInput`

| Trường | Quy tắc |
|---|---|
| `title` | string, trim 1..300, không chứa ký tự điều khiển (trừ tab? từ chối hết) |
| `year` | `int` (không bool), `1900 <= year <= 2100` |
| `first_author` | string, trim không rỗng, ≤120 |
| `co_authors` | tuple/list string, mỗi phần tử không rỗng, ≤20 phần tử |
| `method_name` | `None` hoặc string không rỗng ≤120 |
| `proposes_benchmark` | như trên |
| `evaluates_on` | tuple/list string không rỗng, ≤20, không trùng sau slug |
| `concept` | như `method_name` |
| `venue_name` | string không rỗng ≤120 |
| `venue_type` | `VenueType` (không nhận string thô) |

Chuẩn hóa khi tạo: trim các nhãn, chuyển list sang tuple. Không tự slug hóa trong `PaperInput`; slug chỉ sinh khi build.

## Va chạm IRI

`build_insert_query` xây một ánh xạ `local_name -> original_label` cho **mọi** thực thể trong lệnh:

- paper (title)
- first_author
- từng co_author
- venue_name
- concept, method, benchmark, từng `evaluates_on`

Quy tắc:

1. Nếu cùng `local_name` xuất hiện với **cùng** nhãn (sau trim, phân biệt hoa thường): bỏ qua bản trùng (RDF set-based, không cần lặp triple).
2. Nếu cùng `local_name` nhưng nhãn khác: `IriCollisionError` nêu local_name và hai nhãn.
3. Nếu `known_iris` có local_name với nhãn khác nhãn hiện tại: `IriCollisionError`; cùng nhãn: chấp nhận.
4. Kiểm tra này áp dụng cho mọi loại, kể cả author và benchmark (không phân biệt "namespace theo loại" vì tất cả dùng chung prefix `:`).

Hệ quả: `"Jane Doe"` làm first_author và `"Jane doe"` làm co_author → cùng `janeDoe` nhưng nhãn khác → lỗi. Nếu cả hai đúng `"Jane Doe"` → một triple author.

## Query canonical

Thứ tự prefix:

```text
PREFIX : <http://example.triet4p.org/paper-kg#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
```

Thân:

```text
INSERT DATA {
  :{first_author} a :Author .
  :{co_author_1} a :Author .
  ...
  :{venue} a :{VenueType} .
  [:{concept} a :Concept .]
  [:{method} a :Method .]
  [:{proposed_bench} a :Benchmark .]
  [:{eval_bench} a :Benchmark .]
  :{paper} a :Paper ;
    :title "{escaped_title}" ;
    :year "{year}"^^xsd:gYear ;
    :hasFirstAuthor :{first_author} ;
    [:hasCoAuthor :{co1}, :{co2} ;]
    :publishedIn :{venue} ;
    [:proposesMethod :{method} ;]
    [:proposesBenchmark :{proposed_bench} ;]
    [:evaluatesOn :{b1}, :{b2} ;]
    [:relatesToConcept :{concept} ;]
```

- Mỗi triple độc lập kết thúc ` .` và thụt hai dấu cách.
- Khối paper thụt hai dấu cách; predicate con thụt bốn.
- Predicate cuối của paper kết thúc bằng ` .` (một dấu cách rồi chấm), không có ` ;`.
- `:hasCoAuthor` gộp nhiều IRI trên một dòng, phân tách `, `.
- `:evaluatesOn` tương tự; nếu `evaluates_on` rỗng, bỏ predicate.
- Không có dòng trống thừa; kết thúc bằng `}\n`.
- `VenueType` in đúng chuỗi `Preprint`/`Conference`/`Journal`.
- Thứ tự triple không phụ thuộc thứ tự dict hay set; làm theo danh sách đã chuẩn hóa.
- `evaluates_on` giữ thứ tự người dùng; co_authors giữ thứ tự.

## Ví dụ

Input:

```python
PaperInput(
    title="Example New Memory Paper",
    year=2026,
    first_author="Jane Doe",
    co_authors=("John Smith",),
    method_name="graph attention retrieval",
    evaluates_on=("LongMemEval",),
    concept="agentic memory",
    venue_name="arXiv preprint",
    venue_type=VenueType.PREPRINT,
)
```

Output chính xác:

```text
PREFIX : <http://example.triet4p.org/paper-kg#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT DATA {
  :janeDoe a :Author .
  :johnSmith a :Author .
  :arxivPreprint a :Preprint .
  :agenticMemory a :Concept .
  :graphAttentionRetrieval a :Method .
  :longmemeval a :Benchmark .
  :exampleNewMemoryPaper a :Paper ;
    :title "Example New Memory Paper" ;
    :year "2026"^^xsd:gYear ;
    :hasFirstAuthor :janeDoe ;
    :hasCoAuthor :johnSmith ;
    :publishedIn :arxivPreprint ;
    :proposesMethod :graphAttentionRetrieval ;
    :evaluatesOn :longmemeval ;
    :relatesToConcept :agenticMemory .
}
```

Lưu ý `longmemeval` (không phải `longMemEval`) vì từ đơn bị `lower()`.

Va chạm:

```python
build_insert_query(paper, known_iris={"janeDoe": "Jane Doe"})  # OK
build_insert_query(paper, known_iris={"janeDoe": "J. Doe"})    # IriCollisionError
```

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Tên rỗng/toàn ký tự bị xóa | `ValueError` |
| `"  Yann   LeCun  "` | `yannLecun` (khoảng trắng gộp) |
| `"GPT-4"` | `gpt4` |
| `"A/B"` | `ab` (xóa `/` còn `AB`, một từ, `lower()` toàn bộ) |
| Title chứa `"` | escape `\"` |
| Title chứa newline | escape `\n` |
| `year=2026.0` | `TypeError` (không phải int) |
| `year=True` | `TypeError`/`ValueError` |
| `venue_type="Preprint"` | `TypeError` |
| Trùng author đúng nhãn | một triple |
| Trùng local name khác nhãn | `IriCollisionError` |
| `evaluates_on` trùng | khử trùng theo local name nếu cùng nhãn |
| Không co-author | bỏ `:hasCoAuthor` |
| Không method/bench/concept | bỏ predicate tương ứng |
| Title chứa `{` `}` | giữ trong literal, không ảnh hưởng cú pháp |
| Non-ASCII trong tên | bị xóa; nếu còn rỗng → lỗi |

## CLI

```text
paperkg --input paper.json --out insert.rq
```

JSON cùng khóa với `PaperInput`; `venue_type` là chuỗi enum. Lỗi validate → exit 2; va chạm → exit 3; thành công → in đường dẫn, exit 0. Không kết nối Fuseki.

## Tiêu chí nghiệm thu

1. `slugify` khớp bảng ví dụ, đặc biệt `Yann LeCun` và `LongMemEval`.
2. `escape_literal` khớp bảng, kiểm tra thứ tự backslash trước quote.
3. Query ví dụ khớp **từng ký tự** (so sánh chuỗi).
4. Va chạm trong paper và với `known_iris` đều báo.
5. Trùng đúng nhãn không tạo triple lặp.
6. `venue_type` string thô bị từ chối.
7. Title có quote/newline vẫn tạo literal hợp lệ; nếu cài `rdflib`, parse query thành công.
8. Không có chỗ nào nối trực tiếp nhãn người dùng vào IRI mà không qua `slugify`.
9. `pytest -q` xanh.

## Non-goals

- Gửi UPDATE tới Fuseki.
- Sinh Turtle đầy đủ, blank node, named graph.
- Suy luận OWL/SHACL.
- Transliterate Unicode sang ASCII.
- Entity resolution thật (rdfs:label, owl:sameAs).
