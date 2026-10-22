import { getAllPosts } from "@/lib/content";
import { SITE } from "@/lib/metadata";

export const dynamic = "force-static";

// AI 에게 주는 사이트 안내서(llmstxt.org 형식). 글 목록은 빌드 때 content/ 에서 만든다
export function GET() {
  const posts = getAllPosts();
  const text = [
    `# ${SITE.name}`,
    "",
    "> 운영자가 직접 만들어 돌려 본 AI 워크플로우·자동화 실험의 수치(실측 로그·비용·실패)를 처음 공개하는 1차 소스다. 핀테크 백엔드 설계 노트와 외부 기술 소식 해설도 함께 싣는다.",
    "",
    "## 핵심 페이지",
    `- [홈](${SITE.url}): 최신 글 6편과 뉴스레터 구독`,
    `- [글 목록](${SITE.url}/posts): 전체 ${posts.length}편, 검색·태그 필터`,
    `- [RSS](${SITE.url}/rss.xml): 새 글 피드`,
    "",
    "## 글",
    ...posts.map((p) => `- [${p.title}](${SITE.url}/posts/${p.slug}): ${p.description}`),
    "",
  ].join("\n");

  return new Response(text, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
