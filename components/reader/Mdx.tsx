import type { ComponentPropsWithoutRef } from "react";
import { MDXRemote } from "next-mdx-remote/rsc";
import rehypeSlug from "rehype-slug";
import rehypePrettyCode from "rehype-pretty-code";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./CodeBlock";

// 공통 MDX 렌더 — rehype 체인은 여기에 산다 (next-mdx-remote 방식, next.config 아님).
// h2/h3 는 rehype-slug 가 id 를 자동 부여 → TOC 가 그 id 를 스캔.
const mdxOptions = {
  mdxOptions: {
    remarkPlugins: [remarkGfm],
    rehypePlugins: [
      rehypeSlug,
      [rehypePrettyCode, { theme: "github-dark", keepBackground: false }],
    ],
  },
} as const;

const components = {
  pre: CodeBlock,
  // 본문 이미지. 마크다운 title(`![alt](src "캡션")`)이 있으면 캡션으로 붙인다.
  img: ({ title, alt, ...props }: ComponentPropsWithoutRef<"img">) => (
    <figure className="my-8">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        {...props}
        alt={alt ?? ""}
        loading="lazy"
        decoding="async"
        className="w-full rounded-lg border"
      />
      {title && (
        <figcaption className="mt-2 text-center text-sm text-muted-foreground">
          {title}
        </figcaption>
      )}
    </figure>
  ),
  // 넓은 표는 자체 가로 스크롤 컨테이너로 (모바일 오버플로우/클리핑 방지)
  table: (props: ComponentPropsWithoutRef<"table">) => (
    <div className="overflow-x-auto">
      <table {...props} />
    </div>
  ),
};

export function Mdx({ source }: { source: string }) {
  return (
    <MDXRemote
      source={source}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      options={mdxOptions as any}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      components={components as any}
    />
  );
}
