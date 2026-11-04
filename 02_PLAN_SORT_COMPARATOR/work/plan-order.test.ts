import { describe, expect, it } from "vitest";
import { comparePlans, sortPlans, validatePlans } from "./plan-order.js";
import type { Plan, ValidationIssue } from "./plan-order.js";

const at = (iso: string): Date => new Date(iso);

const sample: readonly Plan[] = [
    { id: "p1", status: "planned", priority: "high", updatedAt: at("2026-01-01T00:00:00Z") },
    { id: "p2", status: "planned", priority: "high", updatedAt: at("2026-02-01T00:00:00Z") },
    { id: "p3", status: "researching", priority: "low", updatedAt: at("2025-12-01T00:00:00Z") },
    { id: "p4", status: "done", priority: "high", updatedAt: at("2026-03-01T00:00:00Z") },
    { id: "p5", status: "planned", priority: "medium", updatedAt: at("2026-01-15T00:00:00Z") },
    { id: "p6", status: "planned", priority: "high", updatedAt: null },
];

const EXPECTED_ORDER = ["p2", "p1", "p6", "p5", "p3", "p4"];

const idsOf = (plans: readonly Plan[]): string[] => plans.map((plan) => plan.id);

const validPlan = (overrides: Partial<Plan> = {}): Plan => ({
    id: "p1",
    status: "planned",
    priority: "high",
    updatedAt: null,
    ...overrides,
});

const pathsOf = (issues: readonly ValidationIssue[]): string[] => issues.map((issue) => issue.path);

const codesOf = (issues: readonly ValidationIssue[]): string[] => issues.map((issue) => issue.code);

describe("sortPlans — thứ tự nhiều khóa", () => {
    it("sắp bảng ví dụ 6 phần tử đúng thứ tự p2, p1, p6, p5, p3, p4", () => {
        expect(idsOf(sortPlans(sample))).toEqual(EXPECTED_ORDER);
    });

    it("cho cùng kết quả khi đảo thứ tự đầu vào", () => {
        const reversed = [...sample].reverse();
        const rotated = [...sample.slice(3), ...sample.slice(0, 3)];

        expect(idsOf(sortPlans(reversed))).toEqual(EXPECTED_ORDER);
        expect(idsOf(sortPlans(rotated))).toEqual(EXPECTED_ORDER);
        expect(sortPlans(reversed)).toEqual(sortPlans(sample));
    });

    it("không sửa mảng đầu vào", () => {
        const input = [...sample];
        const before = [...input];

        const result = sortPlans(input);

        expect(result).not.toBe(input);
        expect(input).toEqual(before);
        expect(input.every((plan, i) => plan === before[i])).toBe(true);
    });

    it("trả mảng mới cho mảng rỗng và mảng một phần tử", () => {
        const empty: Plan[] = [];
        expect(sortPlans(empty)).toEqual([]);
        expect(sortPlans(empty)).not.toBe(empty);

        const single = [validPlan()];
        const sorted = sortPlans(single);
        expect(sorted).toEqual(single);
        expect(sorted).not.toBe(single);
        expect(sorted[0]).toBe(single[0]);
    });

    it("sắp theo id khi mọi khóa khác bằng nhau, kể cả updatedAt toàn null", () => {
        const plans: Plan[] = [
            validPlan({ id: "b" }),
            validPlan({ id: "c" }),
            validPlan({ id: "a" }),
        ];

        expect(idsOf(sortPlans(plans))).toEqual(["a", "b", "c"]);
    });

    it("coi hai Date cùng epoch là bằng nhau rồi chuyển sang id", () => {
        const plans: Plan[] = [
            validPlan({ id: "z", updatedAt: at("2026-01-01T07:00:00+07:00") }),
            validPlan({ id: "a", updatedAt: at("2026-01-01T00:00:00Z") }),
        ];

        expect(plans[0]!.updatedAt!.getTime()).toBe(plans[1]!.updatedAt!.getTime());
        expect(idsOf(sortPlans(plans))).toEqual(["a", "z"]);
    });

    it("so sánh id theo code unit, không theo locale", () => {
        const plans: Plan[] = [
            validPlan({ id: "a" }),
            validPlan({ id: "Z" }),
            validPlan({ id: "é" }),
            validPlan({ id: "z" }),
        ];

        // UTF-16: "Z"(90) < "a"(97) < "z"(122) < "é"(233)
        expect(idsOf(sortPlans(plans))).toEqual(["Z", "a", "z", "é"]);
    });
});

