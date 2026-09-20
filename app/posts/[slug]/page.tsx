import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { Container } from "@/components/layout/Container";
import { getAllPosts, getPostBySlug } from "@/lib/content";
import { buildMetadata, SITE } from "@/lib/metadata";
import { Cover } from "@/components/post-list/Cover";
import { Mdx } from "@/components/reader/Mdx";
import { TOC } from "@/components/reader/TOC";
import { ReadingProgress } from "@/components/reader/ReadingProgress";
import { ViewCounter } from "@/components/reader/ViewCounter";
import { LikeButton } from "@/components/reader/LikeButton";
import { Comments } from "@/components/reader/Comments";
import { NewsletterForm } from "@/components/NewsletterForm";

export function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const data = getPostBySlug(slug);
  if (!data) return {};
  return buildMetadata({
    title: data.post.title,
    description: data.post.description,
    path: `/posts/${slug}`,
    tags: data.post.tags,
    type: "article",
    publishedTime: data.post.date,
  });
}

export default async function PostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const data = getPostBySlug(slug);
  if (!data) notFound();
  const { post, content } = data;

  // ponytail: 폼·API 라우트 대신 mailto. 12/06 판정의 인바운드는 "특정 게시물을 지목한" 건수라
  // 제목에 글 제목이 박혀 오는 게 곧 집계 수단이다(메일함에서 `[진단]` 검색). 폼은 라우트·저장·스팸
  // 처리가 붙는데 세는 일은 여전히 손이다 — 주 2건을 넘어 손으로 분류가 안 될 때 폼으로 올린다.
  // 주소가 없으면 CTA 를 안 낸다 — 받을 곳 없는 mailto 는 신청을 버린다 (.env.example 의 "비우면 숨긴다" 관례)
  const diagnosticMail = !SITE.contact ? null :
    `mailto:${SITE.contact}` +
    `?subject=${encodeURIComponent(`[진단] ${post.title}`)}` +
    `&body=${encodeURIComponent(
      `이 글을 보고 연락합니다: ${SITE.url}/posts/${slug}\n\n` +
        `지금 손으로 반복하는 일:\n` +
        `여기에 주 몇 시간쯤 씁니다:\n`,
    )}`;

  return (
    <>
      <ReadingProgress />
      <Container className="py-12">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_200px]">
          <article className="mx-auto w-full max-w-[720px]">
            <h1 className="text-[36px] font-semibold leading-tight tracking-tight">
              {post.title}
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              {post.date} · {post.readingTime} <ViewCounter slug={slug} />
            </p>
            <Cover
              post={post}
              lg
              className="mt-8 aspect-[21/9] w-full rounded-xl border"
            />
            <div
              id="post-body"
              className="prose prose-neutral mt-8 max-w-none dark:prose-invert prose-pre:overflow-x-auto prose-pre:rounded-lg prose-pre:bg-[var(--surface-code)] prose-pre:p-4"
            >
              <Mdx source={content} />
            </div>

            <footer className="mt-14 border-t pt-8">
              {post.tags.length > 0 && (
                <div className="mb-10 flex flex-wrap gap-x-3 gap-y-2">
                  {post.tags.map((t) => (
                    <Link
                      key={t}
                      href={`/posts?tags=${encodeURIComponent(t)}`}
                      className="text-sm font-medium text-brand-tag hover:underline"
                    >
                      #{t}
                    </Link>
                  ))}
                </div>
              )}
              <div className="flex justify-center">
                <LikeButton slug={slug} />
              </div>

              {diagnosticMail && (
                <div className="mt-12 rounded-xl border border-dashed p-5 text-sm leading-relaxed">
                  이 글처럼 <strong className="font-semibold">사람 손을 빼는 자동화</strong>를 붙일 데가
                  있으면, 그 일에 <strong className="font-semibold">주 몇 시간</strong>이 들어가는지부터
                  30분 통화로 같이 셉니다.{" "}
                  <a
                    href={diagnosticMail}
                    className="whitespace-nowrap font-medium underline underline-offset-4"
                  >
                    진단 콜 신청 →
                  </a>
                </div>
              )}

              <div
                className={`${diagnosticMail ? "mt-6" : "mt-12"} rounded-xl border bg-muted/30 p-6`}
              >
                <h3 className="text-lg font-semibold">새 글이 올라오면 받아보기</h3>
                <p className="mt-1 mb-4 text-sm text-muted-foreground">
                  스팸 없이, 새 글이 올라올 때만 보내드려요.
                </p>
                <NewsletterForm />
              </div>

              <section className="mt-14">
                <h3 className="mb-6 text-lg font-semibold">댓글</h3>
                <Comments />
              </section>
            </footer>
          </article>
          <aside className="hidden lg:block">
            <TOC containerId="post-body" />
          </aside>
        </div>
      </Container>
    </>
  );
}
