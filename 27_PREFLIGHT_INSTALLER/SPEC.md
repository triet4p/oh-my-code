# SPEC 27 — Installer preflight

## 1. CLI

```bash
python -m installer \
  --source fixtures/payload \
  --home fixtures/home \
  --backup-id test-run-001 \
  --force \
  --summary-out plan.json
```

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--source` | bắt buộc | thư mục payload chứa các root |
| `--home` | bắt buộc | thư mục đích |
| `--what-if` | false | chỉ in kế hoạch |
| `--force` | false | cho phép backup + ghi đè |
| `--backup-id` | sinh từ UTC + UUID | tên thư mục backup; test truyền cố định |
| `--no-preset` | false | bỏ qua preset |
| `--summary-out` | stdout | ghi JSON summary |

Exit code: `0` thành công hoặc không đổi; `1` xung đột; `2` payload/đường dẫn không hợp lệ; `3` lỗi ghi.

## 2. Root và preset

Root theo thứ tự:

1. `.agents/rules`
2. `.agents/skills`
3. `.omp/agent/agents`

Mỗi root phải là thư mục tồn tại và chứa **ít nhất một file thường** (đệ quy). Thư mục chỉ có thư mục con rỗng = rỗng.

Preset (mặc định bật): nguồn `.omp/agent/config.example.yml` → đích `.omp/agent/config.yml`. Nếu file nguồn thiếu → lỗi `MISSING_PRESET`; nếu `--no-preset` → bỏ qua hoàn toàn.

## 3. Chuẩn hóa đường dẫn

Với mỗi file nguồn:

1. Lấy đường dẫn tương đối so với root, chuyển `\` thành `/`.
2. Từ chối nếu:
   - tuyệt đối, có ổ đĩa, bắt đầu `/` hoặc `\`;
   - chứa segment `..`, `.`, hoặc segment rỗng;
   - chứa NUL hoặc ký tự điều khiển `< 0x20`;
   - là symlink hoặc nằm dưới symlink trong cây nguồn;
   - tên kết thúc bằng dấu cách hoặc dấu chấm (Windows không an toàn).
3. Đích = `home / root / relative`.
4. Kiểm tra `resolve()` của đích vẫn nằm trong `home.resolve()`; nếu không → `UNSAFE_PATH`.

`source` và `home` không được chồng lấn: `source` nằm trong `home`, hoặc `home` nằm trong `source` → `OVERLAP`.

## 4. Preflight

Duyệt file theo thứ tự `sorted(relative_path)` (so sánh chuỗi Unicode). Với mỗi file:

1. `size <= 2 MiB`; tổng payload `<= 50 MiB`; số file `<= 10000`.
2. Tính `source_hash = sha256(bytes).hexdigest()`.
3. Xét đích:
   - không tồn tại → `install`;
   - tồn tại nhưng là thư mục/symlink → `DEST_NOT_FILE`, exit 2;
   - tồn tại, hash bằng → `skip`;
   - tồn tại, hash khác → `backup_replace`.
4. Kiểm tra cha gần nhất đã tồn tại: nếu là file → `DEST_PARENT_NOT_DIR`, exit 2. Không tạo thư mục trong preflight.
5. Với `backup_replace`: đường dẫn backup = `<home>/<root>/.install-backups/<backup_id>/<relative>`. Nếu đã tồn tại → `BACKUP_COLLISION`.

Sau khi duyệt hết:

- Nếu có `backup_replace` và không `--force` → `CONFLICT`, exit 1, liệt kê đích theo thứ tự.
- Nếu `--what-if` → in kế hoạch, exit 0, không thay đổi gì.
- Ngược lại apply.

## 5. Apply

Với từng mục `install`/`backup_replace` theo thứ tự:

1. Nếu `backup_replace`:
   - tạo thư mục backup;
   - sao chép đích → backup (atomic cũng được);
   - xác minh hash backup == hash đích cũ; sai → dừng `BACKUP_MISMATCH`.
2. Đảm bảo thư mục cha của đích tồn tại.
3. Ghi atomic: file tạm `.<name>.tmp-<pid>` cùng thư mục, ghi bytes, `flush`, `os.fsync`, `os.replace`.
4. Sau ghi, đọc lại và so hash; sai → `VERIFY_FAILED`.

Không xóa file đích không có trong payload. Không đổi quyền file trừ khi hệ điều hành bắt buộc.

## 6. Summary JSON

```json
{
  "schema_version": 1,
  "backup_id": "test-run-001",
  "what_if": false,
  "counts": { "planned": 4, "installed": 2, "skipped": 2, "backed_up": 1 },
  "actions": [
    { "root": ".agents/rules", "path": "a.md", "action": "install", "source_sha256": "…", "dest_sha256": null },
    { "root": ".agents/rules", "path": "b.md", "action": "skip", "source_sha256": "…", "dest_sha256": "…" },
    { "root": ".agents/skills", "path": "s1/SKILL.md", "action": "backup_replace", "source_sha256": "…", "dest_sha256": "…" }
  ],
  "conflicts": [],
  "error": null
}
```

- `actions` sắp theo `(root_order, path)`.
- Không có đường dẫn tuyệt đối trong summary, chỉ tương đối.
- `counts.planned` = số file nguồn sau preset.
- Khi lỗi preflight, `actions` có thể rỗng và `error = {code, message, path?}`.

## 7. Mã lỗi

| Mã | Exit | Nghĩa |
|---|---|---|
| `MISSING_ROOT` | 2 | root không tồn tại/không phải thư mục |
| `EMPTY_ROOT` | 2 | root không có file |
| `MISSING_PRESET` | 2 | preset bật nhưng thiếu nguồn |
| `UNSAFE_PATH` | 2 | đường dẫn thoát home hoặc không hợp lệ |
| `SYMLINK` | 2 | file/thư mục nguồn là symlink |
| `TOO_LARGE` | 2 | file/tổng vượt giới hạn |
| `DEST_NOT_FILE` | 2 | đích là thư mục/symlink |
| `DEST_PARENT_NOT_DIR` | 2 | cha đích là file |
| `OVERLAP` | 2 | source/home chồng lấn |
| `CONFLICT` | 1 | có ghi đè khi không force |
| `BACKUP_COLLISION` | 1 | backup đã tồn tại |
| `BACKUP_MISMATCH` | 3 | backup không khớp bản gốc |
| `VERIFY_FAILED` | 3 | ghi xong nhưng hash sai |
| `APPLY_IO` | 3 | lỗi I/O khi ghi |

## 8. Ví dụ cụ thể

Payload:

```
.agents/rules/a.md          "alpha\n"
.agents/rules/b.md          "beta\n"
.agents/skills/s1/SKILL.md  "skill v2\n"
.omp/agent/agents/x.md      "agent\n"
.omp/agent/config.example.yml "preset: 1\n"
```

Home:

```
.agents/rules/b.md          "beta\n"        (giống)
.agents/skills/s1/SKILL.md  "skill v1\n"    (khác)
```

### 8.1. Không force

- `a.md`: install.
- `b.md`: skip.
- `s1/SKILL.md`: backup_replace → xung đột.
- `x.md`: install; preset: install.
- Exit 1, `conflicts=[".agents/skills/s1/SKILL.md"]`; home giữ nguyên `skill v1`.

### 8.2. Force, backup id `test-run-001`

- Backup: `<home>/.agents/skills/.install-backups/test-run-001/s1/SKILL.md` chứa `"skill v1\n"`.
- Đích `s1/SKILL.md` chứa `"skill v2\n"`.
- `a.md`, `x.md`, preset được tạo.
- `counts: planned=5, installed=4, skipped=1, backed_up=1`.

### 8.3. What-if

Cùng kế hoạch nhưng không tạo backup, không copy, `counts.installed=0`, `actions` vẫn liệt kê `install`/`backup_replace`.

### 8.4. Chạy lại sau 8.2

- Tất cả `skip`, trừ file nào nội dung đổi.
- `installed=0`, `backed_up=0`, exit 0.

## 9. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Root thiếu | `MISSING_ROOT`, không ghi |
| 2 | Root chỉ có thư mục rỗng | `EMPTY_ROOT` |
| 3 | `--what-if` + xung đột | vẫn exit 1? **Không**: what-if chỉ xem; exit 0, liệt kê conflict |
| 4 | `--what-if` + payload sai | exit 2 |
| 5 | Đích là thư mục | `DEST_NOT_FILE` |
| 6 | Cha đích là file | `DEST_PARENT_NOT_DIR` |
| 7 | File nguồn là symlink | `SYMLINK` |
| 8 | Relative chứa `..` | `UNSAFE_PATH` |
| 9 | Tên kết thúc `.` | `UNSAFE_PATH` |
| 10 | Trùng hash | `skip`, không đụng mtime |
| 11 | `--force` nhưng không xung đột | không backup thừa |
| 12 | `backup_id` chứa `/` | `INVALID_BACKUP_ID` |
| 13 | Backup đã tồn tại | `BACKUP_COLLISION`, exit 1 |
| 14 | Home nằm trong source | `OVERLAP` |
| 15 | Tổng payload > 50 MiB | `TOO_LARGE` |
| 16 | Ghi lỗi giữa chừng | `APPLY_IO`; file đã ghi trước đó giữ nguyên, summary ghi rõ |

## 10. Tiêu chí chấp nhận

- [ ] Kịch bản 8.1 không thay đổi bất kỳ file nào (so hash toàn cây home).
- [ ] Kịch bản 8.2 tạo đúng backup và nội dung đích.
- [ ] What-if không tạo thư mục/file nào (so cây home).
- [ ] Chạy lại 8.2 cho `installed=0`.
- [ ] Không có đường dẫn tuyệt đối trong summary.
- [ ] Mọi lỗi preflight xảy ra trước lần ghi đầu tiên.
- [ ] Hash file ghi xong khớp nguồn.
- [ ] Cùng fixture + backup id cho cùng summary (bỏ qua thời gian nếu có).

## 11. Non-goals

- Không cần giao diện, tiến trình nền, cập nhật từ xa.
- Không cần rollback toàn bộ sau lỗi I/O; chỉ cần báo rõ phần đã ghi.
- Không cần xử lý ACL, registry, dịch vụ hệ thống.
- Không được tự ý xóa file đích không có trong payload.
