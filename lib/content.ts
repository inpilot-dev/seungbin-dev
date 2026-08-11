import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import type { Post, Tag } from "@/types/content";

const CONTENT_DIR = path.join(process.cwd(), "content");

function readingTimeOf(text: string): string {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const mins = Math.max(1, Math.round(words / 200));
  return `${mins} min read`;
}

function parseFile(slug: string): { post: Post; content: string } {
  const raw = fs.readFileSync(path.join(CONTENT_DIR, `${slug}.mdx`), "utf8");
  const { data, content } = matter(raw);
  const post: Post = {
    slug,
    title: typeof data.title === "string" ? data.title : slug,
    description: typeof data.description === "string" ? data.description : "",
    date: data.date ? String(data.date).slice(0, 10) : "",
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    category: typeof data.category === "string" ? data.category : undefined,
    coverImage: typeof data.coverImage === "string" ? data.coverImage : undefined,
    coverCredit: typeof data.coverCredit === "string" ? data.coverCredit : undefined,
    readingTime: readingTimeOf(content),
  };
  return { post, content };
}

export function getAllPosts(): Post[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs
    .readdirSync(CONTENT_DIR)
    .filter((f) => f.endsWith(".mdx"))
    .map((f) => parseFile(f.replace(/\.mdx$/, "")).post)
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

export function getPostBySlug(slug: string): { post: Post; content: string } | null {
  try {
    return parseFile(slug);
  } catch {
    return null;
  }
}

export function getAllTags(): Tag[] {
  const counts = new Map<string, number>();
  for (const post of getAllPosts()) {
    for (const tag of post.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}
