import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Container } from "@/components/layout/Container";
import { getAllPosts, getPostBySlug } from "@/lib/content";
import { coverSrc } from "@/lib/utils";
import { buildMetadata } from "@/lib/metadata";
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
            {/* 히어로 커버. LCP 대상이라 lazy 를 걸지 않는다 */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={coverSrc(post)}
              alt=""
              fetchPriority="high"
              className="mt-8 aspect-[16/9] w-full rounded-xl border object-cover"
            />
            {post.coverCredit && (
              <p className="mt-2 text-right text-xs text-muted-foreground">
                {post.coverCredit}
              </p>
            )}
            <div
              id="post-body"
              className="prose prose-neutral mt-8 max-w-none dark:prose-invert prose-pre:overflow-x-auto prose-pre:rounded-lg prose-pre:bg-[var(--surface-code)] prose-pre:p-4"
            >
              <Mdx source={content} />
            </div>

            <footer className="mt-14 border-t pt-8">
              <div className="flex justify-center">
                <LikeButton slug={slug} />
              </div>

              <div className="mt-12 rounded-xl border bg-muted/30 p-6">
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
