import type { Post } from "@/types/content";
import { cn } from "@/lib/utils";

// 커버는 코드로 그린다. 이미지 파일도, 엣지 함수 호출도 없다.
// 1순위: 터미널 커버(coverCmd). 글에서 뽑은 실제 명령·출력이라 카드마다 내용이 달라
//        목록을 훑을 때 커버 자체가 훅이 된다.
// 2순위: 카테고리 라벨. coverCmd 를 안 쓴 글도 커버가 비지 않게.
// (사진은 걷어냈다 — 스톡 사진은 이 블로그 주제와 붙지 않았고 테마 대응도 안 됐다)
// lg: 상세 페이지 히어로용. 카드(300px)와 같은 글자 크기를 720px 폭에 쓰면
// 텍스트가 허공에 뜬다.
export function Cover({
  post,
  className,
  lg = false,
}: {
  post: Post;
  className?: string;
  lg?: boolean;
}) {
  if (post.coverCmd) return <TerminalCover post={post} className={className} lg={lg} />;

  return (
    <div
      className={cn(
        "flex items-end overflow-hidden bg-gradient-to-br from-[#e9edf1] to-[#f3f0ea] dark:from-[#1c1c1e] dark:to-[#161617]",
        className,
      )}
    >
      <span className="p-5 text-[28px] font-semibold tracking-tight text-black/15 dark:text-white/15">
        {post.category ?? "inpilot.dev"}
      </span>
    </div>
  );
}

function TerminalCover({
  post,
  className,
  lg,
}: {
  post: Post;
  className?: string;
  lg?: boolean;
}) {
  const line = lg ? "text-[15px]" : "text-[11.5px]";
  return (
    <div
      className={cn(
        // 라이트에서도 어둡게 두면 카드가 무거워져 밝은 배색을 따로 준다
        "relative flex flex-col justify-center overflow-hidden",
        lg ? "gap-2.5 px-7 py-6" : "gap-[7px] px-4 py-3.5",
        "bg-[#f6f7f9] dark:bg-[#141416]",
        className,
      )}
    >
      <div className={cn("absolute flex gap-1.5", lg ? "left-6 top-5" : "left-3.5 top-3")} aria-hidden>
        {[0, 1, 2].map((i) => (
          <span key={i} className="size-2 rounded-full bg-black/10 dark:bg-white/10" />
        ))}
      </div>
      <p className={cn("truncate font-mono text-neutral-600 dark:text-neutral-400", line)}>
        <span className="text-brand-green-deep dark:text-brand-green">$</span> {post.coverCmd}
      </p>
      {post.coverOut && (
        <p className={cn("truncate font-mono font-semibold text-neutral-800 dark:text-neutral-200", line)}>
          {post.coverOut}
        </p>
      )}
      <p className={cn("font-mono", line)} aria-hidden>
        <span className="text-brand-green-deep dark:text-brand-green">$</span>
        <span className={cn("ml-1 inline-block translate-y-[2px] bg-brand-green-deep dark:bg-brand-green",
            lg ? "h-4 w-2" : "h-[13px] w-[7px]")} />
      </p>
    </div>
  );
}
