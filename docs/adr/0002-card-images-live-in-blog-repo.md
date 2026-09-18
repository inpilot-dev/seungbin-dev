---
status: accepted
date: 2026-09-18
---
# 카드뉴스 JPEG는 블로그 저장소 `public/cards/`에 두고, 인스타는 inpilot.dev URL을 읽는다

Instagram 콘텐츠 발행 API는 공개 URL의 JPEG만 받는다(PNG 불가, 캐러셀 ≤10장, 24h 100건). card-news(비공개 저장소,
Playwright 렌더러)는 PNG를 로컬에 낸다. 별도 이미지 호스팅(Vercel Blob·GitHub release asset) 대신 렌더 결과를 JPEG로
바꿔 seungbin-dev의 `public/cards/<slug>/NN.jpg`에 PR로 넣기로 했다 — 승인(merge)이 곧 공개 URL 생성이고,
검수 인박스가 저장소 하나로 남는다. card-news 저장소는 합치지 않고 렌더러로만 쓴다(비공개 문서·main 커밋 정책 충돌,
2026-09-14 결정 유지).

## Consequences
- 덱 승인마다 Vercel 배포 1회, 저장소 ~2MB 증가. 3개월에 ~25MB — 커지면 Vercel Blob으로 옮길 자리는 publish 스텝 하나다.
- 이미지가 인스타 게시 전에 공개 URL로 존재한다. 어차피 공개될 것이라 감수한다.
- card-news → seungbin-dev PR 생성에는 두 저장소를 아우르는 fine-grained PAT(`GH_PAT`)가 필요하다.