describe("comparePlans — comparator", () => {
    it("trả 0 khi so một phần tử với chính nó", () => {
        for (const plan of sample) {
            expect(comparePlans(plan, plan)).toBe(0);
        }
    });

    it("trả 0 chỉ khi id bằng nhau và mọi khóa bằng nhau", () => {
        const a = validPlan({ id: "q1" });
        const b = validPlan({ id: "q2" });
        const aCopy = validPlan({ id: "q1" });

        expect(comparePlans(a, aCopy)).toBe(0);
        expect(comparePlans(a, b)).not.toBe(0);
    });

    it("không bao giờ trả NaN trên mọi cặp, kể cả cặp null/null", () => {
        const cases: readonly Plan[] = [
            ...sample,
            validPlan({ id: "q1" }),
            validPlan({ id: "q2" }),
            validPlan({ id: "q3" }),
        ];

        for (const a of cases) {
            for (const b of cases) {
                const ab = comparePlans(a, b);
                expect(Number.isFinite(ab)).toBe(true);
                expect(Number.isFinite(comparePlans(b, a))).toBe(true);
                expect(Math.sign(ab) + Math.sign(comparePlans(b, a))).toBe(0);
            }
        }
    });

    it("là quan hệ thứ tự bắc cầu trên bộ dữ liệu mẫu", () => {
        for (const a of sample) {
            for (const b of sample) {
                for (const c of sample) {
                    if (comparePlans(a, b) <= 0 && comparePlans(b, c) <= 0) {
                        expect(comparePlans(a, c)).toBeLessThanOrEqual(0);
                    }
                }
            }
        }
    });

    it("đặt updatedAt null sau mọi giá trị thật trong cùng nhóm", () => {
        const dated = validPlan({ id: "dated", updatedAt: at("2000-01-01T00:00:00Z") });
        const undated = validPlan({ id: "undated", updatedAt: null });

        expect(comparePlans(dated, undated)).toBeLessThan(0);
        expect(comparePlans(undated, dated)).toBeGreaterThan(0);
    });
});

describe("validatePlans — kiểm tra dữ liệu", () => {
    it("trả mảng rỗng cho dữ liệu hợp lệ", () => {
        expect(validatePlans(sample)).toEqual([]);
    });

    it("chấp nhận readonly Plan[] và updatedAt null", () => {
        const plans = [validPlan({ updatedAt: null })] as const;

        expect(validatePlans(plans)).toEqual([]);
    });

    it("không ném lỗi với input không phải mảng hoặc phần tử lạ", () => {
        const inputs: unknown[] = [null, undefined, "plans", 42, {}, [null], [undefined], [[]], [[validPlan()]]];

        for (const input of inputs) {
            expect(() => validatePlans(input)).not.toThrow();
            expect(validatePlans(input).length).toBeGreaterThan(0);
        }
    });

    it.each<[string, unknown, string, string]>([
        ["không phải mảng", null, "$", "not-an-array"],
        ["phần tử không phải object", [42], "plans[0]", "not-an-object"],
        ["id rỗng", [validPlan({ id: "" })], "plans[0].id", "invalid-id"],
        ["id không phải string", [{ ...validPlan(), id: 7 }], "plans[0].id", "invalid-id"],
        ["status ngoài enum", [{ ...validPlan(), status: "archived" }], "plans[0].status", "invalid-status"],
        ["priority ngoài enum", [{ ...validPlan(), priority: "urgent" }], "plans[0].priority", "invalid-priority"],
        ["updatedAt không phải Date", [{ ...validPlan(), updatedAt: "2026-01-01" }], "plans[0].updatedAt", "invalid-date"],
        ["updatedAt là Date không hợp lệ", [validPlan({ updatedAt: new Date(NaN) })], "plans[0].updatedAt", "invalid-date"],
    ])("phát hiện %s", (_name, input, path, code) => {
        const issues = validatePlans(input);

        expect(issues).toContainEqual({ path, code, message: expect.any(String) });
    });

    it("phát hiện đủ các mã lỗi duy nhất trong bảng SPEC", () => {
        const collected = new Set<string>([
            ...codesOf(validatePlans(null)),
            ...codesOf(validatePlans([42])),
            ...codesOf(validatePlans([validPlan({ id: "" })])),
            ...codesOf(validatePlans([validPlan({ id: "x" }), validPlan({ id: "x" })])),
            ...codesOf(validatePlans([{ ...validPlan(), status: "archived" }])),
            ...codesOf(validatePlans([{ ...validPlan(), priority: "urgent" }])),
            ...codesOf(validatePlans([{ ...validPlan(), updatedAt: "2026-01-01" }])),
            ...codesOf(validatePlans([validPlan({ updatedAt: new Date(NaN) })])),
        ]);

        expect([...collected].sort()).toEqual([
            "duplicate-id",
            "invalid-date",
            "invalid-id",
            "invalid-priority",
            "invalid-status",
            "not-an-array",
            "not-an-object",
        ]);
    });

    it("báo duplicate-id tại lần xuất hiện thứ hai", () => {
        const plans = [validPlan({ id: "dup" }), validPlan({ id: "other" }), validPlan({ id: "dup" })];
        const issues = validatePlans(plans);

        expect(issues).toEqual([
            {
                path: "plans[2].id",
                code: "duplicate-id",
                message: expect.any(String),
            },
        ]);
    });

    it("coi updatedAt undefined là không hợp lệ, khác với null", () => {
        const missing = { id: "p1", status: "planned", priority: "high" };
        const explicitNull = { id: "p1", status: "planned", priority: "high", updatedAt: null };

        expect(codesOf(validatePlans([missing]))).toEqual(["invalid-date"]);
        expect(validatePlans([explicitNull])).toEqual([]);
    });

    it("sắp issue theo path", () => {
        const plans = [
            validPlan({ id: "" }),
            validPlan({ id: "a" }),
            { ...validPlan({ id: "a" }), status: "nope", priority: "nope", updatedAt: new Date(NaN) },
        ];

        const issues = validatePlans(plans);
        const paths = pathsOf(issues);

        expect(paths).toEqual([...paths].sort());
        expect(paths).toEqual([
            "plans[0].id",
            "plans[2].id",
            "plans[2].priority",
            "plans[2].status",
            "plans[2].updatedAt",
        ]);
    });
});
