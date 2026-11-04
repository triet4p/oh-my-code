# GUIDE 60 — Ghi streaming có commit manifest và checkpoint

## 1. Vì sao cần manifest, không phải "thấy file là xong"

Một batch có thể sinh nhiều file (mỗi ngày một file). Đặt từng file bằng `os.replace` là **nhiều** thao tác, không phải một. Crash giữa chừng để lại:

- file 1 đã có, file 2 chưa có;
- nếu resume chỉ kiểm tra "đã có file chưa" và bỏ qua, batch bị **publish thiếu** mà pipeline tưởng đã xong;
- nếu publish lại mà không dọn, có thể sinh tên khác và **trùng dòng**.

Vì vậy:

```text
dọn → ghi tạm → đặt từng part → COMMIT MANIFEST (nguyên tử) → checkpoint
```

Manifest là mốc duy nhất. Trước manifest: coi như chưa có gì, dọn sạch và làm lại. Sau manifest: coi như xong, chỉ tiến checkpoint.

## 2. Cấu trúc

```text
src/
├── config.py     # đọc + validate
├── schema.py     # validate_row, normalize, date_of
├── store.py      # purge_batch, place_part, write_commit, load_commit
├── checkpoint.py # load, save_atomic
├── pipeline.py   # run(config, hooks) -> Report
└── __main__.py
```

Hook:

```python
class Hooks:
    def after_parts_moved(self, batch_id): ...   # crash → mất manifest
    def before_checkpoint(self, batch_id): ...   # crash → manifest có, checkpoint chưa
```

## 3. Thứ tự cài đặt

### Bước 1 — Validate dòng

Thứ tự: object → `event_time` int (loại `bool`) → `user_id` str khác rỗng → `action` thuộc tập → `value` rule. Mã lý do dạng `invalid_type:event_time` để grep được.

### Bước 2 — Ngày phân vùng

```python
datetime.fromtimestamp(event_time, tz=timezone.utc).strftime("%Y-%m-%d")
```

Không dùng `fromtimestamp(ts)` không tz — phụ thuộc timezone máy và làm test flaky.

### Bước 3 — Nhóm theo ngày + sinh tên file

Với batch `b`:

- Nhóm valid theo `date`, sắp ngày tăng.
- `n = số nhóm`.
- `n == 1` ⇒ `date=<D>/part-<b>.jsonl`.
- `n > 1` ⇒ `date=<D>/part-<b>-<seq>.jsonl`, `seq = 0..n-1`.
- Dead: `part-<b>.jsonl` trong `dead_dir`, một dòng mỗi bản ghi hỏng, sắp offset tăng.

Viết `names_for(batch_id, groups)` trả cặp (đường dẫn, nội dung) — một nguồn duy nhất cho cả purge và place.

### Bước 4 — Purge

```python
for p in glob(output_dir / "date=*" / f"part-{b}.jsonl"): p.unlink()
for p in glob(output_dir / "date=*" / f"part-{b}-*.jsonl"): p.unlink()
for p in glob(dead_dir / f"part-{b}.jsonl"): p.unlink()
```

Chỉ chạy khi **chưa có** `_commits/batch-<b>.json`. Purge khi manifest tồn tại là phá dữ liệu đã commit.

### Bước 5 — Ghi tạm và đặt vào chỗ

Ghi mỗi nhóm vào `_tmp/part-<b>-<seq>.jsonl` (chế độ `"w"`), đóng hẳn, rồi `os.replace` sang đích. Không append, không ghi trực tiếp vào đích.

### Bước 6 — Manifest

```python
manifest = {"batch_id": b, "next_offset": next_off, "files": [...], "dead": [...]}
tmp = commit_dir / f".batch-{b}.json.tmp"
tmp.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
os.replace(tmp, commit_dir / f"batch-{b}.json")
```

Chỉ sau bước này mới gọi `before_checkpoint`.

### Bước 7 — Checkpoint

`next_offset += len(rows)`, `batch_id += 1`, ghi `tmp` + `os.replace`.

### Bước 8 — Resume

```python
if (commit_dir / f"batch-{b}.json").exists():
    next_offset += min(batch_size, len(topic) - next_offset)
    skipped_committed += 1
    # rows_written += 0
    ghi checkpoint
    continue
```

Không đọc nội dung manifest để suy ra span; span suy từ `next_offset`, `batch_size`, `len(topic)` — luôn xác định.

Cuối `run`, ghi checkpoint ngay cả khi không có batch nào (ví dụ `latest` với topic đã cạn). Nếu bỏ qua, lần sau `latest` lại bắt đầu từ cuối và bạn không bao giờ quan sát được trạng thái "đã khởi tạo".

## 4. Cạm bẫy

