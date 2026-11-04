# GUIDE 48 — Pipeline toán tử tiến hoá gọi mô hình

## 1. Vì sao thay provider thay vì gọi mô hình

Ba lý do thực dụng:

1. **Tất định**: cùng fixture cho cùng kết quả, nên test được.
2. **Rẻ**: không tốn token, không cần key.
3. **Kiểm soát được đầu vào**: bạn chủ động tạo phản hồi hỏng để thử nhánh sửa lỗi — điều gần như không làm được với mô hình thật.

Điều quan trọng: phần bạn học là **đường ống** (dựng prompt → gọi → parse → xác thực → xử lý), không phải chất lượng prompt. Đường ống này dùng lại được khi cắm mô hình thật.

## 2. Thiết kế

### 2.1 Cây kế thừa

```text
Operator (Protocol)
└── LLMBaseOperator (abstract)
    ├── InitOperator
    ├── CrossoverOperator
    ├── MutationOperator
    ├── SelfEvoOperator
    └── CollectiveRefOperator

Selection (thuần, không provider)
├── random_select
└── top_k_elitism_replace
```

`LLMBaseOperator` giữ ba thứ dùng chung: `provider`, `genome_len`, `schema`. Lớp con chỉ cài `_build_prompt` và `_process_json_response`.

### 2.2 `OperatorResult`

```text
operator: str
prompt_sha256: str
calls: int
repairs: int
ok: bool
value: Individual | None
error: str | None
```

Không đưa prompt/response thô vào kết quả. Nếu cần debug, ghi ra file riêng có cờ `--debug-prompts` và cảnh báo trong README.

## 3. Thứ tự cài đặt

### Bước 1 — Fitness và Individual

Viết `fitness(genes, target)` trước, thuần, không I/O. Test: `[1,2,3]` với target `[1,2,3]` ⇒ `0`; `[1,2,0]` ⇒ `-1`.

Lưu ý: **không** nhận fitness từ mô hình. Nếu ai đó trả `{"fitness": 999}`, đó là `UnknownField`.

### Bước 2 — Provider và ghi nhận

`ScriptedProvider` giữ `list[str]` và một con trỏ. Ghi mỗi lời gọi vào `calls_log` gồm `prompt_sha256`, `prompt_len`, `seq`.

`prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()` — hex đầy đủ; nếu bạn cắt 12 ký tự để hiển thị, giữ bản đầy đủ để so.

### Bước 3 — `parse_with_repair`

Đây là trái tim bài. Viết thành hàm thuần:

```text
parse_with_repair(raw, prompt, provider, schema) -> (obj, repairs, calls)
```

Nhánh lỗi phải phân biệt **ba** trường hợp:

| Trường hợp | Sửa? | Kết quả |
|---|---|---|
| Chuỗi không phải JSON | có, 1 lần | `repairs = 1` hoặc `OperatorRejected` |
| JSON không phải object | không | `WrongType` |
| Object sai lược đồ | không | lỗi cụ thể |

Thứ tự kiểm tra quan trọng: parse trước, rồi kiểu, rồi khóa lạ, rồi khóa thiếu, rồi miền giá trị. Nếu bạn kiểm tra "khóa lạ" trước khi biết đó là object, bạn sẽ crash khi gặp `[]`.

### Bước 4 — Năm schema

Viết một hàm `validate_common(obj, required, optional=())` rồi lớp con bổ sung luật riêng. Đừng viết lại vòng kiểm tra khóa năm lần.

`MutationMismatch` cần so **tập** khác biệt:

```text
actual = {j for j in range(n) if new[j] != old[j]}
declared = set(obj["mutated_positions"])
nếu actual != declared: lỗi
```

Nhớ kiểm tra `mutated_positions` đã sắp tăng **và** không trùng trước khi so tập; nếu không `[1,1]` sẽ lọt.

### Bước 5 — Chọn lọc

`random_select` dùng swap-remove trên `pool` đã sắp — cùng kỹ thuật như bài 41. Đừng dùng `random.sample` nếu bạn muốn LCG tất định xuyên ngôn ngữ (SPEC chọn LCG).

