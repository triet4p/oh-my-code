# SPEC 48 — Pipeline toán tử tiến hoá gọi mô hình

## 1. Mô hình bài toán

### 1.1 Cá thể và fitness

```json
{
  "genome_len": 3,
  "target": [1, 2, 3],
  "population": [
    {"id": "i0", "genes": [1, 2, 0]},
    {"id": "i1", "genes": [0, 0, 3]}
  ]
}
```

`fitness(genes) = -Σ |genes[j] - target[j]|` (số nguyên, **cao hơn tốt hơn**, `0` là hoàn hảo). Fitness luôn được tính lại từ `genes`; không bao giờ tin giá trị mô hình trả về.

### 1.2 Provider

```text
class ModelProvider:
    def get_response(self, prompt: str) -> str
```

Hai cài đặt:

- `ScriptedProvider(responses: list[str])` — trả lần lượt; hết danh sách ⇒ `ProviderExhausted`.
- `EchoProvider(text: str)` — luôn trả cùng một chuỗi (dùng để test nhánh sửa lỗi vô vọng).

Mỗi lời gọi được ghi: `prompt_sha256` (hex đầy đủ), độ dài prompt, và thứ tự.

## 2. Template method

```text
class LLMBaseOperator:
    def __call__(self, state) -> OperatorResult:
        prompt = self._build_prompt(state)
        config = self._build_config()                 # metadata, không gửi đi
        raw = provider.get_response(prompt)           # calls += 1
        obj, repairs = parse_with_repair(raw, prompt, schema)
        self._validate(obj)
        value = self._process_json_response(obj, state)
        return OperatorResult(...)
```

### 2.1 `parse_with_repair`

```text
lần 1: thử json.loads(raw)
    nếu lỗi:
        gửi lại provider với prompt = prompt + "\n\nLỖI: <thông điệp>. Chỉ trả JSON hợp lệ."
        lần 2: thử json.loads(lần 2)
        nếu vẫn lỗi: raise OperatorRejected(reason="invalid_json", attempts=2, last_error=...)
        repairs = 1
```

- Chỉ **một** lần sửa. Không vòng lặp vô hạn.
- `OperatorRejected` mang `attempts` và `last_error` (chuỗi đã cắt tối đa 200 ký tự).
- JSON hợp lệ nhưng sai lược đồ **không** được sửa: đó là `SchemaViolation`, không phải lỗi cú pháp. Ghi rõ lựa chọn này.

### 2.2 Xác thực chung

Mọi phản hồi là object JSON. Kiểm tra theo thứ tự:

1. Không phải object ⇒ `WrongType(expected="object")`.
2. Khóa lạ ⇒ `UnknownField(key)`.
3. Thiếu khóa bắt buộc ⇒ `MissingField(key)`.
4. Sai kiểu ⇒ `WrongType(field, expected)`.
5. Vi phạm miền giá trị ⇒ lỗi riêng của từng toán tử (mục 3).

## 3. Năm toán tử

| Toán tử | Prompt chứa | Lược đồ phản hồi | Kiểm tra miền |
|---|---|---|---|
| `init` | `target`, `genome_len` | `{"genes": [int,…]}` | độ dài `= genome_len`; mỗi gen là số nguyên |
| `crossover` | `parent_a.genes`, `parent_b.genes` | `{"genes": [int,…]}` | độ dài đúng; **mỗi vị trí phải lấy alen từ p1 hoặc p2** (`AlleleNotInherited(pos)`) |
| `mutation` | `parent.genes` | `{"genes": […], "mutated_positions": [int,…]}` | `mutated_positions` tăng ngặt, trong `[0, genome_len)`; tập vị trí khác parent **đúng bằng** tập này (`MutationMismatch`) |
| `self_evo` | `genes`, `reflection` | `{"genes": […], "improved": bool}` | `improved` phải bằng `fitness(new) > fitness(old)` (`InconsistentClaim`) |
| `collective_ref` | `genes`, `population_ids` | `{"genes": […], "cited_ids": [str,…]}` | `cited_ids` không rỗng, là tập con của `population_ids` (`UnknownCitation`) |

`MutationMismatch` so sánh **tập** vị trí, không phải thứ tự; nhưng `mutated_positions` phải đã sắp tăng.

## 4. Chọn lọc

### 4.1 `random_select(population, k, seed)`

Chọn `k` cá thể **không hoàn lại**, tất định:

```text
pool = [0..n-1] đã sắp tăng
chọn lặp k lần:
    idx = floor(next_u() * len(pool))
    lấy pool[idx]; pool[idx] = pool[-1]; pool.pop()
```

`next_u()` là LCG 32-bit (`state = (1664525*state + 1013904223) mod 2^32`) trên `seed` của **lần gọi**, không dùng trạng thái toàn cục.

### 4.2 `top_k_elitism_replace(population, offspring, k)`

```text
hợp = population + offspring (loại trùng id, giữ bản xuất hiện trước)
sắp theo (-fitness, id) ; giữ k đầu tiên làm "elite"
phần còn lại = các cá thể của offspring chưa nằm trong elite, theo thứ tự offspring
kết quả = elite + phần còn lại, cắt còn len(population)
```

Hệ quả: kích thước quần thể không đổi; cá thể tốt nhất không bao giờ bị loại.