- **Coi một part là dấu hiệu đã publish**: đúng lỗi mà bài này muốn loại bỏ. Chỉ manifest mới là mốc.
- **Append dead-letter vào file dùng chung**: crash trước checkpoint ⇒ ghi trùng. Dùng file theo batch + purge.
- **Purge sau khi đã ghi tạm nhưng trước khi đặt**: thứ tự không quan trọng miễn là trước `os.replace`; nhưng nếu purge sau khi đặt, bạn xoá chính file vừa ghi.
- **Ghi manifest trước khi đặt đủ part**: mất dữ liệu vĩnh viễn.
- **`open(..., "a")` cho data part**: resume sinh bản ghi trùng trong cùng file.
- **`shutil.move` thay `os.replace`**: có thể copy-rồi-xoá, không nguyên tử.
- **Quên xoá `_tmp`**: rác tích luỹ; dọn sau khi manifest xong (không phải trước, để còn debug khi crash).
- **`fromtimestamp` không tz**: ngày lệch theo máy.
- **`event_time` kiểu bool**: `True` là `int`; kiểm tra `type(x) is int`.
- **Đếm `rows_written` cho batch bị skip**: phải là 0.
- **`data_loss` reset mỗi lần chạy**: chỉ đặt khi phát hiện.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `clean_run` | 8.1: 3 file, 5 dòng, 3 manifest |
| `rerun` | 8.2: không ghi gì |
| `crash_before_manifest` | 8.3: tổng dòng 5 sau resume; nội dung part giống hệt |
| `crash_after_manifest` | 8.4: `skipped_committed = 1`, `rows_written = 1` |
| `lone_part_ignored` | đặt sẵn `part-0.jsonl` cũ khi batch 0 chưa commit ⇒ bị dọn, publish lại, không trùng |
| `multi_file_batch` | 8.5: hai part, một manifest liệt kê cả hai; mô phỏng crash-giữa-file bằng cách đặt sẵn `part-0-0.jsonl` cũ |
| `dead_letter_once` | 8.6: chạy 5 lần, `dead/` vẫn đúng 1 bản ghi cho offset 1 |
| `latest` | 8.7 |
| `data_loss` | 8.7 hai nhánh |
| `schema_mismatch` | đổi `schema_version` ⇒ lỗi |
| `atomic_writes` | không còn `*.tmp` sau chạy |
| `determinism` | hai lần chạy sạch ⇒ nội dung giống hệt |

Crash injection:

```python
class Boom(Hooks):
    def __init__(self, phase, batch): self.phase, self.batch = phase, batch
    def after_parts_moved(self, b):
        if self.phase == "after_parts" and b == self.batch: raise RuntimeError("crash")
    def before_checkpoint(self, b):
        if self.phase == "before_ckpt" and b == self.batch: raise RuntimeError("crash")
```

Test dùng `unittest`/`pytest` đều được; không cần process hay signal.

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src run --config fixtures/config.json
cat out/checkpoint.json
ls out/_commits out/data/date=2023-11-14 | sort
```

So với SPEC 8.1. Kiểm tra không trùng sau nhiều lần:

```bash
python -m src run --config fixtures/config.json
python -m src run --config fixtures/config.json
cat out/data/date=*/*.jsonl | wc -l
```

Kỳ vọng `5`. Kiểm tra manifest là nguồn sự thật:

```bash
python - <<'PY'
import json, pathlib
for p in sorted(pathlib.Path("out/_commits").glob("batch-*.json")):
    m = json.loads(p.read_text())
    print(m["batch_id"], m["next_offset"], [f["path"] for f in m["files"]])
PY
```

Mỗi batch chỉ một manifest; tổng `rows` trong `files` = 5.

## 7. Gợi ý

- Viết `place_batch(...)` như một hàm nhận danh sách `(dest, content)` đã tính sẵn; test nó trên thư mục tạm mà không cần topic.
- Viết `committed(batch_id)` là một dòng `Path.exists`; dùng nó ở **mọi** nhánh quyết định.
- Đừng dùng timestamp trong tên file; muốn thời gian thì để trong nội dung.
- Nếu muốn chứng minh tính idempotent mạnh hơn: băm nội dung các file part sau mỗi lần resume và so với lần đầu.

## 8. Mở rộng

- **Compaction**: gộp các part theo ngày thành một file; cập nhật manifest kiểu "generation" để không phá idempotency.
- **Lease một writer**: file `_lease` với PID + heartbeat; test hai tiến trình.
- **fsync**: fsync từng part và thư mục trước khi ghi manifest; mô phỏng mất điện bằng cách bỏ fsync và so.
- **Watermark**: bỏ dòng có `event_time` cũ hơn X so với max đã thấy, ghi rõ mất mát.
- **Định dạng cột**: thay JSONL bằng parquet nếu có thư viện cục bộ; giữ nguyên manifest/checkpoint.
