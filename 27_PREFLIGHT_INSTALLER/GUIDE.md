# GUIDE 27 — Thiết kế preflight và apply

## 1. Kiến trúc

```
installer/
├─ model.py     # Action, Plan, InstallError
├─ scan.py      # liệt kê file, chuẩn hóa, chống symlink
├─ plan.py      # preflight + conflict
├─ apply.py     # backup + atomic write
├─ cli.py
└─ digest.py
fixtures/
```

Tách `plan()` khỏi `apply()`. Test preflight chỉ cần fixture và không ghi gì.

## 2. Mô hình

```python
@dataclass(frozen=True)
class Action:
    root: str
    rel: str
    source: Path
    dest: Path
    action: str          # install | skip | backup_replace
    source_hash: str
    dest_hash: str | None

@dataclass
class Plan:
    actions: list[Action]
    conflicts: list[str]
```

`source`/`dest` là đường dẫn tuyệt đối nội bộ; summary chỉ xuất `root` + `rel`.

## 3. Quét an toàn

- Dùng `os.walk(..., followlinks=False)`; kiểm tra `Path.is_symlink()` cho cả thư mục và file.
- Không dùng `glob("**")` vì có thể đi qua symlink tùy nền tảng.
- Kiểm tra `path.resolve(strict=True)` nằm trong `root.resolve()`; nếu không → `UNSAFE_PATH`.
- Chuẩn hóa tên: `unicodedata.normalize("NFC", name)` có thể làm hai tên khác nhau trùng nhau; nếu muốn chặt, từ chối tên không NFC.
- Từ chối tên rỗng, `.`/`..`, ký tự `< 0x20`, `:` trên Windows (ổ đĩa), `/` `\` trong segment.

## 4. Preflight

Thứ tự gợi ý:

1. Validate tham số và overlap.
2. Với từng root: kiểm tra tồn tại, là thư mục, có file; nếu không, dừng ngay.
3. Thu thập tất cả file vào list tạm; kiểm tra giới hạn tổng.
4. Sắp xếp theo `(root_order, rel)`.
5. Với mỗi file: hash nguồn, xét đích, xác định action.
6. Phát hiện xung đột; nếu không force → dừng.

**Bẫy:** nếu bạn kiểm tra conflict và apply trong cùng vòng lặp, file đầu tiên có thể đã bị ghi trước khi phát hiện conflict ở file sau. Luôn tách hai pha.

## 5. Ghi atomic

```python
tmp = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
with open(tmp, "wb") as f:
    f.write(data)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, dest)
```

- Tạo thư mục cha trước.
- Nếu `os.replace` lỗi, cố xóa tmp trong `finally` (không che lỗi gốc).
- Không dùng `shutil.copy2` trực tiếp vào đích: ghi dở sẽ để lại file nửa vời.
- Với backup, dùng cùng cơ chế; backup phải hoàn tất trước khi ghi đè.

## 6. Backup

- Đường dẫn: `home / root / ".install-backups" / backup_id / rel`.
- `backup_id` chỉ cho `[A-Za-z0-9._-]{1,64}`, không `.`/`..`.
- Nếu tồn tại bất kỳ file backup → lỗi; không ghi đè backup cũ.
- Sau khi copy, so hash; nếu sai, dừng trước khi ghi đè đích.

## 7. What-if

- Vẫn chạy toàn bộ preflight, kể cả kiểm tra quyền cha gần nhất.
- Không tạo thư mục, không copy, không backup.
- In summary với `what_if=true`; `counts.installed=0`.
- Nếu có conflict, **vẫn exit 0** vì đây là chế độ xem; ghi conflict trong summary. (Khác chế độ thật, nơi conflict là exit 1.)

## 8. Bẫy thường gặp

- **So sánh mtime**: sai; dùng hash. Mtime thay đổi khi checkout git.
- **Copy trước, kiểm tra sau**: vi phạm preflight.
- **`os.path.join(home, rel)` với rel tuyệt đối**: trên Python, path tuyệt đối ghi đè home. Luôn kiểm tra trước.
- **Theo symlink**: có thể đọc/ghi ngoài cây. Từ chối.
- **Tạo thư mục trong preflight**: what-if sẽ để lại rác.
- **Backup vào ngoài home**: rò dữ liệu; luôn trong root tương ứng.
- **Xóa file đích thừa**: ngoài phạm vi và nguy hiểm.
- **Ghi đè khi hash giống**: làm mtime đổi, phá idempotence.
- **Bỏ qua preset khi `--no-preset` nhưng vẫn tính trong planned**: sai count.
- **Summary chứa đường dẫn tuyệt đối**: rò thông tin máy; chỉ tương đối.

## 9. Kiểm chứng

```bash
cd 27_PREFLIGHT_INSTALLER
# chụp trạng thái
find fixtures/home -type f -exec sha256sum {} \; | sort > /tmp/before.txt
python -m installer --source fixtures/payload --home fixtures/home --summary-out /tmp/plan.json
echo "exit=$?"   # 1
find fixtures/home -type f -exec sha256sum {} \; | sort > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt   # phải giống
```

What-if:

```bash
python -m installer --source fixtures/payload --home fixtures/home --what-if --summary-out /tmp/w.json
find fixtures/home -type f | wc -l   # không đổi
```

Force:

```bash
cp -r fixtures/home /tmp/home-test
python -m installer --source fixtures/payload --home /tmp/home-test \
  --force --backup-id test-run-001 --summary-out /tmp/f.json
sha256sum /tmp/home-test/.agents/skills/.install-backups/test-run-001/s1/SKILL.md
```

Test:

```bash
python -m unittest discover -s tests -v
```

## 10. Gợi ý

- Bắt đầu bằng `scan` + test path traversal, symlink.
- Viết `plan` là hàm thuần nhận danh sách file; test conflict không cần copy.
- Viết `apply` nhận Plan; test với thư mục tạm `tempfile.TemporaryDirectory`.
- Dùng `hashlib.file_digest` (Python 3.11) để hash file lớn.
- Đừng in nội dung file khi lỗi; chỉ in hash rút gọn nếu cần.

## 11. Mở rộng

1. Thêm chế độ `--prune` có xác nhận rõ ràng; mặc định tắt.
2. Thêm manifest `installed.json` để gỡ cài đặt.
3. Thêm kiểm tra chữ ký payload.
4. Thêm tiến trình song song có khóa file.
5. Thêm rollback theo transaction log.
