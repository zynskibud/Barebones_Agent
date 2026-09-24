/**
 * Parse simple settings text.
 *
 * Each setting is one line in the form `key = value`.
 * Blank lines and lines that start with # are skipped.
 */

export type Settings = Record<string, string>;

const TRUE_WORDS = ["true", "yes", "on", "1"];

/** Return an object with one entry for each setting line. */
export function parseSettings(text: string): Settings {
  const settings: Settings = {};
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (line === "" || line.startsWith("#")) {
      continue;
    }
    const index = line.indexOf(" = ");
    const key = line.slice(0, index);
    const value = line.slice(index + 3);
    settings[key] = value;
  }
  return settings;
}

/** Return the setting as an integer, or `fallback` if it is missing. */
export function getInt(settings: Settings, key: string, fallback = 0): number {
  if (!Object.hasOwn(settings, key)) {
    return fallback;
  }
  return Number.parseInt(settings[key], 10);
}

/** Return true for true, yes, on, or 1. Return `fallback` if it is missing. */
export function getBool(settings: Settings, key: string, fallback = false): boolean {
  if (!Object.hasOwn(settings, key)) {
    return fallback;
  }
  return TRUE_WORDS.includes(settings[key].toLowerCase());
}

/** Return the settings as text, one `key = value` line each. */
export function formatSettings(settings: Settings): string {
  const lines = Object.entries(settings).map(([key, value]) => `${key} = ${value}`);
  return lines.join("\n");
}
