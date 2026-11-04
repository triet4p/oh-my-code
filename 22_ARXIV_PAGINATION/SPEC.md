# SPEC 22 — Client phân trang ArXiv offline

## 1. Giao diện CLI

```bash
python -m arxiv_pager \
  --fixtures fixtures \
  --query "agent memory" \
  --categories cs.AI,cs.CL \
  --max-results 250 \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --out result.json
```

| Tham số | Bắt buộc | Mặc định | Ràng buộc |
|---|---|---|---|
| `--fixtures` | không | `fixtures` | thư mục tồn tại |
| `--query` | không | `""` | ≤ 500 ký tự, không ký tự điều khiển |
| `--categories` | không | rỗng | mỗi mã khớp `^[a-z-]+(\.[A-Za-z0-9-]+)?$` |
| `--max-results` | không | `20` | 1…5000 |
| `--start-date` | không | rỗng | `YYYY-MM-DD`, ngày thật |
| `--end-date` | không | rỗng | `YYYY-MM-DD`, ngày thật, ≥ start |
| `--out` | không | stdout | đường dẫn ghi JSON |

Nếu chỉ có một trong hai ngày → lỗi `INVALID_DATE_RANGE`, exit 2. Nếu `--out` không ghi được → exit 3.

## 2. Dựng `search_query`

Thuật toán bắt buộc:

1. `q = query.strip()`; thay mọi `+` bằng dấu cách; gộp khoảng trắng liên tiếp.
2. Nếu `q` khác rỗng:
   - nếu `q` chứa `cat:` hoặc `all:` → dùng nguyên văn `q` làm một phần;
   - ngược lại → `all:<q>`.
3. Nếu `categories` không rỗng → thêm `(` + các `cat:<c>` nối bằng ` OR ` + `)`.
4. Nếu chưa có phần nào → `cat:cs.AI`.
5. Nối các phần bằng ` AND `.
6. Nếu có đủ hai ngày:

   ```
   s = YYYYMMDD + "0000"
   e = YYYYMMDD + "2359"
   query += f" AND submittedDate:[{s} TO {e}]"
   ```

7. Không thêm khoảng trắng thừa ở đầu/cuối.

Ví dụ:

| Input | Output |
|---|---|
| `query="agent memory"`, cats `["cs.AI","cs.CL"]`, 2026-01-01…2026-01-31 | `all:agent memory AND (cat:cs.AI OR cat:cs.CL) AND submittedDate:[202601010000 TO 202601312359]` |
| `query=""`, cats `[]` | `cat:cs.AI` |
| `query="all:retrieval"`, cats `[]` | `all:retrieval` |
| `query="ti:graph+neural"`, cats `["cs.LG"]` | `ti:graph neural AND (cat:cs.LG)` |

`query` chứa `[`, `]`, `(`, `)` khi chưa có tiền tố `all:`/`cat:` → lỗi `INVALID_QUERY`: bài không cố mô phỏng cú pháp ArXiv đầy đủ.

## 3. Transport offline

Interface logic:

```
fetch_page(offset: int, max_results: int) -> PageResult
PageResult: status: int, body: bytes
```

Transport chuẩn:

1. Đọc `fixtures/pages/{offset:06d}.xml`.
2. Nếu file không tồn tại → status 404, body rỗng.
3. Nếu tồn tại → đọc toàn bộ XML, cắt còn tối đa `max_results` phần tử `<entry>` **theo thứ tự tài liệu** rồi serialize lại thành body.
4. Ghi lại `(offset, max_results)` vào danh sách `calls` để test.

Không dùng `datetime.now`, không random, không sleep.

## 4. Phân trang

```
offset = 0
received_total = 0
pages = 0
max_pages = 100
while received_total < max_results and pages < max_pages:
    want = min(100, max_results - received_total)
    page = fetch_page(offset, want)
    if page.status != 200:
        error = { code: "PAGE_HTTP", status: page.status, offset }
        break
    parsed = parse_page(page.body)
    if parsed.fatal:
        error = { code: "PAGE_XML", offset, message }
        break
    if len(parsed.papers) == 0:
        break
    for p in parsed.papers:
        if received_total == max_results: break
        received_total += 1
        accept(p)
    offset += len(parsed.papers)
    pages += 1
```

Quy tắc:

- Nếu trang trả về ít hơn `want` nhưng > 0, vẫn tăng offset theo số thực nhận; lần sau có thể nhận nốt.
- Nếu `len(parsed.papers) > want` (transport lỗi), chỉ lấy `want` mục đầu và đặt `warning=TRANSPORT_OVERSIZED`.
- Không gọi lại cùng offset.
- Chạm `max_pages` khi vẫn còn thiếu → `error.code = "PAGE_LIMIT"`, giữ kết quả đã có.
- `max_results` đạt được → dừng, không gọi thêm.

## 5. Parse Atom

Không gian tên:

- Atom: `http://www.w3.org/2005/Atom`
- ArXiv: `http://arxiv.org/schemas/atom`

Với mỗi `<entry>`:

| Trường | Nguồn | Bắt buộc | Chuẩn hóa |
|---|---|---|---|
| `id_url` | `atom:id` | có | text |
| `paper_id` | id_url | có | lấy sau `/abs/`, bỏ hậu tố `v\d+$` |
| `title` | `atom:title` | có | thay newline bằng khoảng trắng, gộp space, trim |
| `summary` | `atom:summary` | có | như title |
| `authors` | `atom:author/atom:name` | có ít nhất 1 | giữ thứ tự, trim |
| `published` | `atom:published` | có | ISO-8601; `Z` → `+00:00` |
| `pdf_link` | `atom:link[@title="pdf"]/@href` | không | thiếu → `id_url` thay `/abs/` bằng `/pdf/` + `.pdf` |
| `primary_category` | `arxiv:primary_category/@term` | không | thiếu → `cs.AI` |

