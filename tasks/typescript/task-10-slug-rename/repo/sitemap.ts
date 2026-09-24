/** Build a sitemap for a list of posts. */

import { writeFileSync } from "node:fs";
import * as slugs from "./slugs.ts";
import { BASE_URL } from "./posts.ts";
import type { Post } from "./posts.ts";

/** Return one URL per post, in post order. */
export function sitemapLines(posts: Post[]): string[] {
  const lines: string[] = [];
  for (const post of posts) {
    const slug = slugs.mkSlug(post.title);
    lines.push(`${BASE_URL}/${slug}`);
  }
  return lines;
}

/** Return the sitemap as text with one URL per line. */
export function sitemapText(posts: Post[]): string {
  return sitemapLines(posts).join("\n") + "\n";
}

/** Write the sitemap to a file. */
export function writeSitemap(posts: Post[], path: string): void {
  writeFileSync(path, sitemapText(posts), "utf8");
}
