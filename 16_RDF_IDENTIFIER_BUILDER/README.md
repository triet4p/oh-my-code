# 16 — RDF identifier builder: slug IRI, escape literal, chống trùng

## Mục tiêu

Tự viết lớp xây lệnh `INSERT DATA` cho knowledge graph: biến tên người/khái niệm thành IRI local name theo quy tắc xác định, escape chuỗi an toàn, từ chối loại venue lạ, và phát hiện hai nhãn khác nhau cùng sinh một IRI. Bài tập rèn cách giữ tính idempotent của RDF mà không tạo dữ liệu sai hoặc lỗi cú pháp.

## Giá trị học được

- IRI local name là một không gian tên; slug hóa là ánh xạ nhiều-một, nên **va chạm** là chuyện bình thường, không phải ngoại lệ hiếm.
- RDF là tập hợp: chèn lại cùng triple không tạo trùng, nhưng hai thực thể khác nhau cùng IRI thì gộp sai.
- SPARQL literal cần escape; nếu không, dấu `"` hoặc xuống dòng làm hỏng toàn bộ lệnh.
- Không cho người dùng chèn class tùy ý (`venue_type`) — đó là bề mặt chèn cú pháp.
- Ngày tháng có kiểu (`xsd:gYear`), không phải chuỗi trần.
- Canonical output giúp test snapshot và so sánh diff.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Trung bình – Khó**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- Không cần Fuseki, không cần mạng. `rdflib` là tùy chọn để kiểm tra cú pháp.

## Nguồn gốc

- Nguồn: `triet4p/paper-kg-ontology`, file `scripts/add_paper.py`.
- URL chính xác: <https://github.com/triet4p/paper-kg-ontology/blob/main/scripts/add_paper.py>

Hành vi quan sát được trong nguồn:

- `PREFIX = "http://example.triet4p.org/paper-kg#"`, `UPDATE_ENDPOINT` trỏ Fuseki.
- `slugify(name)` xóa mọi ký tự không thuộc `[a-zA-Z0-9 ]`, `split()`, nếu rỗng ném `ValueError`; trả `words[0].lower() + "".join(w.capitalize() for w in words[1:])`.
- `escape_literal(text)` thay `\` bằng `\\` rồi `"` bằng `\"` — chỉ hai ký tự.
- `PaperInput` dataclass: `title`, `year`, `first_author`, `co_authors`, `method_name`, `proposes_benchmark`, `evaluates_on`, `concept`, `venue_name`, `venue_type`.
- `build_insert_query` tạo prefix `:`, `INSERT DATA`, triple `a :Author` cho tác giả, `a :{venue_type}` cho venue, concept/method/benchmark, rồi paper với `:title` (escaped), `:year "..."^^xsd:gYear`, `:hasFirstAuthor`, `:hasCoAuthor`, `:publishedIn`, các predicate tùy chọn; dòng cuối bỏ ` ;` và thêm `.`.
- Nguồn không validate `venue_type`, không kiểm tra va chạm slug, không escape newline/tab, và đặt prefix `xsd` trước prefix `:` trong chuỗi trả về.

## Phạm vi bài tập

Xây package `paperkg`:

- `slugify(name)` tương thích nguồn, có tài liệu về giới hạn ASCII.
- `escape_literal(text)` đầy đủ.
- `PaperInput` có validate.
- `IriRegistry` phát hiện va chạm.
- `build_insert_query(paper, *, known_iris=None)` canonical.
- CLI đọc JSON, ghi `.rq`.

Không nằm trong phạm vi: gửi HTTP tới Fuseki, validate SHACL, suy luận OWL, đọc Turtle có sẵn.

## Liên kết

- [SPEC.md](SPEC.md) — quy tắc slug/escape, validate, query mẫu.
- [GUIDE.md](GUIDE.md) — thiết kế registry, test, bẫy.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập giữ quy tắc `slugify` và bố cục triple của nguồn, nhưng **thắt chặt**: enum venue, escape đầy đủ, phát hiện va chạm, kiểm tra năm/độ dài, thứ tự prefix canonical. Không tuyên bố nguồn có các kiểm tra đó.
