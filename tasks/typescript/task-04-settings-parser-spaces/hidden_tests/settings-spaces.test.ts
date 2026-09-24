import { test } from "node:test";
import assert from "node:assert/strict";
import { getBool, getInt, parseSettings } from "../settings.ts";

test("one space each side still works", () => {
  assert.deepEqual(parseSettings("port = 8080"), { port: "8080" });
});

test("extra spaces are removed", () => {
  assert.deepEqual(parseSettings("port   =   8080"), { port: "8080" });
});

test("no spaces works", () => {
  assert.deepEqual(parseSettings("port=8080"), { port: "8080" });
});

test("spaces on one side only", () => {
  assert.deepEqual(parseSettings("host =localhost"), { host: "localhost" });
  assert.deepEqual(parseSettings("host= localhost"), { host: "localhost" });
});

test("inner spaces in the value are kept", () => {
  assert.deepEqual(parseSettings("name  =  my app"), { name: "my app" });
});

test("only the first equals sign splits", () => {
  assert.deepEqual(parseSettings("url = http://x.test/?a=b"), { url: "http://x.test/?a=b" });
});

test("mixed file", () => {
  const text = "# settings\nhost=localhost\nport   =   8080\n\ndebug = yes\n";
  assert.deepEqual(parseSettings(text), {
    host: "localhost",
    port: "8080",
    debug: "yes",
  });
});

test("comments and blank lines are still skipped", () => {
  assert.deepEqual(parseSettings("\n# a comment\n\n"), {});
});

test("getInt after extra spaces", () => {
  assert.equal(getInt(parseSettings("port   =   8080"), "port"), 8080);
});

test("getBool after no spaces", () => {
  assert.equal(getBool(parseSettings("debug=true"), "debug"), true);
});
