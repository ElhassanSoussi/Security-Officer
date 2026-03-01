import test from "node:test";
import assert from "node:assert/strict";

import { formatConfidencePercent, normalizeConfidenceScore } from "../lib/confidence.ts";

test("normalizeConfidenceScore: returns null for empty/invalid values", () => {
    assert.equal(normalizeConfidenceScore(undefined), null);
    assert.equal(normalizeConfidenceScore(null), null);
    assert.equal(normalizeConfidenceScore(""), null);
    assert.equal(normalizeConfidenceScore("   "), null);
    assert.equal(normalizeConfidenceScore("HIGH"), null);
    assert.equal(normalizeConfidenceScore(Number.NaN), null);
});

test("normalizeConfidenceScore: accepts 0..1 ratios", () => {
    assert.equal(normalizeConfidenceScore(0), 0);
    assert.equal(normalizeConfidenceScore(1), 1);
    assert.equal(normalizeConfidenceScore(0.85), 0.85);
    assert.equal(normalizeConfidenceScore("0.5"), 0.5);
});

test("normalizeConfidenceScore: accepts 0..100 percent", () => {
    assert.equal(normalizeConfidenceScore(50), 0.5);
    assert.equal(normalizeConfidenceScore(100), 1);
    assert.equal(normalizeConfidenceScore("85"), 0.85);
});

test("normalizeConfidenceScore: returns null for out-of-range numbers", () => {
    assert.equal(normalizeConfidenceScore(-0.1), null);
    assert.equal(normalizeConfidenceScore(-5), null);
    assert.equal(normalizeConfidenceScore(101), null);
    assert.equal(normalizeConfidenceScore(1000), null);
});

test("formatConfidencePercent: formats to percent or dash", () => {
    assert.equal(formatConfidencePercent(undefined), "—");
    assert.equal(formatConfidencePercent(null), "—");
    assert.equal(formatConfidencePercent("HIGH"), "—");
    assert.equal(formatConfidencePercent(0.85), "85%");
    assert.equal(formatConfidencePercent(85), "85%");
    assert.equal(formatConfidencePercent("0.1"), "10%");
});
