# SPEC 28 — Validator draw.io

## 1. CLI

```bash
python -m drawio_validate fixtures/valid.drawio
python -m drawio_validate fixtures/overlap.drawio --strict
python -m drawio_validate fixtures/valid.drawio --json
```

- `drawio_file`: bắt buộc, file tồn tại.
- `--strict`: warning cũng làm exit 1.
- `--json`: in một object JSON, không in text.
- Exit: `0` sạch; `1` có error (hoặc warning với `--strict`); `2` lỗi tham số/không đọc được file.

## 2. Cấu trúc hợp lệ

```xml
<mxfile host="app.diagrams.net" compressed="false">
  <diagram id="p1" name="Page 1">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="v1" value="Service" style="rounded=0;whiteSpace=wrap;html=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="160" height="60" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Quy tắc gốc:

| Kiểm tra | Mức | Thông điệp |
|---|---|---|
| Root tag là `mxfile` | error | `Root element must be <mxfile>.` |
| `compressed` bằng `false` (không phân biệt hoa thường) | error | `Source-controlled diagram must set compressed="false".` |
| Có ít nhất một `<diagram>` | error | `No <diagram> pages found.` |
| Mỗi diagram có `<mxGraphModel>` | error | `Page has no editable mxGraphModel; it may be compressed.` |
| Mỗi model có `<root>` | error | `Page has no graph root.` |
| `mxCell` con trực tiếp của root có `id` | error | `mxCell is missing id.` |
| `id` duy nhất trong trang | error | `Duplicate cell id on page.` |

Trang thiếu model/root bị bỏ qua phần còn lại của trang đó; vẫn tiếp tục trang khác.

## 3. Hình học

`parse_style(style)`:

- Tách theo `;`, bỏ item rỗng.
- `key=value` → `key` ánh xạ `value`.
- `key` không có `=` → giá trị chuỗi rỗng.
- Key trùng: giá trị sau thắng.
- Không trim key/value (giữ đúng nguồn); so sánh theo key chính xác.

`geometry(cell)`:

- Không có `mxGeometry` → `None`.
- `x`, `y` mặc định `0`; `width`, `height` mặc định `0`.
- `float()` lỗi → `None`.
- Giá trị `NaN`/`Infinity` → `None` (bổ sung an toàn; nguồn chỉ bắt `ValueError`).

## 4. Vertex

Với `vertex="1"`:

1. Tăng `stats.vertices`.
2. Nếu geometry `None`, width ≤ 0, hoặc height ≤ 0 → error `Vertex needs positive numeric geometry.`
3. Nếu `style.shape == "image"`:
   - tăng `stats.images`;
   - `style.image` rỗng → error `Image cell has no image value.`
   - không bắt đầu `data:image/` → warning `Image is not an embedded data URI; offline rendering may fail.`
   - width > 64 hoặc height > 64 → warning `Product icon exceeds 64 px; inspect scaling and label clearance.`
4. Ngược lại nếu `value` khác rỗng và style không chứa key `swimlane` → đây là **text cell**, dùng cho kiểm tra chồng lấn.

Vertex không có `value` không phải text cell. Shape khác image (kể cả group) không phải text cell nếu không có value.

## 5. Edge

Với `edge="1"`:

1. Tăng `stats.edges`.
2. Không có `mxGeometry` → error `Edge is missing mxGeometry.`
3. Nếu có `source` và id không tồn tại → error `Edge source references unknown cell '<id>'.`
4. Tương tự `target`.
5. `style.edgeStyle != "orthogonalEdgeStyle"` → warning `Edge is not orthogonal; confirm this is an intentional exception.`

Cạnh không có source/target (floating) hợp lệ. Self-loop hợp lệ nếu id tồn tại.

## 6. Chồng lấn ảnh/nhãn

Sau khi duyệt tất cả cell của trang, với mỗi cặp `(image_cell, text_cell)`:

- `Rect.intersects` dùng bất đẳng thức chặt: chạm biên **không** tính chồng.
- Nếu chồng → warning gắn với `image_cell.id`:
  `Image geometry overlaps a labeled node (<text_id>); inspect the rendered page for covered text.`
- Thứ tự cặp theo thứ tự image cell rồi text cell trong tài liệu.

## 7. Output text

```text
pages=1 vertices=4 edges=1 images=1
```

Sau đó mỗi issue một dòng:

```text
ERROR: Page 1/v2: Vertex needs positive numeric geometry.
WARNING: Page 1/img1: Image is not an embedded data URI; offline rendering may fail.
```

- `page` là `diagram@name` nếu có, ngược lại `page-<index>` (1-based).
- `cell_id` `None` → chỉ in page.
- Không in stack trace; lỗi đọc file thành issue `ERROR: <file>: <message>`.

## 8. Output JSON

```json
{
  "stats": { "pages": 1, "vertices": 4, "edges": 1, "images": 1 },
  "issues": [
    {
      "severity": "warning",
      "page": "Page 1",
      "cell_id": "img1",
      "message": "Product icon exceeds 64 px; inspect scaling and label clearance."
    }
  ]
}
```

- `indent=2`, `ensure_ascii=False`.
- `issues` rỗng → `[]`.
- Không có khóa thừa.

## 9. Ví dụ cụ thể — `valid.drawio`

Nội dung:

- `v1` Box `(40,40,160,60)` có value.
- `v2` Box `(260,40,160,60)` có value.
- `e1` từ `v1` đến `v2`, `edgeStyle=orthogonalEdgeStyle`, có `mxGeometry`.
- `v3` Box `(260,200,120,40)` có value.
- `img1` shape image, `data:image/png;base64,AAAA`, `(40,160,48,48)`.

Kết quả:

```text
pages=1 vertices=4 edges=1 images=1
```

Exit 0, không issue.

`overlap.drawio`: `img1` tại `(40,40,48,48)` chồng `v1` → đúng một warning gắn `img1`; exit 0 (không strict), exit 1 (strict).

`duplicate-id.drawio`: hai `mxCell id="v1"` → một error tại `cell_id="v1"`.

`dangling-edge.drawio`: `target="missing"` → error `Edge target references unknown cell 'missing'.`

`compressed.drawio`: `compressed="true"` và body nén → error compressed; nếu không có `mxGraphModel`, thêm error trang không sửa được.

## 10. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | File rỗng | error parse, exit 1 |
| 2 | Root `<svg>` | error root |
| 3 | `compressed` thiếu | error (mặc định true) |
| 4 | `compressed="FALSE"` | hợp lệ |
| 5 | Không có diagram | error pages |
| 6 | Diagram không tên | page `page-1` |
| 7 | Hai trang cùng tên | vẫn xử lý độc lập; page trùng tên trong output |
| 8 | Vertex width `0` | error |
| 9 | Vertex width `-5` | error |
| 10 | Vertex width `abc` | error geometry |
| 11 | Edge không source/target | hợp lệ |
| 12 | Edge source = target | hợp lệ |
| 13 | Ảnh chạm biên text | **không** warning |
| 14 | Hai ảnh chồng nhau | không kiểm tra (chỉ ảnh–text) |
| 15 | Swimlane có value | không tính text cell |
| 16 | `style` rỗng | parse `{}` |
| 17 | `style="shape=image;image="` | error image value |
| 18 | Icon đúng 64×64 | không warning |
| 19 | Icon 64×65 | warning |
| 20 | JSON + strict | exit 1 nếu warning |

## 11. Tiêu chí chấp nhận

- [ ] `valid.drawio` cho đúng dòng stats và exit 0.
- [ ] Mỗi fixture lỗi cho đúng số issue và đúng `severity`.
- [ ] Thứ tự issue ổn định giữa các lần chạy.
- [ ] `--json` parse được, khớp schema, không có output text lẫn vào.
- [ ] `--strict` chỉ đổi exit code, không đổi issue.
- [ ] File hỏng không làm crash.
- [ ] Icon 64×64 không warning; 65 warning.
- [ ] Chạm biên không tính overlap.
- [ ] Không sửa file nguồn.

## 12. Non-goals

- Không render SVG/PNG, không kiểm tra font/màu.
- Không kiểm tra `parent`, layer, z-order.
- Không hỗ trợ file nén; đó là lỗi có chủ đích.
- Không kiểm tra mũi tên, nhãn cạnh, hay chồng cạnh–đỉnh.
