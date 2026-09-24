import { test } from "node:test";
import assert from "node:assert/strict";
import { formatSettings, getBool, getInt, parseSettings } from "../settings.ts";

const TEXT = `# server settings
host = localhost
port = 8080

debug = yes
`;

test("parseSettings reads each line", () => {
  assert.deepEqual(parseSettings(TEXT), {
    host: "localhost",
    port: "8080",
    debug: "yes",
  });
});

test("parseSettings skips comments and blank lines", () => {
  assert.deepEqual(parseSettings("# only a comment\n\n"), {});
});

test("getInt", () => {
  const settings = parseSettings(TEXT);
  assert.equal(getInt(settings, "port"), 8080);
  assert.equal(getInt(settings, "workers", 4), 4);
});

test("getBool", () => {
  const settings = parseSettings(TEXT);
  assert.equal(getBool(settings, "debug"), true);
  assert.equal(getBool(settings, "verbose"), false);
});

test("formatSettings round trip", () => {
  const settings = { host: "localhost", port: "8080" };
  assert.deepEqual(parseSettings(formatSettings(settings)), settings);
});
