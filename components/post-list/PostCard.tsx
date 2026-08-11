import Link from "next/link";
import type { Post } from "@/types/content";
import { Card } from "@/components/ui/card";
import { Cover } from "./Cover";

// 카드 전체 클릭 가능 + 태그는 별도 링크. 중첩 <a> 금지 → 본문 링크는 절대위치 오버레이,
// 태그는 z-10 으로 그 위에 떠서 독립 동작.
export function PostCard({ post }: { post: Post }) {
  return (
    <Card className="group relative flex flex-col overflow-hidden p-0 transition-shadow hover:shadow-md">
      <Cover post={post} className="aspect-[16/9] w-full" />
      <div className="flex flex-1 flex-col gap-2.5 p-5">
        {post.tags.length > 0 && (
          <div className="relative z-10 flex flex-wrap gap-x-2 gap-y-1">
            {post.tags.slice(0, 3).map((t) => (
              <Link
                key={t}
                href={`/posts?tags=${encodeURIComponent(t)}`}
                className="text-xs font-medium text-brand-tag hover:underline"
              >
                #{t}
              </Link>
            ))}
          </div>
        )}
        <h3 className="text-lg font-semibold leading-snug">{post.title}</h3>
        <p className="line-clamp-2 flex-1 text-sm text-muted-foreground">
          {post.description}
        </p>
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{post.date}</span>
          <span aria-hidden>·</span>
          <span>{post.readingTime}</span>
        </div>
      </div>
      <Link
        href={`/posts/${post.slug}`}
        className="absolute inset-0 rounded-[inherit] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        aria-label={post.title}
      />
    </Card>
  );
}
