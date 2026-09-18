# Threads API: 9/21 토큰 재발급 권한과 dev 모드 한계 (2026-09-18 조사)

이슈 #46 (부모 #45). 1차 출처는 Meta 공식 Threads API 문서와 changelog다. 확인하지 못한 항목은 **미확인**으로 적었다.
2026-09-18 기준 changelog 최신 항목 날짜는 2026-08-12다 ([changelog](https://developers.facebook.com/docs/threads/changelog)).

## 결론

- **키워드 검색은 리뷰 없는 앱에서 본인 글만 돌려준다.** 남의 공개 글 검색은 `threads_keyword_search` 앱 리뷰 승인 뒤에만 된다.
- **`/replies` 조회(GET)에는 `threads_read_replies`가 따로 필요하다.** `threads_manage_replies`는 POST 전용이다.
- **9/21에 받을 권한은 6개다.** 기존 계획 5개에 `threads_read_replies`를 더한다.

## 1. keyword_search (`GET /keyword_search`)

| 항목 | 공식 문서 내용 | 출처 |
|---|---|---|
| 권한 | `threads_basic` + `threads_keyword_search` | [keyword-search](https://developers.facebook.com/docs/threads/keyword-search) |
| **리뷰 전 범위** | "If your app has not been approved for the `threads_keyword_search` permission, the search will be performed only on posts owned by the authenticated user." | 같은 문서 |
| 한도 | "A user can send a maximum of 2,200 queries within a rolling 24-hour period." 결과 0건인 쿼리는 한도에 포함되지 않는다. (2025-06-25 changelog에 한도 변경 항목 있음) | 같은 문서, [changelog](https://developers.facebook.com/docs/threads/changelog) |
| `search_type` | `TOP`(기본) / `RECENT` | keyword-search |
| 기타 파라미터 | `q`(필수), `search_mode` = `KEYWORD`(기본)/`TAG`, `media_type` = `TEXT`/`IMAGE`/`VIDEO`, `since` ≥ 1688540400, `until` ≤ 현재, `limit` 기본 25·최대 100, `author_username`(2026-01-20 추가) | keyword-search, changelog |
| 필드 | 필드는 Media 필드 목록을 따른다. 다만 "The owner field is excluded and will not be returned." `id,text,username,permalink,timestamp` 각각이 응답에 오는지는 문서 문장으로 확인하지 못했다. **미확인** (Media 필드에는 포함된다) | keyword-search |

→ dev/standard 상태에서 키워드 검색으로 남의 글을 주워 오는 설계는 성립하지 않는다. #54의 폴백(본인 글의 답글)이 사실상 기본 경로다.

## 2. 답글 조회 폴백의 권한

- 문서 원문: "`threads_read_replies` — Required for making GET calls to reply endpoints.", "`threads_manage_replies` — Required for making POST calls to reply endpoints." ([retrieve-and-manage-replies](https://developers.facebook.com/documentation/threads/retrieve-and-manage-replies), [get-started](https://developers.facebook.com/documentation/threads/get-started))
- changelog 2024-06-12 항목도 `reply_audience` 조회 조건을 `threads_basic`와 `threads_read_replies`로 적었다 ([changelog](https://developers.facebook.com/docs/threads/changelog)).
- **답: 따로 필요하다.** `threads_manage_replies`만으로는 `/replies`·`/conversation` GET을 부를 수 없다.
- 참고: `reply_to_id`로 답글을 달려면 "You are the owner of the root thread post"이거나 `threads_keyword_search` 또는 `threads_manage_mentions` 권한이 있어야 한다 ([create-replies](https://developers.facebook.com/docs/threads/retrieve-and-manage-replies/create-replies)). 본인 글에 체인을 잇는 `write_thread.py`는 첫 조건으로 된다. 체인 발행에 `threads_manage_replies`가 꼭 필요한지는 페이지에 명시되어 있지 않다. **미확인**이라 유지하는 편이 안전하다.
- 한도: 답글은 24시간 이동창 기준 1,000건, 게시물은 250건이다 ([overview](https://developers.facebook.com/docs/threads/overview)).

## 3. 사용자 인사이트 (`GET /{threads-user-id}/threads_insights`)

권한은 `threads_basic`과 `threads_manage_insights`다 ([insights](https://developers.facebook.com/documentation/threads/insights)).

| metric | 형태 | 비고 |
|---|---|---|
| `views` | Time Series | "The number of times your profile was viewed." 게시물 조회수 합이 아니라 **프로필 조회수**다 |
| `likes` | Total Value | |
| `replies` | Total Value | 최상위 답글만 센다 |
| `reposts` | Total Value | |
| `quotes` | Total Value | |
| `clicks` | Link Total Values | 2025-07-02 추가 |
| `followers_count` | Total Value | "This metric does not support the `since` and `until` parameters." |
| `follower_demographics` | Total Value | since/until 미지원, **팔로워 100명 이상** 필요, `breakdown` 하나(`country`/`city`/`age`/`gender`) |

- since/until: 1712991600(2024-04-13) 이전 값은 거부된다. 생략하면 어제부터 오늘까지 2일 범위가 기본값이다. "User insights are not guaranteed to work before June 1, 2024." ([insights](https://developers.facebook.com/documentation/threads/insights))
- **`followers_count`에는 팔로워 수 하한이 없다.** 하한 100명은 `follower_demographics`에만 걸린다. 2026-01-30부터 Instagram 연동이 없는 프로필도 두 메트릭을 조회할 수 있다 ([changelog](https://developers.facebook.com/docs/threads/changelog)).
- `followers_count`는 기간을 받지 않는 현재값이다. 추이를 보려면 매일 스냅샷을 저장해야 한다 (#53 계기판).
- 미디어 인사이트 메트릭은 `views, likes, replies, reposts, quotes, shares`다. `shares`는 2024-10-28 추가.

## 4. 리뷰 전 앱에서 누가 권한을 줄 수 있나

- "each permission must first be approved through the App Review process, and your app must be published" 조건을 채우기 전에는 **Threads Tester**만 권한을 부여할 수 있다. "Threads testers can grant your app these permissions at any time." ([get-started](https://developers.facebook.com/documentation/threads/get-started))
- 본인 계정이 앱의 Threads Tester로 초대·수락되어 있어야 한다. 기존 토큰이 발급됐으므로 이미 테스터일 가능성이 높다. **미확인**이므로 9/21에 대시보드에서 확인한다.
- Advanced Access를 요청하려면 Business Verification이 필요하다 ([permissions reference](https://developers.facebook.com/docs/permissions/)). 이번 범위 밖이다.

## 9/21 권한 체크리스트 (최종)

- [ ] `threads_basic`: 모든 호출
- [ ] `threads_content_publish`: 발행 (`publish_threads.py`)
- [ ] `threads_manage_replies`: 답글 POST(숨김·관리). 체인 발행 안전용으로 유지
- [ ] **`threads_read_replies`**: 신규. `/replies`·`/conversation` GET 폴백
- [ ] `threads_manage_insights`: `/threads_insights`, 미디어 인사이트
- [ ] `threads_keyword_search`: 리뷰 전에는 본인 글만 검색된다. 받아 두면 리뷰 없이 켜 둘 수 있다

받지 않는 권한: `threads_manage_mentions`, `threads_delete`, `threads_location_tagging`, `threads_profile_discovery`. 현재 코드에서 쓰지 않는다.
