# GUIDE 22 — Thiết kế client phân trang

## 1. Chia module

```
arxiv_pager/
├─ query.py        # build_query, validate
├─ transport.py    # OfflineTransport
├─ atom.py         # parse_page
├─ pager.py        # paginate + dedupe
├─ cli.py          # argparse, JSON output
└─ models.py       # dataclass Paper, PageResult
fixtures/
├─ pages/*.xml
├─ saved.json
└─ expected/*.json
```

`query`, `atom`, `pager` phải là hàm thuần hoặc nhận dependency rõ ràng; CLI chỉ nối dây.

## 2. Cấu trúc dữ liệu

```python
@dataclass(frozen=True)
class Paper:
    paper_id: str
    title: str
    summary: str
    authors: tuple[str, ...]
    published: str          # ISO-8601 có offset
    pdf_link: str
    primary_category: str
    is_saved: bool
    local_path: str | None
    read_status: str = "UNREAD"

@dataclass
class ParseOutcome:
    papers: list[Paper]
    skipped: int
    warnings: list[dict]
    fatal: bool = False
    message: str | None = None
```

Dùng tuple cho `authors` để tránh sửa ngoài ý muốn; output chuyển list.

## 3. Query builder — các bước

1. Validate đầu vào trước khi ghép chuỗi.
2. Chuẩn hóa keyword; kiểm tra ký tự nguy hiểm **chỉ khi** không có tiền tố `all:`/`cat:`.
3. Thêm category; nếu không có gì thì mặc định.
4. Ghép ` AND `.
5. Ghép ngày bằng phép cộng chuỗi cuối cùng.

Gợi ý: viết bảng test dạng `(query, cats, dates) -> expected`; đây là phần dễ đạt 100% test nhất.

**Bẫy:** `query` rỗng nhưng categories rỗng vẫn phải ra `cat:cs.AI`, không phải chuỗi rỗng. `query` đã có `cat:` không được bọc thêm `all:`.

## 4. Transport

`OfflineTransport.fetch_page(offset, max_results)`:

- Mở file theo offset; không dùng `glob` mơ hồ.
- Parse XML gốc, lấy danh sách `<entry>` theo namespace.
- Cắt `entries[:max_results]`, dựng lại một `<feed>` tối thiểu hoặc trả thẳng danh sách entry cho parser (đơn giản hơn: trả `body` đã cắt).
- Không cache ngầm giữa các lần gọi; test cần thấy đúng lời gọi.

Có thể thêm `SlowTransport` để mô phỏng lỗi, nhưng không cần.

## 5. Parser

- Dùng `ET.fromstring`; kiểm tra `root.tag == "{atom}feed"`.
- Helper `text(entry, "title")` trả `None` nếu thiếu; helper `clean_text` gộp newline và space.
- Tách `paper_id` bằng `rsplit("/abs/", 1)[-1]`, rồi `re.sub(r"v\d+$", "", value)`.
- Với `published`: thay `Z` bằng `+00:00`, `datetime.fromisoformat`; nếu không có timezone, gắn UTC (nhưng ghi cảnh báo).
- PDF: tìm `link` có `title="pdf"`; fallback từ `id_url`.
- Mỗi entry bọc trong `try/except (AttributeError, ValueError, TypeError)`; không bắt `KeyboardInterrupt`/`SystemExit`.

**Bẫy:** namespace sai làm `findall('entry')` trả rỗng mà không lỗi. Luôn dùng prefix đầy đủ. Title có newline và thẻ XML con (hiếm) — dùng `"".join(itertext())` thay vì `.text`.

## 6. Vòng phân trang

- Tính `want` từ phần còn thiếu, không luôn 100.
- Gọi transport, kiểm tra status trước khi parse.
- Chỉ tăng `received_total` cho entry được nhận sau khử trùng? Cần quyết định: `max_results` là số **kết quả cuối**, hay số entry thô?

Thiết kế chọn: `received_total` đếm entry **đã nhận và vượt qua parse**, kể cả trùng; `papers` là kết quả cuối có thể ít hơn. Khi đó `returned` có thể < `max_results` dù còn trang. Nếu muốn lấp đầy, phải tiếp tục cho đến khi đủ kết quả hoặc hết trang, với guard `max_pages`. Bài chọn cách đơn giản, tất định: dừng khi `received_total >= max_results`; ghi `stats.received`.

- `offset += len(page.papers)` chứ không `+= want`: nếu server trả thiếu, không nhảy qua bản ghi.
- Guard `pages < 100` để tránh transport lỗi gây lặp vô hạn.
- Không gọi trang mới nếu `want == 0`.

## 7. Khử trùng

Dùng `seen: set[str]`. Kiểm tra trước khi append. Nếu bản ghi trùng nhưng bản mới có version cao hơn, bài vẫn giữ bản đầu (đơn giản, khớp thứ tự giảm dần của API). Ghi chú rõ trong README nếu bạn chọn ngược lại.

## 8. Kiểm tra gỡ lỗi

- In `calls` khi chạy `--debug` (cờ tùy chọn) để thấy offset/want.
- Viết test cho `parse_page` với: feed rỗng, entry thiếu title, ngày `Z`, ngày có offset, id không có `/abs/`.
- Kiểm tra `query` bằng cách so chuỗi chính xác, không `in`.
- Chạy với `max_results=99`, `100`, `101` để bắt lỗi biên.
- Thử fixture có entry trùng ở hai trang.
- Chạy hai lần, so hash file output.

## 9. Kiểm chứng độc lập

```bash
cd 22_ARXIV_PAGINATION
python -m arxiv_pager --fixtures fixtures --query "agent memory" \
  --categories cs.AI,cs.CL --max-results 250 \
  --start-date 2026-01-01 --end-date 2026-01-31 --out /tmp/out.json
python - <<'PY'
import json
d = json.load(open('/tmp/out.json', encoding='utf-8'))
assert [c["max_results"] for c in d["calls"]] == [100, 100, 50], d["calls"]
assert len(d["papers"]) == 250
assert all(not p["paper_id"].split(".")[-1].startswith("v") for p in d["papers"])
print(d["stats"])
PY
```

Test thuần:

```bash
python -m unittest discover -s tests -v
```

Nếu dùng `--out` trên Windows, dùng đường dẫn có ổ đĩa; script không phụ thuộc `/tmp`.

## 10. Gợi ý (không lời giải)

- Bắt đầu bằng `build_query` + test bảng; sau đó parser; cuối cùng vòng lặp.
- Đừng để parser tự khử trùng; tách trách nhiệm.
- Dùng `dataclasses.replace` nếu cần thêm `local_path` sau khi parse.
- Với XML, viết helper `find_text` để tránh lặp `.find(...).text` gây `AttributeError`.
- Nếu output lệch byte, kiểm tra `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=False)` và newline cuối.

## 11. Mở rộng

1. Thêm `PDFTransport` thật sau interface, giữ nguyên pager.
2. Thêm rate limiter dạng token bucket có đồng hồ tiêm được.
3. Thêm sắp xếp theo `published` sau khi nhận, ổn định với tie-break `paper_id`.
4. Thêm chế độ resume từ offset đã lưu.
5. Thêm kiểm tra chữ ký/định dạng ngày chặt hơn bằng schema JSON.
