# Resend API — 브로드캐스트·구독자 수 (2026-09 조사)

> 이슈 #47 (map #45 의 자식). 증분 3(계기판 구독자 수)·증분 4(금 09:00 뉴스레터)가 기대는 사실만 확정한다.
> 조사일 2026-09-18. 1차 출처: resend.com/docs (`.md` 원문), `resend/resend-openapi` 저장소(`resend.yaml`, 마지막 커밋 2026-09-17), Resend 블로그.
> "미확인" = 공식 문서에 명시가 없어 9/21 실제 호출로 확인해야 하는 항목.

## 한 줄 요약

Audiences 는 **Segments 로 이름이 바뀌었고**(2025-11-05 발표) 브로드캐스트는 이제 `segment_id` 필수다. `audience_id` 는 deprecated 별칭으로 남아 있다. 기존 `RESEND_AUDIENCE_ID` 값을 `segment_id` 자리에 넣으면 되고(같은 ID 로 추정 — 미확인), 키는 **full access** 여야 한다.

## 1. Broadcasts API 현재 형태

| 항목 | 사실 | 출처 |
|---|---|---|
| 생성 | `POST https://api.resend.com/broadcasts` — 필수 `segment_id`·`from`·`subject`, 선택 `html`·`text`·`reply_to`·`name`·`topic_id`·`send`·`scheduled_at` | [Create Broadcast](https://resend.com/docs/api-reference/broadcasts/create-broadcast) |
| `audience_id` | OpenAPI `CreateBroadcastOptions` 에 `deprecated: true` 로 남음. 설명: "Use `segment_id` instead. Unique identifier of the segment…" | [resend.yaml](https://github.com/resend/resend-openapi/blob/main/resend.yaml) |
| 이름 변경 | 문서 안내문: "Audiences are now called Segments." `/audiences` 엔드포인트는 "still work, but will be removed in the future." 제거 날짜는 없음 | [Create Audience](https://resend.com/docs/api-reference/audiences/create-audience), [Migration guide](https://resend.com/docs/dashboard/segments/migrating-from-audiences-to-segments) |
| 발표일 | 2025-11-05 "New Contacts Experience" — Global Contacts, Audiences→Segments | [블로그](https://resend.com/blog/new-contacts-experience) |
| 2단계 발송 | `POST /broadcasts` (기본 `send:false` = draft) → `POST /broadcasts/{id}/send`. 발송 엔드포인트는 "API 로 만든 브로드캐스트만" 보낼 수 있음 | [Send Broadcast](https://resend.com/docs/api-reference/broadcasts/send-broadcast) |
| 1단계 발송 | 생성 시 `send:true` 면 별도 `/send` 호출 없이 발송/예약 | Create Broadcast |
| 예약 | `scheduled_at` 지원 — 자연어(`in 1 hour`) 또는 ISO 8601. 생성 시엔 `send:true` 필수, `/send` 본문에도 넣을 수 있음 | Create/Send Broadcast |
| 취소 | `scheduled`→`draft`, `queued`→`canceled`. 상태: `draft`·`scheduled`·`queued`·`sent`·`canceled` | [Manage Broadcasts](https://resend.com/docs/dashboard/broadcasts/manage-broadcasts), [Cancel](https://resend.com/docs/knowledge-base/how-do-i-cancel-a-broadcast) |
| 수신거부 | 본문에 `{{{RESEND_UNSUBSCRIBE_URL}}}` 를 넣으면 연락처별 링크로 치환. `topic_id` 를 빼면 세그먼트의 구독 중인 연락처 전원에게 발송 | Create Broadcast |

**금 09:00 설계 함의**: GitHub Actions cron 지연을 피하려면 목요일 등 여유 시점에 `send:true` + `scheduled_at: "2026-..T00:00:00Z"`(KST 09:00 = UTC 00:00)로 예약해 두는 방식이 가능하다. 즉시 발송도 가능.

## 2. 구독자 수 세기

- `GET https://api.resend.com/contacts?segment_id=<ID>&limit=100&after=<마지막 id>` — OpenAPI 상 `segment_id` 는 **query** 파라미터(문서 페이지는 "Path Parameters" 로 표기하지만 cURL·OpenAPI 는 query). [List Contacts](https://resend.com/docs/api-reference/contacts/list-contacts), resend.yaml
- 응답 `{object:"list", has_more, data:[{id,email,first_name,last_name,created_at,unsubscribed}]}`. `has_more` 가 false 가 될 때까지 `after=<data[-1].id>` 로 반복. [Pagination](https://resend.com/docs/api-reference/pagination)
- `limit` 을 생략하면 "all contacts will be returned in a single response" 라고 적혀 있음(최대 100·최소 1). 한 번에 다 오는지 상한이 있는지는 **미확인** → 스크립트는 `limit=100` + `has_more` 루프로 짠다.
- **unsubscribed 제외 필터 파라미터는 없다**. 클라이언트에서 `unsubscribed == false` 만 센다. `unsubscribed` 는 전역 상태(모든 브로드캐스트 거부). [Create Contact](https://resend.com/docs/api-reference/contacts/create-contact)
- Global Contacts 모델: `segment_id` 없이 부르면 팀 전체 연락처가 나온다 → 반드시 `segment_id` 를 붙인다.
- 전용 "개수" 엔드포인트는 없음(OpenAPI 에 없음).
- 레이트리밋: 팀당 기본 10 req/s, 초과 시 429. [Usage Limits](https://resend.com/docs/api-reference/rate-limit)

## 3. 구독자 0명·테스트 발송·키 권한

| 질문 | 답 | 출처 |
|---|---|---|
| 0명 세그먼트에 브로드캐스트 | **미확인** — 문서에 언급 없음. 에러인지 0통 `sent` 인지 모름. 스크립트가 먼저 2번의 구독자 수를 세고 0이면 발송을 건너뛰는 게 안전 | — |
| 연락처 한도 초과 | 브로드캐스트 발송 시 `403 validation_error` "You have reached your contacts quota…" | Usage Limits |
| 테스트 발송 `POST /emails` | `from` 이 `@resend.dev` 면 **계정 주인 이메일로만** 발송 가능, 그 외 수신자는 403. 다른 주소로 보내려면 인증된 도메인의 `from` 필요 | [403 resend.dev](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain) |
| 이메일 쿼터 | Free 플랜은 일일 쿼터(UTC 자정 리셋) + 월 쿼터, 초과 시 429 `daily_quota_exceeded`/`monthly_quota_exceeded` | Usage Limits |
| 키 권한 | `full_access`: 모든 리소스 생성·삭제·조회·수정. `sending_access`: "Can only send emails" (+선택적 `domain_id` 제한) | [Create API key](https://resend.com/docs/api-reference/api-keys/create-api-key), [Create an API key](https://resend.com/docs/create-an-api-key) |
| 우리에게 필요한 권한 | contacts 목록 조회·broadcasts 생성은 "send emails" 밖이므로 **full access 필요**. sending access 로 broadcasts 가 되는지는 문서에 명시 없음(미확인이지만 문구상 불가로 본다) | 위 두 문서 |
| 키 값 재확인 | Resend 대시보드는 생성 후 키 값을 다시 보여주지 않음 | [Manage API keys](https://resend.com/docs/dashboard/api-keys/introduction) |

## 4. 블로그 구독 폼 코드 (`app/api/subscribe/route.ts`)

- 읽는 env: **`RESEND_API_KEY`**, **`RESEND_AUDIENCE_ID`** (둘 다 없으면 503), **`RESEND_FROM`** (없으면 환영 메일 생략), **`RESEND_REPLY_TO`** (환영 메일 `reply_to`, 선택). 그 밖에 `LEAD_MAGNET_URL`·`STAR_GATE_URL`(Resend 무관).
- 호출: `GET /audiences/{RESEND_AUDIENCE_ID}/contacts/{email}` 로 중복 확인 → 없으면 `POST /audiences/{RESEND_AUDIENCE_ID}/contacts` `{email, unsubscribed:false}` → `POST /emails` 환영 메일.
- 즉 contacts 는 `RESEND_AUDIENCE_ID` 가 가리키는 옛 Audience(=지금의 Segment)에 들어간다.
- 이 경로(`/audiences/{id}/contacts`)는 현재 OpenAPI 에 없고 문서의 대체는 `POST /contacts` + `segments:[{id}]`, `GET /contacts/{email}`. Audiences 계열은 "still work" 로 안내되지만 이 하위 경로가 지금도 200 을 주는지는 **미확인**(구독자 0명이라 실운영 검증 이력도 없음). 이관은 #47 범위 밖 — 제거 공지 전까지 동작한다고 보고, 깨지면 위 대체 경로로 바꾼다.
- 폼이 contacts 를 쓰므로 Vercel 의 `RESEND_API_KEY` 는 full access 여야 한다(sending access 면 구독이 502). 실제 권한은 **미확인** — 9/21 에 Resend 대시보드 API keys 에서 확인.

## 9/21 Secret 최종본

| Secret 이름 | 필수 | 값의 출처 | 용도 |
|---|---|---|---|
| `RESEND_API_KEY` | 예 | Vercel 프로젝트 env 의 같은 이름 값. Vercel 에서 "Sensitive" 라 안 보이면 Resend 대시보드 → API keys 에서 **Full access** 키를 새로 만들어 Vercel·GitHub 둘 다 갱신 | contacts 조회·broadcast 생성/발송 |
| `RESEND_AUDIENCE_ID` | 예 | Vercel env 같은 이름 값. 교차확인: Resend 대시보드 Audience/Segments 페이지의 ID. 스크립트는 이 값을 **`segment_id`** 로 보낸다(이름은 폼 코드와 맞추려고 유지) | `GET /contacts?segment_id=`, `POST /broadcasts` |
| `RESEND_FROM` | 예 | Vercel env 같은 이름 값. 인증된 도메인 주소여야 함(`@resend.dev` 면 본인에게만 발송 가능) | broadcast `from` |
| `RESEND_REPLY_TO` | 선택 | Vercel env 에 있으면 같은 값 | broadcast `reply_to` |

## 미확인 목록 (9/21 첫 호출로 확인)

1. 옛 Audience ID 를 `segment_id` 로 그대로 쓸 수 있는가 — OpenAPI 가 `audience_id` 를 "segment 의 ID" 라고 설명하는 것으로 추정할 뿐 명시 문장 없음. 첫 `GET /contacts?segment_id=…` 가 200 이면 확정.
2. 0명 세그먼트 브로드캐스트의 동작.
3. Vercel 키가 full access 인지.
4. `/audiences/{id}/contacts` 하위 경로가 아직 동작하는지.
5. `limit` 생략 시 전량 반환의 상한.