Bản ghi thiếu trường bắt buộc, ngày sai, hoặc `paper_id` rỗng → bỏ qua, tăng `skipped_entries`, thêm cảnh báo `ENTRY_INVALID` có `id` nếu có. Không làm hỏng cả trang.

`parse_page` trả `fatal=True` khi `ET.fromstring` ném `ParseError`; root không phải `feed` cũng là fatal.

## 6. Khử trùng và trạng thái đã lưu

- Tập `saved_ids` đọc từ `fixtures/saved.json` (mảng chuỗi).
- Khóa trùng là `paper_id` sau khi bỏ phiên bản.
- Giữ bản ghi xuất hiện trước; bản sau tăng `duplicates_skipped`.
- `is_saved = paper_id in saved_ids`; `local_path` chỉ có khi đã lưu, lấy từ fixture `saved.json` dạng object `{ "<id>": "<path>" }`; nếu fixture là mảng thì `local_path = null`.
- `read_status` luôn `"UNREAD"`.

## 7. Output JSON

```json
{
  "schema_version": 1,
  "query": {
    "search_query": "all:agent memory AND (cat:cs.AI OR cat:cs.CL) AND submittedDate:[202601010000 TO 202601312359]",
    "max_results": 250,
    "start_date": "2026-01-01",
    "end_date": "2026-01-31"
  },
  "calls": [
    { "offset": 0, "max_results": 100 },
    { "offset": 100, "max_results": 100 },
    { "offset": 200, "max_results": 50 }
  ],
  "stats": {
    "returned": 250,
    "pages": 3,
    "duplicates_skipped": 1,
    "skipped_entries": 0
  },
  "papers": [
    {
      "paper_id": "2601.00001",
      "title": "Synthetic Paper 001",
      "summary": "Synthetic abstract 001.",
      "authors": ["Author 001"],
      "published": "2026-01-31T10:00:00+00:00",
      "pdf_link": "http://arxiv.org/pdf/2601.00001v2.pdf",
      "primary_category": "cs.AI",
      "is_saved": false,
      "local_path": null,
      "read_status": "UNREAD"
    }
  ],
  "error": null
}
```

Khi lỗi: `error` là object `{ "code": ..., "message": ..., "offset": ... }` hoặc `null`; `papers` vẫn chứa phần đã nhận. Exit code: 0 thành công (kể cả 0 kết quả), 1 có `error`, 2 tham số sai, 3 ghi file lỗi.

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | `max_results=1` | một lời gọi `(0,1)`, một paper |
| 2 | `max_results=250` | gọi `(0,100),(100,100),(200,50)` |
| 3 | Trang 100 rỗng | dừng, `returned` theo trang 0 |
| 4 | Trang 200 có 10 entry dù xin 50 | nhận 10, offset 210, tiếp tục |
| 5 | Cùng paper ở trang 0 và 100 | giữ bản đầu, `duplicates_skipped=1` |
| 6 | `id` có `v12` | `paper_id` không có `v12` |
| 7 | Entry thiếu `published` | bỏ entry, `skipped_entries+1` |
| 8 | XML hỏng ở trang 100 | giữ 100 kết quả, `error.code=PAGE_XML` |
| 9 | File trang 404 | `PAGE_HTTP`, status 404 |
| 10 | Chỉ truyền start-date | `INVALID_DATE_RANGE`, exit 2 |
| 11 | `end < start` | `INVALID_DATE_RANGE` |
| 12 | Category sai định dạng | `INVALID_CATEGORY`, exit 2 |
| 13 | Query chứa `(` | `INVALID_QUERY`, exit 2 |
| 14 | `saved.json` là mảng | `local_path=null`, `is_saved` đúng |
| 15 | `pdf_link` thiếu | fallback `http://arxiv.org/pdf/<id>.pdf` |

## 9. Ví dụ cụ thể

Fixture `duplicate/000000.xml` có 3 entry: `2601.00001v2`, `2601.00002v1`, `2601.00001v1`. Kết quả sau trang 0 với `max_results=3`:

- `papers`: 2 mục (`2601.00001`, `2601.00002`);
- `stats.returned=2`, `stats.duplicates_skipped=1`;
- `papers[0].pdf_link` lấy từ link PDF của **phiên bản xuất hiện đầu** (`v2`).

## 10. Tiêu chí chấp nhận

- [ ] `build_query` cho đúng 4 ví dụ ở mục 2.
- [ ] `max_results=250` tạo đúng ba lời gọi với `want` 100/100/50.
- [ ] Không có offset trùng trong `calls`.
- [ ] `paper_id` không còn hậu tố `vN` ở mọi kết quả.
- [ ] Trang rỗng dừng vòng lặp, exit 0.
- [ ] XML hỏng giữ kết quả một phần và exit 1.
- [ ] Output khớp schema, không có khóa thừa.
- [ ] Chạy hai lần trên cùng fixture cho byte output giống nhau (trừ đường dẫn `--out`).

## 11. Non-goals

- Không gọi mạng thật, không tải PDF, không lưu paper.
- Không cần rate limiter thật; chỉ cần cấu trúc cho phép chèn sau này.
- Không cần cú pháp ArXiv đầy đủ (`abs:`, `au:`, trường boolean lồng nhau).
- Không cần song song hóa phân trang.
