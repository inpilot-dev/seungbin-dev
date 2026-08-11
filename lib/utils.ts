import type { Post } from "@/types/content";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 커버 이미지: frontmatter 에 지정이 있으면 그걸, 없으면 동적 OG 이미지로 폴백.
// 40편 전부에 파일을 두지 않아도 카드/상세가 비지 않는다.
export function coverSrc(post: Post): string {
  if (post.coverImage) return post.coverImage;
  const q = new URLSearchParams({
    bare: "1",
    label: post.category ?? "inpilot.dev",
    tags: post.tags.slice(0, 4).join(","),
  });
  return `/api/og?${q}`;
}