Ví dụ: `population = [i0(f=5), i1(f=3)]`, `offspring = [i2(f=7), i3(f=1)]`, `k = 2` ⇒ elite `[i2(7), i0(5)]`, còn lại `[i3]`, cắt còn 2 ⇒ `[i2(7), i0(5)]`.

## 5. Vòng tiến hoá

Mỗi thế hệ, theo đúng thứ tự:

1. `random_select(pop, 2, seed + gen)` ⇒ `(p1, p2)`
2. `crossover(p1, p2)` ⇒ `child`
3. `mutation(child)` ⇒ `child`
4. `self_evo(child)` ⇒ `child`
5. `collective_ref(child)` ⇒ `child`
6. `top_k_elitism_replace(pop, [child], k=2)`

Nếu một toán tử ném `OperatorRejected`/`SchemaViolation`, ghi vào log với `ok: false`, **giữ nguyên quần thể**, sang thế hệ kế. Không dừng cả tiến trình vì một phản hồi hỏng.

## 6. Đầu ra

```json
{
  "generations": [
    {
      "generation": 0,
      "operations": [
        {"calls": 1, "ok": true, "operator": "crossover", "prompt_sha256": "…", "repairs": 0}
      ],
      "population": [{"fitness": 7, "genes": [1, 2, 3], "id": "g0"}],
      "provider_calls": 5
    }
  ],
  "total_provider_calls": 25
}
```

- `prompt_sha256` là hex đầy đủ của prompt **cuối cùng** đã gửi (kể cả prompt sửa lỗi nếu có).
- `calls` của mỗi toán tử là 1 hoặc 2 (2 khi có sửa).
- `ok: false` kèm `"error": "<tên lỗi>"`.
- `population` đã sắp theo `(-fitness, id)`.
- Toàn bộ output in bằng `json.dumps(..., sort_keys=True, ensure_ascii=False)`.

## 7. Ví dụ cụ thể

### 7.1 Sửa JSON một lần

Script: `["không phải json", "{\"genes\": [1,2,3]}"]`, toán tử `init`:

- Lần 1 lỗi cú pháp ⇒ gửi prompt sửa lỗi.
- Lần 2 hợp lệ ⇒ `ok: true`, `repairs: 1`, `calls: 2`.

### 7.2 Sửa thất bại

Script: `["hỏng", "vẫn hỏng"]`, toán tử `init`:

- `OperatorRejected(reason="invalid_json", attempts=2)`.
- Log: `ok: false`, `error: "OperatorRejected"`, `calls: 2`.
- Quần thể **không** đổi.

### 7.3 Vi phạm lược đồ

`{"genes": [1,2,3], "extra": 1}` ⇒ `UnknownField("extra")`. Không thử lại.
`{"genes": [1,2]}` với `genome_len = 3` ⇒ `LengthMismatch(expected=3, got=2)`.
`{"genes": "123"}` ⇒ `WrongType("genes", "list[int]")`.

### 7.4 Crossover không kế thừa

`p1 = [1,2,3]`, `p2 = [4,5,6]`, phản hồi `{"genes": [1,9,6]}` ⇒ `AlleleNotInherited(1)` vì `9` không có ở vị trí 1 của cả hai bố mẹ. Vị trí 0 (`1`) và 2 (`6`) hợp lệ.

### 7.5 Mutation khai báo sai

`parent = [1,2,3]`, phản hồi `{"genes": [1,9,3], "mutated_positions": [0]}` ⇒ `MutationMismatch(declared=[0], actual=[1])`.

### 7.6 Self-evolution tự mâu thuẫn

`old = [1,2,0]` (fitness `-1`), phản hồi `{"genes": [1,2,3], "improved": false}`. Fitness mới `0 > -1` ⇒ `InconsistentClaim(expected=true, got=false)`.

### 7.7 Elitism

Như mục 4.2: kết quả `[i2(f=7), i0(f=5)]`.

### 7.8 Gọi mạng bằng không

`python -m src run --fixture fixtures/script_cli.json` phải chạy với `socket` bị chặn (xem GUIDE §6); không có import `http`, `requests`, `httpx`, `urllib.request` trong mã nguồn.

## 8. Tiêu chí chấp nhận

1. Ví dụ 7.1–7.7 cho đúng hành vi và đúng tên lỗi.
2. `repairs` chỉ bằng `0` hoặc `1`; không bao giờ `2`.
3. JSON hợp lệ nhưng sai lược đồ **không** kích hoạt lần gửi thứ hai (`total calls` không tăng).
4. `top_k_elitism_replace` giữ cá thể tốt nhất và không đổi kích thước quần thể với 20 trường hợp sinh ngẫu nhiên.
5. `random_select` trả `k` chỉ số phân biệt, tất định với cùng seed; `k > n` ⇒ `InvalidSelection`.
6. Cùng fixture ⇒ output giống hệt từng byte.
7. `total_provider_calls` khớp tổng `calls` của mọi toán tử.
8. Không có tên miền mạng nào được gọi; test khẳng định `socket.socket` không được tạo.

## 9. Non-goals

- Không gọi mô hình thật; không API key; không tính chi phí token.
- Không song song; không cache; không streaming.
- Không tối ưu đa mục tiêu hay NSGA-II (bài 19 trong lộ trình).
- Không xử lý prompt injection; đây là ghi chú production, không phải phạm vi.
