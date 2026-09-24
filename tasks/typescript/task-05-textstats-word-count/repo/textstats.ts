/** Simple statistics for a block of text. */

export type Summary = {
  chars: number;
  lines: number;
};

/** Return the number of characters, spaces included. */
export function charCount(text: string): number {
  return text.length;
}

/** Return the number of lines that hold some text. */
export function lineCount(text: string): number {
  return text.split("\n").filter((line) => line.trim() !== "").length;
}

/** Return the longest line. Return an empty string if there is none. */
export function longestLine(text: string): string {
  let longest = "";
  for (const line of text.split("\n")) {
    if (line.length > longest.length) {
      longest = line;
    }
  }
  return longest;
}

/** Return the most common non-space character, or null. */
export function mostCommonChar(text: string): string | null {
  const counts = new Map<string, number>();
  for (const char of text) {
    if (/\s/.test(char)) {
      continue;
    }
    counts.set(char, (counts.get(char) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [char, count] of counts) {
    if (count > bestCount) {
      best = char;
      bestCount = count;
    }
  }
  return best;
}

/** Return the main counts in one object. */
export function summary(text: string): Summary {
  return {
    chars: charCount(text),
    lines: lineCount(text),
  };
}
