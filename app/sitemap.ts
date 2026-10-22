import type { MetadataRoute } from "next";
import { getAllPosts } from "@/lib/content";
import { SITE } from "@/lib/metadata";

export default function sitemap(): MetadataRoute.Sitemap {
  const posts = getAllPosts().map((p) => {
    const last = p.updated ?? p.date;
    return {
      url: `${SITE.url}/posts/${p.slug}`,
      lastModified: last ? new Date(last) : new Date("2026-01-01"),
    };
  });
  // 홈·목록은 글이 바뀔 때 바뀐다 — 가장 최근 글 날짜를 따른다
  const latest = posts.map((p) => p.lastModified).sort((a, b) => b.getTime() - a.getTime())[0];

  return [
    { url: SITE.url, lastModified: latest },
    { url: `${SITE.url}/posts`, lastModified: latest },
    ...posts,
  ];
}
