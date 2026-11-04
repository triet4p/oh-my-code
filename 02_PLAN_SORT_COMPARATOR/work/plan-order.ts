export type Status = "planned" | "researching" | "on-hold" | "done";
export type Priority = "high" | "medium" | "low";

export interface Plan {
    id: string;
    status: Status;
    priority: Priority;
    updatedAt: Date | null;
}

export interface ValidationIssue {
    path: string;       // ví dụ "plans[2].updatedAt"
    code: string;       // "invalid-status" | "invalid-date" | ...
    message: string;
}

const STATUS_RANK: Record<Status, number> = { planned: 1, researching: 2, "on-hold": 3, done: 4 };
const PRIORITY_RANK: Record<Priority, number> = { high: 1, medium: 2, low: 3 };

const STATUSES: readonly Status[] = ["planned", "researching", "on-hold", "done"];
const PRIORITIES: readonly Priority[] = ["high", "medium", "low"];

function timeOf(plan: Plan): number {
    return plan.updatedAt?.getTime() ?? -Infinity;
}

export function comparePlans(a: Plan, b: Plan): number {
    if (STATUS_RANK[a.status] !== STATUS_RANK[b.status]) {
        return STATUS_RANK[a.status] - STATUS_RANK[b.status];
    }
    if (PRIORITY_RANK[a.priority] !== PRIORITY_RANK[b.priority]) {
        return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
    }
    const ta = timeOf(a);
    const tb = timeOf(b);
    if (ta !== tb) {
        return ta < tb ? 1 : -1; // newer first; never NaN, even when both are -Infinity
    }
    if (a.id < b.id) return -1;
    if (a.id > b.id) return 1;
    return 0;
}

function isPlanObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function validatePlans(input: unknown): ValidationIssue[] {
    if (!Array.isArray(input)) {
        return [{ path: "$", code: "not-an-array", message: "Plans must be an array." }];
    }

    const issues: ValidationIssue[] = [];
    const seenIds = new Set<string>();

    input.forEach((value, i) => {
        const path = `plans[${i}]`;
        if (!isPlanObject(value)) {
            issues.push({ path, code: "not-an-object", message: "Each plan must be an object." });
            return;
        }

        const id = value["id"];
        if (typeof id !== "string" || id === "") {
            issues.push({ path: `${path}.id`, code: "invalid-id", message: "id must be a non-empty string." });
        } else if (seenIds.has(id)) {
            issues.push({ path: `${path}.id`, code: "duplicate-id", message: `duplicate id "${id}".` });
        } else {
            seenIds.add(id);
        }

        const status = value["status"];
        if (!STATUSES.includes(status as Status)) {
            issues.push({
                path: `${path}.status`,
                code: "invalid-status",
                message: `status must be one of: ${STATUSES.join(", ")}.`,
            });
        }

        const priority = value["priority"];
        if (!PRIORITIES.includes(priority as Priority)) {
            issues.push({
                path: `${path}.priority`,
                code: "invalid-priority",
                message: `priority must be one of: ${PRIORITIES.join(", ")}.`,
            });
        }

        const updatedAt = value["updatedAt"];
        if (updatedAt !== null && (!(updatedAt instanceof Date) || !Number.isFinite(updatedAt.getTime()))) {
            issues.push({
                path: `${path}.updatedAt`,
                code: "invalid-date",
                message: "updatedAt must be a valid Date or null.",
            });
        }
    });

    return issues.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
}

export function sortPlans(plans: readonly Plan[]): Plan[] {
    return [...plans].sort(comparePlans);
}

