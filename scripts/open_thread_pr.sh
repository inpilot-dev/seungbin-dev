#!/usr/bin/env bash
# Threads 원고 → `thread/<slug>` 브랜치 → PR(라벨 원고:thread, 탈락이면 +탈락). PR URL 한 줄을 stdout 에.
# review.yml derive(블로그 파생)와 auto-post(다이제스트 논평 ①②)가 같이 쓴다 (증분 2, 2026-09-18).
#
#   scripts/open_thread_pr.sh <slug> "<본문 첫 줄: 무엇의 원고인가>"
#
# drafts/threads/<slug>.md 또는 <slug>.FAIL.md 와 사이드카 <slug>.json(publish_on·source)이 있어야 한다.
# 커밋 후 원래 브랜치로 돌아온다 — 같은 잡에서 원고를 여러 개 연다.
set -euo pipefail
SLUG=$1 HEAD_LINE=$2
D=""; for f in "drafts/threads/$SLUG.md" "drafts/threads/$SLUG.FAIL.md"; do [ -f "$f" ] && { D="$f"; break; }; done
[ -n "$D" ] || { echo "::error title=초안 없음::drafts/threads/$SLUG(.FAIL).md 가 없다" >&2; exit 1; }
SIDE="drafts/threads/$SLUG.json"
[ -f "$SIDE" ] || { echo "::error title=사이드카 없음::$SIDE — 발행일 없는 원고는 큐가 못 낸다" >&2; exit 1; }
# cut -c 는 GNU 에서 바이트 단위라 한글 요일을 못 자른다 — 파이썬 한 번에 셋 다
IFS=$'\t' read -r ON DOW SRC < <(python3 -c 'import json,sys,datetime as d; j=json.load(open(sys.argv[1])); o=j["publish_on"]
print(o, "월화수목금토일"[d.date.fromisoformat(o).weekday()], j.get("source") or "-", sep="\t")' "$SIDE")
[ "$SRC" = "-" ] && SRC=""
FAIL=false; [[ "$D" == *.FAIL.md ]] && FAIL=true

gh label create "원고:thread" --force --color c98a00 --description "Threads 원고 PR — merge 하면 발행 대기, 채널 시각에 나간다" >/dev/null
BASE=$(git rev-parse --abbrev-ref HEAD)
git checkout -q -b "thread/$SLUG"
git add "$D" "$SIDE"
git commit -q -m "thread: $SLUG (채점 $($FAIL && echo 탈락 || echo 통과) · $ON 발행 예정)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -q -u origin "thread/$SLUG"
git checkout -q "$BASE"

BODY=$(mktemp)
{
  echo "## Threads 원고 — $HEAD_LINE"; echo
  echo "**발행 예정: $ON($DOW) 09:00 KST** — merge 하면 발행 대기, 그 시각에 publish-queue 가 낸다."
  echo "그 시각까지 결정이 없으면 그 주는 보류(안 나간다)."; echo
  [ -n "$SRC" ] && { echo "출처: $SRC"; echo; }
  echo '```'; cat "$D"; echo '```'; echo
  echo "체인은 \`---\` 로 나뉜다."; echo
  echo "## 검수"; echo
  echo "- **승인** = merge → 발행 대기"; echo "- **반려** = close + 사유 한 줄"
  echo "- 채점 탈락(라벨 탈락)은 merge 해도 나가지 않는다(\`.FAIL\` 원고는 큐가 안 본다) — close 로 반려"; echo
  echo "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
} > "$BODY"
LABELS=(--label "원고:thread"); $FAIL && LABELS+=(--label "탈락")
gh pr create --title "thread: $SLUG" --body-file "$BODY" --head "thread/$SLUG" "${LABELS[@]}"
