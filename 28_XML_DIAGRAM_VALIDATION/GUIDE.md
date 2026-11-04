# GUIDE 28 — Thiết kế validator draw.io

## 1. Kiến trúc

```
drawio_validate/
├─ model.py      # Issue, Rect
├─ style.py      # parse_style
├─ geometry.py   # geometry()
├─ validate.py   # validate(path) -> issues, stats
└─ cli.py
fixtures/
```

Giữ `validate` thuần theo file; CLI chỉ format. Test có thể gọi `validate(Path(...))`.

## 2. Dữ liệu

```python
@dataclass(frozen=True)
class Issue:
    severity: str      # "error" | "warning"
    page: str
    cell_id: str | None
    message: str

@dataclass(frozen=True)
class Rect:
    x: float; y: float; width: float; height: float
    def intersects(self, other): ...
```

`Rect.intersects` dùng điều kiện chặt; nếu dùng `<=` sai, hai ô chạm biên sẽ bị báo chồng.

## 3. Parse style

```
for item in style.split(";"):
    if not item: continue
    key, sep, value = item.partition("=")
    result[key] = value if sep else ""
```

Không dùng `split("=")` vì value có thể chứa `=` (data URI base64 có `=`). `partition` giữ phần còn lại.

## 4. Validate theo trang

1. Parse file; bắt `ParseError`/`OSError`.
2. Kiểm tra root.
3. Kiểm tra compressed.
4. Lặp diagram:
   - lấy tên;
   - tìm `mxGraphModel`; nếu thiếu, issue và `continue`;
   - tìm `root`; nếu thiếu, issue và `continue`;
   - duyệt `root.findall("mxCell")` (chỉ con trực tiếp; tế bào lồng trong `UserObject` không được xử lý — ghi rõ non-goal hoặc mở rộng).
   - xây `cell_by_id`, phát hiện trùng/thiếu.
   - duyệt cell theo thứ tự tài liệu để đếm vertex/edge, kiểm tra geometry/endpoint.
   - thu thập image/text cell.
   - kiểm tra chéo overlap.

## 5. Bẫy thường gặp

- **`mxCell` lồng trong `<UserObject>`**: draw.io thường bọc cell trong `UserObject`; validator nguồn chỉ tìm trực tiếp nên bỏ sót. Bài giữ phạm vi hẹp; nếu muốn hỗ trợ, phải đệ quy và gán id từ `UserObject`.
- **`value` rỗng**: không phải text cell.
- **`swimlane`**: là container, nhãn của nó không nên tính overlap.
- **`shape=image` nhưng không có `image`**: error, không warning.
- **Image icon có value**: vẫn không phải text cell; nhãn icon không được kiểm tra overlap.
- **Edge có `mxGeometry` nhưng thiếu `as="geometry"`**: nguồn không kiểm tra; bài cũng không.
- **Tọa độ tương đối của edge**: không dùng cho stats.
- **`float("nan")`**: `nan <= 0` là false, nên nếu không kiểm tra `isfinite`, geometry NaN lọt. Dùng `math.isfinite`.
- **ID trùng ở hai trang**: hợp lệ; chỉ trùng trong cùng trang mới lỗi.
- **Không có `name`**: page index 1-based.

## 6. Gỡ lỗi

- In stats trước issues để phân biệt “không đọc được” với “đọc được nhưng sai”.
- Với overlap, in cả hai rect khi debug; xóa trước khi nộp.
- Kiểm tra `len(issues)` cho từng fixture.
- Thử `--strict` trên `valid.drawio`: exit 0.
- Thử file XML hỏng: exit 1, một issue `severity=error`, `page="<file>"`.
- Đảm bảo output JSON không có text lẫn vào stdout.

## 7. Kiểm chứng

```bash
cd 28_XML_DIAGRAM_VALIDATION
python -m drawio_validate fixtures/valid.drawio
python -m drawio_validate fixtures/overlap.drawio --strict; echo "exit=$?"
python -m drawio_validate fixtures/valid.drawio --json > /tmp/v.json
python - <<'PY'
import json
d=json.load(open('/tmp/v.json'))
assert d['stats']=={'pages':1,'vertices':4,'edges':1,'images':1}, d
assert d['issues']==[], d
print('ok')
PY
```

Test:

```bash
python -m unittest discover -s tests -v
```

## 8. Gợi ý

- Viết `parse_style` và `Rect.intersects` trước; test biên.
- Dùng `ET.parse` thay vì `fromstring` để giữ lỗi file.
- Không dùng `assert` cho kiểm tra runtime.
- Tách `_validate_page(diagram, index) -> (issues, stats_delta)` để dễ test.
- Đừng cố sửa file; validator chỉ đọc.

## 9. Mở rộng

1. Hỗ trợ `UserObject` bọc cell.
2. Kiểm tra `parent` tồn tại và không tạo chu trình.
3. Kiểm tra nhãn cạnh chồng đỉnh.
4. Thêm chế độ `--fix` tách riêng, không bao giờ mặc định.
5. Tích hợp pre-commit và CI, in diff khi strict.
