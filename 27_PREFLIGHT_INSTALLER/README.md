# 27 — Trình cài đặt có preflight toàn bộ payload

## Mục tiêu

Viết công cụ cài đặt payload thư mục theo mô hình **plan trước, ghi sau**: quét toàn bộ cây nguồn, kiểm tra từng đích, phát hiện xung đột bằng SHA-256, chỉ rồi mới sao chép; hỗ trợ `--what-if`, `--force` có backup, và chạy lại không thay đổi gì.

## Giá trị

- Cài đặt là thao tác phá hủy; preflight là cách biến “có thể hỏng giữa chừng” thành “hoặc không đổi gì, hoặc làm đúng kế hoạch”.
- Học so sánh nội dung thay vì thời gian sửa file.
- Học chống path traversal, symlink và ghi ngoài thư mục đích.
- Học thiết kế CLI có chế độ xem trước và đầu ra máy đọc được.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | `pathlib`, `hashlib`, quyền file; không cần quyền admin |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/coding-agent-stacks`
- File nguồn: <https://github.com/triet4p/coding-agent-stacks/blob/main/install.ps1>
- Hành vi quan sát được:
  - `[CmdletBinding(SupportsShouldProcess = $true)]`, tham số `-HomePath`, `-Force`, `-UsePresetConfig`.
  - `$payloadRoots = @('.agents/rules', '.agents/skills', '.omp/agent/agents')`.
  - `Get-ContentDigest` dùng `SHA256`.
  - Preflight: `# Preflight the entire payload before copying any files.`; lỗi `Missing payload directory` và `Empty payload directory`.
  - Kiểm tra cha của đích: nếu tồn tại nhưng không phải thư mục → `Destination parent is not a directory`.
  - Đích tồn tại nhưng không phải file → `Destination is not a file`.
  - Nếu hash nguồn bằng hash đích → bỏ qua; khác → thêm vào `$conflicts`.
  - Có xung đột và không `-Force` → ném lỗi, **không cài gì**.
  - Backup nằm trong `<root>/.install-backups/<backupId>/<relativePath>`, `backupId` là UTC timestamp + GUID.
  - `ShouldProcess` cho phép `-WhatIf` xem trước.
  - Preset `.omp/agent/config.example.yml` → `.omp/agent/config.yml`.

**Phần là thiết kế của bài:** CLI bằng Python, `--backup-id` tiêm được để test tất định, mã lỗi, JSON summary, atomic write, chống symlink/path traversal, và kiểm tra chồng lấn source/home. Nguồn dùng thời gian + GUID nên backup không tái lập; bài cho phép tiêm ID.

## Hành vi bài tập yêu cầu

- Quét đủ ba root; root thiếu hoặc rỗng là lỗi preflight, không ghi gì.
- Mọi đường dẫn tương đối được chuẩn hóa; từ chối `..`, tuyệt đối, ký tự điều khiển, symlink.
- Lập kế hoạch cho từng file: `install`, `skip` (hash bằng), `backup_replace` (khác hash).
- Không `--force` mà có `backup_replace` → exit 1, danh sách xung đột, **không file nào bị đổi**.
- `--what-if` in kế hoạch, không tạo thư mục, không copy, exit 0.
- `--force` backup từng file bị ghi đè trước khi thay; không xóa file thừa ở đích.
- Ghi atomic: tạo file tạm cùng thư mục, ghi, `os.replace`.
- Chạy lần hai: mọi file `skip`, exit 0, `installed=0`.
- Preset tùy chọn theo cùng quy tắc.

## Phạm vi

Trong phạm vi: preflight, hash, plan, apply, backup, what-if, CLI, test.

Ngoài phạm vi: gỡ cài đặt, cập nhật từ xa, quyền hệ thống, registry Windows, đa người dùng, rollback toàn giao dịch sau lỗi I/O.

## Fixture offline

- `fixtures/payload/`: ba root, vài file nhỏ, một file preset.
- `fixtures/home/`: đích có file trùng hash, file khác hash.
- `fixtures/invalid/`: root thiếu, root rỗng, symlink (tạo trong test, không commit), đường dẫn `..`.
- Nội dung tổng hợp, không credential.

## Liên kết

- [SPEC.md](SPEC.md) — thuật toán preflight/apply, mã lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế plan, atomic write và kiểm chứng.
