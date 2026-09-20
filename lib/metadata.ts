import type { Metadata } from "next";

export const SITE = {
  name: "inpilot",
  title: "inpilot — AI에게 맡기지 않고, 조종합니다",
  description: "AI 워크플로우·자동화·백엔드를 만들고 전부 공개하는 기술 블로그.",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://inpilot.dev",
  author: "Seungbin",
  locale: "ko_KR",
  // 문의 수신 주소. **값을 소스에 두지 않는다** — 이 저장소는 공개고, 커밋은 지워도 남는다.
  // 서버 컴포넌트가 빌드 때 읽으므로 NEXT_PUBLIC_ 접두사가 필요 없다(클라이언트 번들에 안 실린다).
  // 받을 편지함이 있는 주소여야 한다: inpilot.dev 에는 MX 레코드가 없어 hello@inpilot.dev 로는
  // 답장을 못 받는다(2026-09-21 dig. api/subscribe 의 RESEND_REPLY_TO 주석과 같은 사정).
  contact: process.env.CONTACT_EMAIL ?? "",
} as const;

// 안 넣으면 CTA 가 통째로 사라지고 12/06 판정의 인바운드가 0 에 고정된다. 조용히 넘어가지 않는다.
if (!SITE.contact) {
  console.warn("[inpilot] CONTACT_EMAIL 미설정 — 게시물 하단 진단 콜 CTA 를 숨긴다 (인바운드 지표가 0 으로 고정)");
}

export function ogImageUrl(params: { title: string; tags?: string[] }): string {
  const sp = new URLSearchParams({ title: params.title });
  if (params.tags?.length) sp.set("tags", params.tags.join(","));
  return `${SITE.url}/api/og?${sp.toString()}`;
}

/** OG/Twitter 카드 + canonical 포함 메타데이터 생성 헬퍼. */
export function buildMetadata(opts: {
  title?: string;
  description?: string;
  path?: string;
  tags?: string[];
  type?: "website" | "article";
  publishedTime?: string;
}): Metadata {
  const title = opts.title ?? SITE.title;
  const description = opts.description ?? SITE.description;
  const url = `${SITE.url}${opts.path ?? ""}`;
  const image = ogImageUrl({ title: opts.title ?? SITE.name, tags: opts.tags });

  return {
    title,
    description,
    metadataBase: new URL(SITE.url),
    // 재발행처(velog/LinkedIn 등)에서도 블로그를 정본으로 귀속 → 중복 콘텐츠 SEO 방지
    alternates: { canonical: url },
    openGraph: {
      type: opts.type ?? "website",
      title,
      description,
      url,
      siteName: SITE.name,
      locale: SITE.locale,
      images: [{ url: image, width: 1200, height: 630 }],
      ...(opts.publishedTime ? { publishedTime: opts.publishedTime } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}
