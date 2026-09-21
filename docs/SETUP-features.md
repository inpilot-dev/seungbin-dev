# 동적 기능 설정 가이드

정적 블로그에 얹은 4개 동적 기능. **키를 안 넣어도 사이트는 정상 동작**하고, 해당 기능만 숨겨집니다(graceful degradation). 필요한 것부터 하나씩 켜세요.

로컬은 `.env.local`, 배포는 Vercel 프로젝트의 **Settings → Environment Variables**에 넣습니다.

---

## 1. 좋아요 ❤️ — 설정 불필요

`components/reader/LikeButton.tsx`. localStorage 기반이라 **키 없이 바로 작동**. 기기당 토글이며 공유 카운트는 없습니다. (집계가 필요해지면 조회수와 같은 Upstash로 승급)

---

## 2. 조회수 👁 — Upstash Redis (무료)

1. https://console.upstash.com → **Create Database** (Redis, 가까운 리전)
2. DB 상세 → **REST API** 탭 → `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` 복사
3. env에 추가 → 재배포

- 미설정 시: 조회수 숫자가 안 보임(나머지 정상)
- 중복제거: 세션당 1회만 카운트(클라 `sessionStorage`). 봇 인플레가 문제되면 `app/api/views/route.ts`에 `SET NX EX` 게이트 추가.

---

## 3. 댓글 💬 — giscus (GitHub Discussions, 무료·DB 0)

1. 댓글을 저장할 **public GitHub 저장소**에서 **Settings → Features → Discussions** 켜기
2. https://github.com/apps/giscus 설치 (해당 저장소 허용)
3. https://giscus.app 접속 → 저장소 입력 → **Discussion 카테고리**는 `Announcements` 권장 → 매핑 `pathname`
4. 페이지가 생성해주는 값에서 아래 4개를 env에 복사:
   - `NEXT_PUBLIC_GISCUS_REPO` (예: `<owner>/<repo>`)
   - `NEXT_PUBLIC_GISCUS_REPO_ID`
   - `NEXT_PUBLIC_GISCUS_CATEGORY` (예: `Announcements`)
   - `NEXT_PUBLIC_GISCUS_CATEGORY_ID`
5. 재배포

- 미설정 시: "댓글은 giscus 설정 후 표시됩니다" 안내만 노출
- 다크모드 자동 연동됨. 독자는 댓글 작성 시 GitHub 로그인 필요.

---

## 4. 뉴스레터/문의 📮 — Resend (무료)

1. https://resend.com 가입 → **API Keys** → 키 생성 → `RESEND_API_KEY`
2. **Audiences** → 오디언스 생성 → 그 ID → `RESEND_AUDIENCE_ID`
3. env에 추가 → 재배포

- 미설정 시: 구독 폼은 보이되 제출하면 "아직 설정되지 않았어요"(503)
- 동작: 이메일 형식 검증(400) → Resend 오디언스에 contact 추가
- 도메인 인증(발송 메일용)은 Resend의 **Domains**에서 별도 진행 권장.

## 5. 진단 콜 CTA 📞 — `CONTACT_EMAIL` (외부 서비스 없음)

게시물 하단 전환 한 줄의 `mailto:` 수신자. 12/06 판정의 **인바운드** 지표가 이 편지함에서 세어진다(메일 제목 `[진단] <글 제목>`으로 들어온다 — `CONTEXT.md` 참조).

1. Vercel → 프로젝트 → Settings → Environment Variables → `CONTACT_EMAIL` (Production) → 재배포

- **값을 저장소에 적지 말 것.** 이 저장소는 공개고 커밋은 지워도 SHA로 남는다. Vercel env에만 둔다.
- 접두사 없음(서버 전용). 서버 컴포넌트가 빌드 때 읽어 정적 HTML에 박으므로 `NEXT_PUBLIC_`이 필요 없다.
- **미설정 시: CTA가 통째로 숨고 빌드 로그에 경고가 찍힌다.** 사이트는 정상 동작하지만 인바운드 지표는 0에 고정된다.
- ⚠️ **받을 편지함이 있는 주소여야 한다.** `inpilot.dev`에는 MX 레코드가 없어 `hello@inpilot.dev`로는 답장을 못 받는다(2026-09-21 `dig` 확인). `send.inpilot.dev`의 MX는 SES 반송용이지 사람 편지함이 아니다.

> 📌 `.env.example`은 `.gitignore`의 `.env*`에 걸려 **추적되지 않는다** — 로컬에만 있다. 그래서 env 카탈로그는 이 파일이 정본이다.

---

## 배포 시 주의

- env 변경 후 **재배포**해야 반영됩니다(빌드타임 주입).
- `NEXT_PUBLIC_` 접두사 값은 **클라이언트에 노출**됩니다 — giscus 값은 원래 공개값이라 문제없음. Upstash/Resend 키는 접두사 없이(서버 전용) 두세요.
