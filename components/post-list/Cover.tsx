import type { Post } from "@/types/content";
import { cn } from "@/lib/utils";

// 커버. 사진이 지정된 글만 <img>, 나머지는 CSS 로 그린다.
// /api/og 를 쓰지 않는 이유: 래스터라 테마 토글을 못 따라가고(다크모드에서 흰 판),
// 카드 40장이 매번 엣지 함수를 부른다. OG 라우트는 소셜 공유 카드 전용으로 남긴다.
export function Cover({ post, className }: { post: Post; className?: string }) {
  return (
    <div
      className={cn(
        "flex items-end overflow-hidden bg-gradient-to-br from-[#e9edf1] to-[#f3f0ea] dark:from-[#1c1c1e] dark:to-[#161617]",
        className,
      )}
    >
      {post.coverImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={post.coverImage}
          alt=""
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover"
        />
      ) : (
        <span className="p-5 text-[28px] font-semibold tracking-tight text-black/15 dark:text-white/15">
          {post.category ?? "inpilot.dev"}
        </span>
      )}
    </div>
  );
}
