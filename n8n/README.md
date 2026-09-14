# n8n 검수 게이트 (발행 직전 1회)

계획서: `docs/n8n-review-plan.md`. 착수 판정 전까지 **켜지 않는다.**

## 켜는 순서 (착수 결정 후)
1. `cd n8n && docker compose up -d` → http://localhost:5678 에서 계정 생성
2. Credentials 2개 등록
   - **Telegram API**: @BotFather 로 만든 봇 토큰
   - **GitHub API** (또는 Header Auth): `repo` 스코프 PAT — `repository_dispatch` 호출용
3. Workflows → Import from File → `review-gate.workflow.json`
   - Telegram 노드의 `chatId` 를 본인 chat id 로 바꾼다 (봇에게 아무 말이나 보낸 뒤 `https://api.telegram.org/bot<토큰>/getUpdates` 에서 확인)
4. 워크플로 Activate → Webhook 노드의 **Production URL** 복사
5. `gh secret set REVIEW_WEBHOOK_URL -R inpilot-dev/seungbin-dev --body "<그 URL>"`
   - 이 Secret 이 있는 순간부터 `auto-post.yml` 은 머지하지 않고 검수로 보낸다. 지우면 원래대로 자동 머지.

## 흐름
`auto-post.yml` → (PR 생성) → 웹훅 → Telegram 미리보기 + [승인][반려] → Wait(48h) → `repository_dispatch` → `review-result.yml` 이 머지·발행 또는 PR 닫기

## 아직 안 만든 것
- 주제 선택 검수(①) — 착수 둘째 주. 같은 구조를 `daily-digest.yml` 뒤에 한 번 더.
- 반려 사유 입력 — 지금은 버튼만. 사유는 PR 댓글에 직접 쓴다.
