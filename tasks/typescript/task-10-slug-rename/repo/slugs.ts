/**
 * Turn titles into URL slugs.
 *
 * A slug is lowercase. It holds only letters, digits, and single hyphens.
 */

/** Return the slug for a title. */
export function mkSlug(title: string): string {
  const lowered = title.toLowerCase();
  const cleaned = lowered.replace(/[^a-z0-9]+/g, "-");
  return cleaned.replace(/^-+|-+$/g, "");
}

/** Return true if the text is already a valid slug. */
export function isSlug(text: string): boolean {
  return text !== "" && text === mkSlug(text);
}

/** Return one slug per title. Add -2, -3, and so on to repeats. */
export function uniqueSlugs(titles: string[]): string[] {
  const seen = new Map<string, number>();
  const result: string[] = [];
  for (const title of titles) {
    let slug = mkSlug(title);
    const count = (seen.get(slug) ?? 0) + 1;
    seen.set(slug, count);
    if (count > 1) {
      slug = `${slug}-${count}`;
    }
    result.push(slug);
  }
  return result;
}
