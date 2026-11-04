# GUIDE 44 — Coordinator có ngân sách analyst

## 1. Bài toán thật sự là gì

Không phải "tìm phương án phân bổ tốt". Bài toán là: **một vòng lặp có ngân sách, luôn dừng, luôn báo cáo trung thực, và không để lại rác**.

Ba câu hỏi thiết kế phải trả lời trước khi viết code:

1. Ngân sách đếm cái gì? (số lượt gọi analyst, số lần sửa, hay cả hai?)
2. Kiểm tra khả thi có tác dụng phụ không? (nếu có, phải trên bản sao).
3. Khi hết ngân sách thì trả gì? (`bounded_stop` + `decision = null`, không ném lỗi).

## 2. Thiết kế

### 2.1 Ba lớp tách biệt

```text
Analyst  ──►  Coordinator  ──►  ActionExecutor
(sinh kế hoạch)   (đếm, lặp)        (kiểm tra trên bản sao)
```

- `Analyst` không biết gì về ngân sách.
- `ActionExecutor` không biết gì về vòng lặp.
- `Coordinator` không biết gì về cấu trúc thế giới ngoài `execute`.

Nếu `Coordinator` bắt đầu kiểm tra `capacity` trực tiếp, bạn đã trộn hai tầng và test cô lập sẽ không còn ý nghĩa.

### 2.2 Dữ liệu

- `World`: `resources: dict[str, Resource]`, `assignments: list[Assignment]`. Cả hai phải **thuần dữ liệu** để `deepcopy` đúng.
- `Feasibility(ok: bool, reasons: list[str], world_after: World)`.
- `CoordinationResult` với đúng 9 trường. Từ chối trường lạ ngay tại constructor.

## 3. Thứ tự cài đặt

### Bước 1 — `ActionExecutor.execute` và bốn lý do

Viết hàm này trước, test riêng, vì mọi thứ khác dựa vào nó.

Thứ tự kiểm tra nên cố định để `reasons` ổn định:

1. `unknown_request` — id không có trong `requests`.
2. `missing_request` — mọi id của `requests` không có trong plan.
3. `amount_mismatch`.
4. `capacity_exceeded`.

Dùng **cùng một** thứ tự trong mọi lần chạy; nếu bạn lặp dict không sắp xếp, `reasons` sẽ đổi thứ tự và snapshot test sẽ flaky. Sắp theo `request.id`.

### Bước 2 — Bản sao sâu

`execute(deepcopy(world), plan)` — nhưng cẩn thận: `deepcopy` phải nằm **trong** `Coordinator`, không phải trong `execute`, để `execute` vẫn dùng được cho thực thi thật nếu sau này cần. Ghi rõ hợp đồng: "execute giả định nó nhận quyền sở hữu thế giới".

Một lỗi tinh vi: nếu `World` chứa tham chiếu tới object bên ngoài (ví dụ một list được chia sẻ giữa hai fixture), `deepcopy` vẫn tách đúng — nhưng nếu bạn tự viết "copy nông" để nhanh, test cô lập sẽ đỏ.

### Bước 3 — Đếm trước khi gọi

```text
while analyst_calls < MAX_ANALYST_CALLS:
    plan = analyst.propose(...)
    analyst_calls += 1
    ...
```

Đặt `while` theo ngân sách gọi, và kiểm tra ngân sách sửa ở nhánh thất bại. Điều này khiến hai ngân sách độc lập và dễ test.

### Bước 4 — Trace

Mỗi sự kiện là một dòng, `step` tăng từ 0. Đừng gộp "propose + feasibility" vào một dòng: khi debug, bạn cần biết đề xuất nào ứng với lý do nào.

`detail` cho `propose` nên rỗng (`""`) thay vì chứa toàn bộ plan — plan đã có trong `recommendations`, chép lại làm trace phình và dễ lệch.

### Bước 5 — Kết quả

`decision` chỉ được gán ở nhánh `ok`. Ở mọi nhánh khác, giữ `None`. Test bất biến `decision is not None iff outcome == "decided"`.

`recommendations` chứa **mọi** đề xuất đã thử, kể cả `null` (abstain) và đề xuất sai. Đừng lọc — mục đích là tái dựng lịch sử.

## 4. Cạm bẫy

