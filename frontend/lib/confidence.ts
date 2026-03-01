export function normalizeConfidenceScore(value: unknown): number | null {
    // Normalize confidence to a 0..1 ratio.
    // Accepts:
    // - 0..1 (ratio)
    // - 0..100 (percent)
    // - numeric strings ("0.85", "85")
    if (value === null || value === undefined) return null;

    let num: number | null = null;

    if (typeof value === "number") {
        num = value;
    } else if (typeof value === "string") {
        const trimmed = value.trim();
        if (!trimmed) return null;
        const parsed = Number(trimmed);
        if (!Number.isFinite(parsed)) return null;
        num = parsed;
    } else {
        return null;
    }

    if (!Number.isFinite(num) || Number.isNaN(num)) return null;
    if (num < 0) return null;

    // If the value looks like a ratio, keep it; if it looks like percent, convert.
    if (num <= 1) return num;
    if (num <= 100) return num / 100;
    return null;
}

export function formatConfidencePercent(value: unknown): string {
    const ratio = normalizeConfidenceScore(value);
    if (ratio === null) return "—";
    return `${Math.round(ratio * 100)}%`;
}

