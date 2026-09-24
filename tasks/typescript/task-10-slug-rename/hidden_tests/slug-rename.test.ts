import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as posts from "../posts.ts";
import * as sitemap from "../sitemap.ts";
import * as slugs from "../slugs.ts";
import { isSlug, makeSlug, uniqueSlugs } from "../slugs.ts";

const POSTS = [
  { title: "Hello, World!", body: "First post." },
  { title: "Python 3.12 Notes", body: "Second post." },
];

const SOURCE_FILES = ["slugs.ts", "posts.ts", "sitemap.ts"];

test("makeSlug", () => {
  assert.equal(makeSlug("Hello, World!"), "hello-world");
  assert.equal(makeSlug("  Two   Spaces "), "two-spaces");
  assert.equal(makeSlug("Python 3.12 Notes"), "python-3-12-notes");
});

test("isSlug still works", () => {
  assert.equal(isSlug("hello-world"), true);
  assert.equal(isSlug("Hello World"), false);
});

test("uniqueSlugs still works", () => {
  assert.deepEqual(uniqueSlugs(["A", "B", "a"]), ["a", "b", "a-2"]);
});

test("postUrl still works", () => {
  assert.equal(posts.postUrl(POSTS[0]), "https://example.com/posts/hello-world");
});

test("findPost still works", () => {
  assert.equal(posts.findPost(POSTS, "python-3-12-notes"), POSTS[1]);
  assert.equal(posts.findPost(POSTS, "missing"), null);
});

test("sitemap still works", () => {
  const expected =
    "https://example.com/posts/hello-world\n" +
    "https://example.com/posts/python-3-12-notes\n";
  assert.equal(sitemap.sitemapText(POSTS), expected);
});

test("old name is gone from the module", () => {
  assert.equal("mkSlug" in slugs, false);
});

test("old name is gone from every source file", () => {
  for (const file of SOURCE_FILES) {
    const source = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
    assert.equal(source.includes("mkSlug"), false, file);
  }
});
