# 60 — Ghi streaming có commit manifest và checkpoint

## Mục tiêu

Mô phỏng một pipeline streaming **không cần Spark**: đọc topic append-only cục bộ theo micro-batch, kiểm tra lược đồ, ghi ra file phân vùng theo ngày, và phát hành theo **commit manifest nguyên tử** để khởi động lại không tạo dòng trùng — kể cả khi một batch sinh nhiều file hoặc có bản ghi lỗi.

1. Đọc theo offset với `batch_size` cố định; dòng hỏng vào dead-letter **theo batch**, không phải file append dùng chung.
2. Mỗi batch publish theo thứ tự: ghi tạm → dọn dấu vết cũ của batch → đặt từng part vào chỗ → **ghi manifest commit** (nguyên tử) → cập nhật checkpoint.
3. **Manifest là nguồn sự thật duy nhất** về việc đã publish; một file part đơn lẻ không bao giờ được coi là batch đã xong.
4. Resume phân biệt bốn trạng thái: chưa có gì, có part mà chưa có manifest, có manifest mà checkpoint chưa tiến, và cả hai đã khớp.
5. Xử lý `failOnDataLoss` và `starting_offsets` như cấu hình.

## Giá trị

- Đây là bài toán "exactly-once" ở mức thực dụng: không có giao dịch phân tán, chỉ có **thứ tự thao tác + idempotency**. Bài tập chỉ ra chỗ mà trực giác "thấy file là xong" sai.
- Publish nhiều file trong một batch là tình huống thật (partition theo ngày); nếu chỉ kiểm tra một file, crash giữa chừng sẽ làm mất dữ liệu hoặc publish thiếu mà không ai biết.
- Dead-letter append là cái bẫy kinh điển: crash trước checkpoint làm bản ghi lỗi bị ghi hai lần. Bài tập buộc dead-letter đi cùng batch và cùng manifest.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`json`, `os`, `pathlib`, `datetime`, `glob`) |
| Độ khó | Khó |
| Điều kiện | Ghi file nguyên tử, offset, lược đồ, `datetime` UTC, suy nghĩ về thứ tự |
| Runtime | Không mạng, không Kafka/HDFS/Spark, không GPU |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/app-log-process-k8s` (nhánh `main`, repo đã archived 2026-08-02)
- File nguồn: <https://github.com/triet4p/app-log-process-k8s/blob/main/docker-images/spark/scripts/streaming_process.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Schema khai báo tường minh: `StructType().add("event_time", DoubleType())…`.
  - Đọc Kafka: `.readStream.format("kafka").option("startingOffsets", "latest").option("failOnDataLoss", "false")`.
  - Phân tích payload: `from_json(col("value"), schema)` cộng `from_unixtime`.
  - Ghi theo lô: `.foreachBatch(write_to_parquet)` với `mode("append")` vào `hdfs://namenode:9000/applog/streaming`.
  - Checkpoint: `.option("checkpointLocation", "hdfs://namenode:9000/checkpoints/logs-v2")`.
- Giới hạn bằng chứng: đọc toàn bộ file (34 dòng theo ghi nhận); không quan sát được nội dung `write_to_parquet`, cấu hình cluster, hay cách xử lý bản ghi hỏng. Spark tự lo tính nguyên tử của checkpoint và commit; bài tập phải tự cài phần đó.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: lược đồ tường minh; hai tùy chọn `startingOffsets` và `failOnDataLoss`; chuyển `event_time` Unix sang phân vùng ngày; ghi append theo batch; checkpoint riêng.

Phần **do bài tập định nghĩa**:

- Topic là file JSONL cục bộ; offset là số dòng 0-based.
- **Commit manifest** cho mỗi batch (nguồn dùng cơ chế commit nội bộ của Spark; bài tập cài tường minh) và quy tắc dọn dấu vết khi chưa có manifest.
- Dead-letter **theo batch** thay vì file append dùng chung.
- Ngữ nghĩa bốn trạng thái resume và bảng hành động tương ứng.
- Hook `after_parts_moved` / `before_checkpoint` để test crash; không dùng process/signal.
- Quy tắc `fail_on_data_loss`, `starting_offsets`, mã lý do dead-letter.

Nguồn **không** bao gồm: Spark, Kafka, HDFS, parquet, giao dịch phân tán, hay watermark.

## Phạm vi

Trong phạm vi:

- Topic ≤ 10 000 dòng; batch ≤ 500; một tiến trình, một writer.
- Ghi JSONL (thay parquet); phân vùng `date=YYYY-MM-DD`; nhiều file mỗi batch khi nhiều ngày.
- Sáu kịch bản: chạy sạch, chạy lại, crash trước manifest, crash sau manifest, batch nhiều file, dead-letter + crash.

Ngoài phạm vi:

- Không Kafka/HDFS/Spark; không parquet; không đa tiến trình, không lease.
- Không `fsync` cho data part; không exactly-once với hệ ngoài.
- Không watermark, cửa sổ thời gian, state store, compaction.

## Cảnh báo production

- Manifest + checkpoint chỉ đúng cho **một** writer. Hai tiến trình cùng ghi sẽ tranh nhau dọn part và ghi manifest; cần lease hoặc scheduler.
- `os.replace` nguyên tử trong cùng filesystem; NFS hoặc khác ổ đĩa có thể không nguyên tử.
- Dọn part theo batch là thao tác **phá huỷ**; chỉ an toàn vì ta biết chưa có manifest. Đừng dọn khi manifest tồn tại.
- Không `fsync` cho data part: mất điện có thể mất dữ liệu đã đặt vào chỗ nhưng chưa xuống đĩa. Bài tập giữ đơn giản; production phải fsync thư mục và file trước khi ghi manifest.
- Dead-letter chứa dòng thô: production phải che dữ liệu nhạy cảm trước khi ghi.

## Fixture offline

- `fixtures/topic_basic.jsonl` — 5 dòng hợp lệ, `event_time = 1700000000` (ngày `2023-11-14`).
- `fixtures/topic_two_days.jsonl` — 3 dòng: 2 dòng ngày `2023-11-14`, 1 dòng `2023-11-15` để một batch sinh hai part.
- `fixtures/topic_with_bad.jsonl` — 3 dòng, dòng offset 1 sai kiểu `event_time`.
- `fixtures/config.json` — `batch_size = 2`, đường dẫn tương đối.
- `fixtures/config_latest.json` — `starting_offsets: latest`.
- Không có URL ngoài; không cần cluster.

## Liên kết

- [SPEC.md](SPEC.md) — lược đồ, manifest, bảng resume, ví dụ file, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế publish/commit, bẫy crash và dead-letter, cách kiểm chứng.
