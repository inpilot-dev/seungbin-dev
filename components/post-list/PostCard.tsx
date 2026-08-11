import Link from "next/link";
import type { Post } from "@/types/content";
import { coverSrc } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// 카드 전체 클릭 가능 + 태그는 별도 링크. 중첩 <a> 금지 → 본문 링크는 절대위치 오버레이,
// 태그는 z-10 으로 그 위에 떠서 독립 동작.
export function PostCard({ post }: { post: Post }) {
  return (
    <Card className="group relative flex flex-col overflow-hidden p-0 transition-shadow hover:shadow-md">
      {/* 커버. 로드 전/실패 시 기존 그라데이션이 그대로 배경으로 남는다 */}
      <div className="aspect-[16/9] w-full bg-gradient-to-br from-[#e9edf1] to-[#f3f0ea] dark:from-[#1c1c1e] dark:to-[#161617]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={coverSrc(post)}
          alt=""
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
        />
      </div>
      <div className="flex flex-1 flex-col gap-2.5 p-5">
        {post.tags.length > 0 && (
          <div className="relative z-10 flex flex-wrap gap-1.5">
            {post.tags.slice(0, 3).map((t) => (
              <Link key={t} href={`/posts?tags=${encodeURIComponent(t)}`}>
                <Badge
                  variant="secondary"
                  className="bg-[var(--tag-bg)] font-semibold text-brand-tag hover:bg-[var(--tag-bg)]/80"
                >
                  {t}
                </Badge>
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