`top_k_elitism_replace`: dedupe theo `id` trước khi sắp, nếu không một cá thể có mặt ở cả hai danh sách sẽ chiếm hai chỗ.

### Bước 6 — Vòng tiến hoá

Mỗi thế hệ là một hàm `run_generation(pop, gen) -> (pop, log)`. Bao `try/except` quanh **từng** toán tử, không quanh cả thế hệ — nếu không, một lần hỏng làm mất các bước đã thành công.

## 4. Cạm bẫy

- **Sửa lỗi vô hạn**: `while True` quanh provider là lỗi chí mạng. Chỉ một lần.
- **Sửa cả lỗi lược đồ**: làm provider "học" cách trả lời sai hợp lệ; SPEC cấm.
- **Tin fitness từ mô hình**: mô hình có thể bịa; luôn tính lại.
- **`json.loads` với `NaN`**: Python chấp nhận `NaN` — nhưng JSON chuẩn không. Nếu muốn chặt, dùng `parse_constant` để từ chối.
- **Ghi log prompt thô**: rò dữ liệu. Chỉ băm.
- **`elitism` làm tăng quần thể**: nhớ cắt về kích thước ban đầu.
- **Trùng id trong offspring**: dedupe trước khi sắp.
- **Đếm `calls` sai**: mỗi `get_response` là một call, kể cả lần sửa. Test tổng khớp.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `fitness_sign` | hoàn hảo = 0; lệch 1 = -1 |
| `repair_once` | 7.1: `repairs=1`, `calls=2` |
| `repair_fails` | 7.2: `OperatorRejected`, quần thể không đổi |
| `schema_errors` | 7.3: ba lỗi, `calls` vẫn `1` |
| `allele` | 7.4: `AlleleNotInherited(1)` |
| `mutation_set` | 7.5: `MutationMismatch` |
| `self_evo_claim` | 7.6: `InconsistentClaim` |
| `elitism` | 7.7: đúng thứ tự |
| `selection_small` | `k > n` ⇒ `InvalidSelection` |
| `no_network` | chặn `socket.socket`, chạy cả pipeline |
| `determinism` | hai lần chạy, so byte |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src run --fixture fixtures/script_cli.json | python -m json.tool
python -m src run --fixture fixtures/script_bad_json.json | python -m json.tool
python -m src run --fixture fixtures/script_unknown_key.json; echo "exit=$?"
```

Chứng minh không có mạng:

```bash
python -c "import socket; socket.socket = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('network blocked')); import runpy; runpy.run_module('src', run_name='__main__')" --fixtures fixtures/script_cli.json
```

(Điều chỉnh đường dẫn module theo cấu trúc của bạn.) Nếu pipeline cố mở socket, bạn sẽ thấy `RuntimeError('network blocked')`.

## 7. Gợi ý

- Viết `validate_common` trước; năm lớp con chỉ thêm 2–3 dòng.
- Viết một `RecordingProvider` bọc provider khác để đếm call — hữu ích cho test hơn là đọc log.
- Nếu muốn thấy prompt, dùng `--debug-prompts` ghi ra `debug/` và nhớ xoá trước khi commit.
- Đừng cố "làm mượt" lỗi bằng cách trả cá thể cha khi toán tử hỏng; SPEC yêu cầu giữ nguyên quần thể và ghi `ok: false`. Trả cha là che lỗi.

## 8. Mở rộng

- **Provider có xác suất hỏng**: cấu hình `failure_rate` để chạy thử 1000 lần và đo tỉ lệ `ok`.
- **Cache theo băm prompt**: giảm số call; kiểm tra rằng cache không làm thay đổi kết quả.
- **Hai mô hình**: provider định tuyến theo toán tử (model A cho crossover, B cho mutation) — mô phỏng chọn model theo tác vụ.
- **Đa mục tiêu**: trả `fitness` dạng vector và dùng Pareto (bài 19 trong lộ trình).
- **Ghi log có cấu trúc**: JSONL mỗi lời gọi, kèm `prompt_sha256`, để phân tích sau.
