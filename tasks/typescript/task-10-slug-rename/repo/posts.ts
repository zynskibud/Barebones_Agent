/**
 * Blog posts.
 *
 * A post has a title and a body.
 */

import { mkSlug } from "./slugs.ts";

export type Post = {
  title: string;
  body: string;
};

export const BASE_URL = "https://example.com/posts";

/** Return the public URL of a post. */
export function postUrl(post: Post): string {
  return `${BASE_URL}/${mkSlug(post.title)}`;
}

/** Return the post whose title gives this slug, or null. */
export function findPost(posts: Post[], slug: string): Post | null {
  for (const post of posts) {
    if (mkSlug(post.title) === slug) {
      return post;
    }
  }
  return null;
}

/** Return the first `length` characters of the body. */
export function postSummary(post: Post, length = 40): string {
  const body = post.body;
  if (body.length <= length) {
    return body;
  }
  return body.slice(0, length) + "...";
}