- **Gọi rồi mới kiểm tra ngân sách**: vượt một lượt. Test bằng script dài và đếm số lần `propose` thực sự được gọi (dùng analyst bọc đếm).
- **`deepcopy` một lần rồi tái sử dụng**: nếu `execute` sửa bản sao, lần sau bạn kiểm tra trên thế giới đã bị trừ. Luôn copy mới mỗi lượt.
- **Danh sách `reasons` không ổn định**: sắp theo id.
- **Cho analyst giữ tham chiếu `world_view`**: nếu analyst lưu lại rồi sửa, thế giới gốc có thể bị ảnh hưởng ở lần sau. Truyền bản sao sâu và ghi rõ "read-only".
- **Ném lỗi khi hết ngân sách**: sai. `bounded_stop` là kết quả.
- **Cho fixture nới ngân sách**: nếu bạn đọc `max_calls` từ fixture, người dùng có thể đặt 10^9. Hằng phải ở module.
- **`extra="forbid"` chỉ ở phía serialize**: phải từ chối cả khi dựng từ dict trong test, nếu không bạn không mô phỏng đúng hợp đồng.

## 5. Kiểm thử

| Test | Khẳng định |
|---|---|
| 7.1 | trace 6 dòng đúng thứ tự, `decided`, calls 2, revisions 1 |
| 7.2 | `bounded_stop`, calls 3, revisions 2, `decision is None` |
| 7.5 | `bounded_stop`, calls 6, revisions 0, 7 dòng trace |
| Cô lập | `json.dumps(world, sort_keys=True)` trước == sau, cho cả nhánh lỗi |
| Ngân sách | Analyst đếm số lần được gọi; không vượt 6 |
| Seed/ngày | Lệch ⇒ ngoại lệ và analyst **không** được gọi (đếm = 0) |
| Kết quả | Dựng từ dict có khóa lạ ⇒ `ExtraFieldForbidden` |
| Song song | `threading.active_count()` trước == sau |
| Tất định | Hai lần chạy cho cùng `json.dumps(result)` |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src fixtures/infeasible_then_feasible.json | python -m json.tool
python -m src fixtures/always_infeasible.json | python -m json.tool
```

Đối chiếu `outcome`, `analyst_calls`, `revision_count` với mục 7 của SPEC. Kiểm tra cô lập bằng một lệnh:

```bash
python -c "import json,subprocess,copy; f=json.load(open('fixtures/always_infeasible.json')); b=copy.deepcopy(f['world']); subprocess.run(['python','-m','src','fixtures/always_infeasible.json'],capture_output=True); print(f['world']==b)"
```

Lưu ý: lệnh trên chỉ chứng minh tiến trình con không ghi ra file; để chứng minh trong cùng tiến trình, hãy viết test gọi trực tiếp `coordinate`.

## 7. Gợi ý

- Viết `CountingAnalyst` bọc một analyst khác, chỉ để test ngân sách — rẻ và chính xác hơn suy luận từ trace.
- Viết `assert_result_invariants(r)` gồm 4 dòng: `outcome` hợp lệ, `calls <= 6`, `revisions <= 2`, `decision` khớp `outcome`. Gọi nó ở cuối mọi test.
- Nếu `trace` quá dài, đừng cắt — thay vào đó giảm kích thước fixture.
- Với `extra="forbid"`, dùng `dataclasses` + một hàm `from_dict` kiểm tra tập khóa; không cần Pydantic cho bài này.

## 8. Mở rộng

- **Phục vụ một phần**: cho phép `plan[id] <= amount` và thêm reason `under_served`; khi đó bài toán gần với tối ưu hơn nhưng vẫn không cần solver.
- **Nhiều loại ràng buộc**: thêm ràng buộc thời gian (mỗi tài nguyên chỉ làm một việc mỗi bước) — executor phải phát hiện xung đột.
- **Ngân sách theo chi phí**: thay số lượt bằng "token/chi phí"; analyst trả kèm chi phí ước tính, coordinator cộng dồn và dừng khi vượt.
- **Trace có cấu trúc**: đưa `plan_hash` vào mỗi dòng để nhóm các lần lặp giống nhau.
- **So sánh**: chạy cùng fixture với `MAX_REVISIONS = 0` và `= 2`; thấy rõ trade-off giữa chi phí và tỉ lệ `decided`.
