# 04 — Log generator: sinh sự kiện có kiểm soát

## Mục tiêu

Tự viết một generator sự kiện log chạy cục bộ: đọc cấu hình tần suất, sinh bản ghi có cấu trúc, ghi ra file NDJSON, tôn trọng giới hạn số lượng, và dừng sạch khi bị ngắt. Bài tập lấy ý tưởng từ một producer Kafka nhưng thay sink bằng file để không cần dịch vụ, tài khoản hay cụm.

## Giá trị học được

- Tách **sinh dữ liệu** khỏi **vận chuyển**: cùng một generator có thể ghi file, stdout, hay Kafka.
- Lập lịch theo deadline tuyệt đối thay vì `sleep(interval)` tích lũy sai số.
- Tính tất định khi có seed và mốc thời gian cố định; phân biệt rõ phần tất định và phần phụ thuộc phiên bản thư viện.
- Xử lý `KeyboardInterrupt` mà không để lại dòng JSON dở dang.
- Kiểm tra cấu hình ở biên trước khi mở file.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Dễ – Trung bình**.
- Thời lượng gợi ý: 3–4 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- `PyYAML` và `Faker` (hoặc tự sinh UUID/chuỗi từ seed; xem SPEC).
- Không cần Kafka, Docker, mạng.

## Nguồn gốc

- Nguồn: `triet4p/app-log-process-k8s`, file `docker-images/application/app/sim_log.py`.
- URL chính xác: <https://github.com/triet4p/app-log-process-k8s/blob/main/docker-images/application/app/sim_log.py>

Hành vi quan sát được trong nguồn:

- Đọc YAML tại `CONFIG_PATH = '/etc/sim-config/generator-config.yaml'`.
- Tạo `KafkaProducer` với `bootstrap_servers` và `value_serializer` dùng `json.dumps(...).encode('utf8')`.
- `simulate_log()` trả dict gồm `event_time` (epoch giây), `user_id` (`faker.uuid4()`), `action` chọn từ `['click', 'view', 'purcharse', 'login', 'logout']`, `device` (`faker.user_agent()`), `location` (`faker.city()`).
- `interval = 1.0 / log_rate`; vòng lặp `while True` gửi rồi `time.sleep(interval)`.
- Lỗi gửi bị bắt bằng `except` trần và chỉ in thông báo.

## Phạm vi bài tập

Xây CLI `logsim`:

- Đọc cấu hình YAML có kiểm tra.
- Sinh `count` sự kiện (không vô hạn).
- Ghi NDJSON vào file đích.
- Hỗ trợ `--seed`, `--start-time`, `--rate` ghi đè cấu hình.
- Dừng sạch khi `Ctrl+C`, đảm bảo mọi dòng đã ghi là JSON hợp lệ.

Không nằm trong phạm vi: Kafka, K8s manifest, Spark, gửi mạng, xoay vòng file, nén.

## Liên kết

- [SPEC.md](SPEC.md) — lược đồ sự kiện, kiểm tra cấu hình, lịch, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế generator, sink, kiểm thử tất định.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập sửa lỗi chính tả `purcharse` thành `purchase`, thay sink Kafka bằng file, thêm seed/mốc thời gian để tất định, và thay vòng lặp vô hạn bằng `count`. Đây là thiết kế của bài tập; không tuyên bố nguồn có các hành vi đó.
