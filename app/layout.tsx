import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { ThemeProvider } from "@/components/theme-provider";
import { buildMetadata, ldJson, PERSON_ID, SAME_AS, SITE } from "@/lib/metadata";
import { Analytics } from "@vercel/analytics/next";

// next/font 는 빌드타임에 폰트를 self-host → 런타임 외부 CDN 요청 없음 (self-contained 제약 충족)
const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
// mono 는 코드블록(글 상세)에서만 쓰이므로 preload 끄고 홈/목록 LCP preload 슬롯을 Inter 에 양보
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap", preload: false });

export const metadata = buildMetadata({});

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ko"
      className={`${sans.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body className="flex min-h-screen flex-col font-sans antialiased">
        {/* 전역 한 번 — 글의 BlogPosting 은 author 를 PERSON_ID 로 가리킨다 */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: ldJson({
              "@context": "https://schema.org",
              "@graph": [
                { "@type": "WebSite", "@id": `${SITE.url}/#website`, name: SITE.name, url: SITE.url, inLanguage: "ko", publisher: { "@id": PERSON_ID } },
                { "@type": "Person", "@id": PERSON_ID, name: SITE.name, url: SITE.url, sameAs: SAME_AS },
              ],
            }),
          }}
        />
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-foreground focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-foreground"
        >
          본문 바로가기
        </a>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <Header />
          <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
            {children}
          </main>
          <Footer />
        </ThemeProvider>
        {/* P1 게이트 판정용 (Threads→랜딩 100세션) — 리퍼러별 세션은 Vercel 대시보드 Analytics 탭 */}
        <Analytics />
      </body>
    </html>
  );
}
