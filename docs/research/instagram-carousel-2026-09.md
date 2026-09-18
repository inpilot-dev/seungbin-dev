# Instagram 캐러셀 게시 — 4:5 유지 · image_url 조건 · 토큰 갱신

조사일 2026-09-18 · 이슈 #48 (맵 #45) · 대상: Instagram API with Instagram Login (`graph.instagram.com`, 문서 예시 버전 v25.0)

전제: 카드는 1080×1350 JPEG, 캐러셀당 ≤10장, `public/cards/<slug>/NN.jpg` 로 커밋해서 `https://inpilot.dev/cards/<slug>/NN.jpg` 로 서빙한다. 계정은 이미 프로페셔널 계정이다.

출처 약어

- **[CP]** Content Publishing — https://developers.facebook.com/docs/instagram-platform/content-publishing
- **[MEDIA]** IG User Media 레퍼런스 — https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
- **[LIMIT]** IG User Content Publishing Limit — https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit
- **[LOGIN]** Business Login — https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login
- **[REFRESH]** refresh_access_token 레퍼런스 — https://developers.facebook.com/docs/instagram-platform/reference/refresh_access_token
- **[HELP-RES]** Instagram 고객센터, 사진 해상도 — https://help.instagram.com/1631821640426723/
- **[HELP-MULTI]** Instagram 고객센터, 여러 장 게시 — https://help.instagram.com/269314186824048/

## 1. 캐러셀에서 4:5(1080×1350)가 유지되나 — 유지된다

| 사실 | 출처 |
|---|---|
| "Carousel images are all cropped based on the first image in the carousel, with the default being a 1:1 aspect ratio." | [CP] |
| 이미지 비율은 4:5 ~ 1.91:1 범위여야 한다. 가로 최소 320, 최대 1440 | [MEDIA] |
| 가로 320~1080px에 비율이 1.91:1~4:5 사이면 원본 해상도를 유지한다. 가로 1080이면 세로 566~1350 | [HELP-RES] |
| 게시물 하나 안의 사진은 모두 같은 방향(정사각·세로·가로)을 쓴다 | [HELP-MULTI] |
| 캐러셀은 최대 10개 (API 기준. 앱은 20개까지 허용하지만 API는 10) | [CP], [HELP-MULTI] |

결론: 1080×1350은 허용 범위의 **세로 끝(4:5)에 딱 맞는다**. 모든 장이 4:5이면 첫 장도 4:5라서 크롭 기준이 4:5가 되고, 잘리는 장이 없다. "default 1:1"은 기준 이미지가 없을 때의 기본값으로 읽히지만, API로 올렸을 때 첫 장 비율을 실제로 따르는지 문서에 예시가 없다 → **미확인(첫 게시 후 눈으로 확인)**.
주의: 4:5보다 1px이라도 세로로 길면(예: 1080×1351) 범위 밖이라 컨테이너 생성이 실패하거나 잘린다. 렌더러 출력 크기를 게시 전에 검사해 두면 좋다.

## 2. `image_url` 조건 — inpilot.dev apex는 충족한다

