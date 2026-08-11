import { ImageResponse } from "next/og";

export const runtime = "edge";

// 동적 OG 이미지. 쿼리: title, tags(csv). 규칙#3 토큰은 OG 이미지에만 적용 → 브랜드 원색 사용.
// 한글 렌더: NanumGothic 을 같은 오리진(/fonts)에서 self-host fetch (외부 CDN 아님). 실패 시 기본 폰트로 폴백.
async function loadFont(origin: string): Promise<ArrayBuffer | null> {
  try {
    const res = await fetch(new URL("/fonts/NanumGothic-Bold.ttf", origin), {
      cache: "force-cache",
    });
    if (!res.ok) return null;
    return await res.arrayBuffer();
  } catch {
    return null;
  }
}

export async function GET(req: Request) {
  const { searchParams, origin } = new URL(req.url);
  const title = (searchParams.get("title") ?? "inpilot.dev").slice(0, 100);
  const tags = (searchParams.get("tags") ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 4);

  const font = await loadFont(origin);

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          padding: "64px",
          background: "#ffffff",
          color: "#0a0a0a",
          fontFamily: font ? "NanumGothic, sans-serif" : "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 30, color: "#5a5a5c" }}>
          <div style={{ width: 18, height: 18, borderRadius: 9999, background: "#00d4a4" }} />
          inpilot.dev
        </div>
        <div style={{ display: "flex", fontSize: 64, lineHeight: 1.15, letterSpacing: -1 }}>
          {title}
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          {tags.map((t) => (
            <div
              key={t}
              style={{
                display: "flex",
                fontSize: 26,
                color: "#2f66c0",
                background: "rgba(55,114,207,0.15)",
                padding: "6px 18px",
                borderRadius: 9999,
              }}
            >
              {t}
            </div>
          ))}
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: font
        ? [{ name: "NanumGothic", data: font, weight: 700 as const, style: "normal" as const }]
        : [],
      headers: {
        "Cache-Control": "public, max-age=31536000, immutable, no-transform",
      },
    },
  );
}
