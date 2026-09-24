import { test } from "node:test";
import assert from "node:assert/strict";
import { charCount, lineCount, longestLine, mostCommonChar, summary } from "../textstats.ts";

const TEXT = "one two\n\nthree four five\n";

test("charCount", () => {
  assert.equal(charCount("abc"), 3);
  assert.equal(charCount(""), 0);
});

test("lineCount ignores blank lines", () => {
  assert.equal(lineCount(TEXT), 2);
});

test("longestLine", () => {
  assert.equal(longestLine(TEXT), "three four five");
  assert.equal(longestLine(""), "");
});

test("mostCommonChar", () => {
  assert.equal(mostCommonChar("aab b"), "a");
  assert.equal(mostCommonChar("   "), null);
});

test("summary", () => {
  assert.deepEqual(summary(TEXT), { chars: 25, lines: 2 });
});