| 조건 | 내용 | 출처 |
|---|---|---|
| 포맷 | JPEG만. MPO·JPS 같은 확장 JPEG 불가 | [CP], [MEDIA] |
| 크기 | 최대 8 MB | [MEDIA] |
| 색공간 | sRGB (다른 색공간은 sRGB로 변환됨) | [MEDIA] |
| 공개성 | Meta가 URL을 cURL로 가져간다. 게시 시점에 공개 서버에 있어야 한다 | [CP], [MEDIA] |
| 리다이렉트 | 공식 문서에 명시 없음 → **미확인**. 커뮤니티 보고로는 리다이렉트·로그인 페이지 뒤 URL에서 9004/2207052("media could not be fetched")가 난다 ([Make 커뮤니티](https://community.make.com/t/only-photo-or-video-can-be-accepted-as-media-type-9004-oauthexception/78565), [postiz #1472](https://github.com/gitroomhq/postiz-app/issues/1472)) | 2차 출처 |
| 요구 헤더·응답 시간 | 공식 문서에 명시 없음 → **미확인** | — |

### 실측 (2026-09-18, `curl -sI`)

아직 `public/` 에 JPEG가 없어서 같은 정적 경로인 `public/diagrams/*.svg`, `public/fonts/*.ttf` 로 확인했다.

```
https://inpilot.dev/diagrams/cursor-pagination.svg → HTTP/2 200, content-type: image/svg+xml, content-length: 2174, 1.1s
https://inpilot.dev/fonts/NanumGothic-Bold.ttf    → HTTP/2 200, content-type: font/ttf, content-length: 2073868 (2 MB), 2.3s
https://www.inpilot.dev/...                        → HTTP/2 308 → https://inpilot.dev/... (next.config.ts redirects)
UA "facebookexternalhit/1.1"                       → 200 (봇 차단 없음)
```

- apex(`inpilot.dev`)는 리다이렉트 없이 200, 확장자에 맞는 `content-type`, `content-length` 를 준다. `.jpg` 면 `image/jpeg` 가 나올 것이다(Vercel 정적 서빙이 확장자로 결정).
- **`www.inpilot.dev` 는 308 리다이렉트** → URL은 반드시 apex로 만든다.
- 응답은 `x-vercel-cache: MISS` 에서 1~2 s. 1080×1350 JPEG(수백 KB)면 충분히 빠르다.
- 파일이 main 에 머지되어 **프로덕션 배포가 끝난 뒤**에야 200이 된다(배포 전은 404 확인). 게시 스크립트는 첫 장 URL에 HEAD 200 + `content-type: image/jpeg` 를 확인한 뒤 컨테이너를 만든다.
- 프리뷰 배포 URL은 Vercel Deployment Protection 이 걸려 있으면 로그인 페이지로 가서 실패한다 → 프로덕션 도메인만 쓴다.

## 3. 컨테이너 상태 폴링 · 게시 한도

흐름 [CP]: 장마다 `POST /<IG_ID>/media` (`image_url`, `is_carousel_item=true`) → `POST /<IG_ID>/media` (`media_type=CAROUSEL`, `children=<id,...>`, `caption`) → `POST /<IG_ID>/media_publish` (`creation_id`).
캡션은 캐러셀 자식 항목에는 못 넣는다(부모 컨테이너에만) [MEDIA].

| 사실 | 출처 |
|---|---|
| `GET /<CONTAINER_ID>?fields=status_code` 값: `FINISHED`, `IN_PROGRESS`, `ERROR`, `EXPIRED`, `PUBLISHED` | [CP] |
| "We recommend querying a container's status once per minute, for no more than 5 minutes." | [CP] |
| `EXPIRED` = 24시간 안에 게시 안 된 컨테이너 | [CP] |
| 계정당 24시간 이동 창에서 API 게시 100건. **캐러셀은 1건** | [CP] |
| 컨테이너 생성은 계정당 24시간 400개 (캐러셀 10장 = 자식 10 + 부모 1 = 11개로 셈 — 추론, 문서에 명시 없음) | [MEDIA] |
| `GET /<IG_ID>/content_publishing_limit` → `quota_usage`(since 이후 게시 수), `config.quota_total`, `config.quota_duration`(86400). `since` 는 24시간 이내 Unix 타임스탬프 | [LIMIT] |

**불일치**: [CP]는 100건이라 쓰고, [LIMIT] 샘플 응답은 `quota_total: 50` 이다. 실제 값은 첫 호출의 `config.quota_total` 로 확인한다 → **미확인**. 하루 몇 건 수준 게시에서는 어느 쪽이든 문제없다.

## 4. 토큰 · 권한

| 사실 | 출처 |
|---|---|
| 단기 토큰: 1시간, 1회용 | [LOGIN] |
| 장기 토큰: 60일 | [LOGIN] |
| 갱신: `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=<장기토큰>` | [REFRESH] |
| 갱신 조건: 장기 토큰이 **발급 24시간 이상 경과** + **만료 전** + 사용자가 `instagram_business_basic` 허용 | [LOGIN], [REFRESH] |
| 응답: `access_token`, `token_type: bearer`, `expires_in`(초, 예시 5183944 ≈ 60일). 갱신한 토큰도 60일 | [REFRESH] |
| 게시에 필요한 권한: `instagram_business_basic`, `instagram_business_content_publish` (구 스코프명은 2025-01-27 폐기) | [CP], [LOGIN] |
| `content_publishing_limit` 도 같은 두 권한 | [LIMIT] |

운영 함의: 갱신은 새 토큰을 돌려주므로 저장소 시크릿을 갱신 결과로 덮어써야 한다. 만료되면 갱신 불가 → 사람이 다시 로그인해야 한다. 2026-10-26 토큰 수령 후 24시간이 지나면 바로 갱신 가능하고, 주기적 갱신(예: 월 1회)이면 60일 창 안에 넉넉하다. 갱신 시 이전 토큰이 즉시 무효가 되는지는 **미확인**.

## 계획에 영향 주는 것

1. 4:5는 유지된다 — 카드 규격 변경 불필요. 단 1350을 넘으면 안 된다.
2. URL은 **apex `https://inpilot.dev/...` 만**. `www` 는 308. 프로덕션 배포 완료 후 HEAD 확인 필요.
3. 폴링은 1분 간격 최대 5분. 컨테이너는 24시간 뒤 만료.
4. 게시 한도 100(또는 50) — 하루 몇 건 수준이면 무관. 캐러셀은 1건으로 센다.
