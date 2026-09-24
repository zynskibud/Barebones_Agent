import { test } from "node:test";
import assert from "node:assert/strict";
import { charCount, lineCount, wordCount } from "../textstats.ts";

test("two words", () => {
  assert.equal(wordCount("hello world"), 2);
});

test("one word", () => {
  assert.equal(wordCount("hello"), 1);
});

test("empty string has zero words", () => {
  assert.equal(wordCount(""), 0);
});

test("only whitespace has zero words", () => {
  assert.equal(wordCount("   \n\t "), 0);
});

test("extra spaces and newlines do not add words", () => {
  assert.equal(wordCount("  a  b\nc  "), 3);
});

test("tabs separate words", () => {
  assert.equal(wordCount("a\tb\tc"), 3);
});

test("punctuation stays inside a word", () => {
  assert.equal(wordCount("well, that is it."), 4);
});

test("other functions still work", () => {
  assert.equal(charCount("abc"), 3);
  assert.equal(lineCount("a\n\nb\n"), 2);
});
