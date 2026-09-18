# claude -p 로 card-news 스킬을 헤드리스 실행할 수 있나 (조사 #49)

- 조사일: 2026-09-18 · 로컬 확인 버전: Claude Code **2.1.274** (`claude --version`)
- 1차 출처: code.claude.com/docs — [headless](https://code.claude.com/docs/en/headless) · [cli-reference](https://code.claude.com/docs/en/cli-reference) · [skills](https://code.claude.com/docs/en/skills) · [agent-sdk/skills](https://code.claude.com/docs/en/agent-sdk/skills) · [agent-sdk/agent-loop](https://code.claude.com/docs/en/agent-sdk/agent-loop) · [permissions](https://code.claude.com/docs/en/permissions) · [authentication](https://code.claude.com/docs/en/authentication) · [github-actions](https://code.claude.com/docs/en/github-actions), 로컬 `claude --help`, card-news 저장소(읽기 전용, `~/dev/products/card-news`)
- 실제 `claude -p` 작업은 돌리지 않았다(쿼터). 아래 "미검증"은 스모크(#50)가 확인할 것.

## 결론 한 줄

**된다.** `-p` 프롬프트 첫머리의 `/card-news …` 는 스킬로 확장되고, `CLAUDE_CODE_OAUTH_TOKEN` 으로 도구 사용까지 된다. 단 세 가지를 워크플로가 해 줘야 한다: ① 러너에 `.claude/skills/card-news` 심링크를 만든다(저장소에 없다) ② `--permission-mode dontAsk` + `--allowedTools` 로 도구 면을 연다 ③ ⑧ 승인은 "리뷰 화면까지 만들고 멈춤"으로 끊는다.

## 1. `-p` 에서 슬래시 스킬이 되나 · 탐색 규칙

| 사실 | 출처 |
|---|---|
| `-p` 에서 사용자 호출 스킬과 커스텀 커맨드는 동작한다. 프롬프트 문자열에 `/skill-name` 을 넣으면 실행 전에 확장된다. `/login` 처럼 터미널 UI 전용 빌트인은 안 된다 | headless §Create a commit 의 Note |
| `-p` 는 `--bare` 가 아니면 대화형과 같은 컨텍스트(작업 디렉터리·`~/.claude` 의 스킬·CLAUDE.md·hooks)를 싣는다 | headless §Start faster with bare mode |
| 프로젝트 스킬 = `.claude/skills/<name>/SKILL.md`, 시작 디렉터리와 그 위로 저장소 루트까지 | skills §Where skills are discovered |
| **심링크 허용**: personal·project 위치의 `<skill-name>` 항목은 심링크여도 되고 대상의 `SKILL.md` 를 읽는다 | skills §Symlinks |
| **v2.1.274 부터** 매칭 안 되는 `/<name>` 은 실패하지 않고 평문 메시지로 모델에 간다("명령이 안 돌았다"는 메모와 함께). 이전엔 `Unknown command:` 로 즉시 끝났다 | agent-sdk/skills §Dispatch commands by name |
| 로드된 스킬 확인 = `system/init` 이벤트의 `skills` 배열, `slash_commands` 배열 | agent-sdk/skills §Confirm skills loaded, §Discover available commands |
| `--bare` 는 스킬 자동 탐색을 끄고(단 `--add-dir` 의 `.claude/skills/` 는 로드) **OAuth 를 안 읽는다** → 이 용도엔 못 쓴다 | headless §bare, authentication §Generate a long-lived token |

**card-news 의 함정 — 스킬이 저장소에 등록돼 있지 않다.** 스킬 본체는 `skill/SKILL.md` 이고, 이 머신에선 `~/.claude/skills/card-news -> ~/dev/products/card-news/skill` 심링크로만 등록돼 있다(로컬 `ls -la ~/.claude/skills`). 게다가 `.claude/` 는 gitignore 대상이다(`card-news/.gitignore:17`). 체크아웃만 한 러너에선 `/card-news` 가 **조용히 평문으로** 간다(위 v2.1.274 동작). 그래서:

```bash
mkdir -p .claude/skills && ln -sfn ../../skill .claude/skills/card-news
```

그러면 스킬 base directory 는 `<repo>/.claude/skills/card-news`, `pwd -P` 는 `<repo>/skill`, 그 상위가 저장소 루트라 SKILL.md ①의 경로 계산(`SKILL.md:50-56`)이 그대로 맞는다.

→ 답: **프롬프트에 `/card-news <주제>` 를 넣으면 된다.** "스킬을 읽게 하는 프롬프트"는 필요 없다. 단 심링크 단계가 빠지면 에러 없이 엉뚱하게 돈다 — init 의 `skills` 에 `card-news` 가 있는지 게이트로 확인할 것.

## 2. 권한 · 인증

**권한 — `--dangerously-skip-permissions` 없이 좁힐 수 있다.**

| 사실 | 출처 |
|---|---|
| `-p` 의 기본 시작 모드는 Manual(`default`). 승인이 필요한 호출은 응답할 호스트가 없으면 거부된다 | headless §Auto-approve tools, §Turn off permission prompts |
| `dontAsk`: 절대 묻지 않는다. allow 규칙에 걸린 것·원래 승인이 필요 없는 것(작업 디렉터리 안 읽기, 읽기 전용 명령)만 돌고 나머지는 거부. `AskUserQuestion` 은 허용해도 거부 | headless §Auto-approve tools, agent-loop §Permission mode |
| `--permission-prompts none`(v2.1.259+): 사람 응답이 필요한 도구(`AskUserQuestion`)를 아예 빼고, 거부된 요청을 재시도하지 말라고 모델에 알린다. 거부는 결과 메시지의 `permission_denials` 에 쌓인다 | headless §Turn off permission prompts |
| `--allowedTools` 는 권한 규칙 문법. `Bash(npm run *)` 은 prefix 매치(공백+`*`). `&&`·`;`·`|` 로 이은 복합 명령은 **부분 명령마다 따로** 맞아야 한다 | headless §Create a commit, permissions §Compound commands |
| deny(`--disallowedTools`)가 allow 보다 우선 | cli-reference `--disallowedTools`, agent-loop §Tool permissions |
| WebFetch·WebSearch 는 Manual 에서 승인 필요 → 허용 목록에 넣어야 한다 | permissions 표 |
| `bypassPermissions` 는 Unix root 로는 못 쓴다. CI·컨테이너 같은 격리 환경 전용 | agent-loop §Permission mode |
| 스킬 frontmatter 의 `allowed-tools` 는 `-p`/SDK 에서도 적용된다 — card-news SKILL.md 엔 없다(`SKILL.md:1-4`) | agent-sdk/skills §Pre-approve tools |

스모크는 `dontAsk` 를 권한다. bypass 로 돌리면 "끝까지 갔다"만 알고, dontAsk 는 **어디서 막혔는지가 `permission_denials` 로 남는다** — #50 의 목적("다음 결정의 재료")에 더 맞다.

**인증 — 도구 사용 포함해서 된다.**

| 사실 | 출처 |
|---|---|
| `claude setup-token` 이 1년짜리 OAuth 토큰을 찍고 `CLAUDE_CODE_OAUTH_TOKEN` 으로 쓴다. Pro/Max/Team/Enterprise 필요. CI 용도 명시 | authentication §Generate a long-lived token |
| 이 토큰은 **모델 요청만** 한다 — Remote Control·claude.ai 커넥터는 불가, 로컬 MCP 는 됨 | 같은 절 |
| 우선순위: `ANTHROPIC_API_KEY` 가 있으면 `-p` 에선 **항상** 그 키가 이긴다(5순위 OAuth 토큰보다 위) | authentication §Authentication precedence |
| GitHub Actions 문서도 구독 인증을 `CLAUDE_CODE_OAUTH_TOKEN` 시크릿으로 안내 | github-actions §Manual setup |

도구(Bash·Read·Write…)는 러너 로컬에서 실행되고 모델 요청만 API 로 가므로 "모델 요청만" 제약에 안 걸린다. seungbin-dev 선례(`scripts/llm.py:33`, `.github/workflows/post-drafts.yml:113`)는 텍스트 전용이라 도구 사용은 이번이 첫 실측이다. **WebSearch 가 구독 토큰+Actions 에서 되는지는 문서에 명시가 없다(미검증)** — 안 되면 `permission_denials` 가 아니라 도구 오류로 보이고 모델은 WebFetch 로 우회할 것이다.

`ANTHROPIC_API_KEY` 시크릿을 같은 잡에 절대 같이 주지 말 것(위 우선순위로 API 과금으로 샌다).

## 3. 턴 · 타임아웃 · 비용 · 종료 코드

| 플래그/신호 | 의미 | 출처 |
|---|---|---|
| `--max-turns N` | print 모드 전용. 도구 사용 왕복 수 상한. 넘으면 **에러로 종료**, 결과 subtype `error_max_turns` | cli-reference, agent-loop §Turns and budget |
| `--max-budget-usd X` | print 모드 전용. 넘으면 `error_max_budget_usd`. 비용은 클라이언트 추정치. **구독 인증에서 이 값이 무슨 의미인지는 문서에 없다(미검증)** — 스모크엔 안 넣는다 | cli-reference, headless §Pipe data |
| 종료 코드 | 성공 0, 실패 non-zero. 잘못된 플래그는 실행 전 stderr. 실행 중 실패(인증 누락 등)는 **stdout 의 result** 로 나온다 | headless §Basic usage |
| SIGTERM | 143. `timeout` 래퍼로 죽이면 `timeout` 자신은 124 | headless §Stop a run with SIGTERM |
| 결과 subtype | `success` / `error_max_turns` / `error_max_budget_usd` / `error_during_execution` — 모든 subtype 에 `num_turns`·`total_cost_usd`·`session_id` | agent-loop §Handle the result |
| `--output-format stream-json --verbose` | 줄 단위 JSON 이벤트. 첫 줄이 `system/init`, 마지막이 `result` | headless §Stream responses, §Read session metadata |
| 구독 한도 | `claude -p` 가 exit 1 로 즉시 죽고 사유를 **stdout** 에 쓴다 | 선례 실측 `scripts/llm.py:21-24` |

턴 예산: 리서치(웹 10±)·후보 검색 2~3회·미리보기 이미지 Read 10±·IR 작성·fetch·render·재시도 ≤3(`SKILL.md:331`)·캡션·review → 50~80 도구 턴 추정. 스모크는 `--max-turns 100`, 벽시계는 `timeout 40m` + 잡 `timeout-minutes: 45`.

## 4. card-news 쪽 함정 — 헤드리스에서 막히거나 오작동하는 단계

| # | 단계 | 무슨 일이 생기나 | 근거 | 대응 |
|---|---|---|---|---|
| a | 스킬 등록 | `.claude/` 가 gitignore, 스킬은 `skill/` 에 있고 `~/.claude/skills` 심링크로만 등록 → 러너엔 없음, v2.1.274 는 에러 없이 평문 처리 | `.gitignore:17`, `SKILL.md:50-52` | 워크플로에서 심링크 생성 + init `skills` 게이트 |
| b | ① `cd "$(cd … && dirname "$(pwd -P)")" && npm run bootstrap` | 명령 치환이 든 복합 명령 — 부분 명령마다 allow 가 맞아야 하고, 파싱 못 하면 승인 요청 → dontAsk 에서 거부될 수 있다(미검증) | `SKILL.md:54-56`, permissions §Compound/Read-only | 프롬프트로 "이미 루트다, cd 생략" 지시. 거부돼도 `permission_denials` 로 보인다 |
| c | 구성 질문 | "물어봐도 되지만 답을 기다리지 않는다" — 헤드리스에선 `AskUserQuestion` 이 제거/거부되므로 기본값(8장·전부 사진)으로 간다. 무해 | `SKILL.md:11-20` | 프롬프트에 구성 명시 |
| d | ②-1 웹 리서치 | WebSearch/WebFetch 가 허용 안 되면 거부 → 숫자 없는 카피 | `SKILL.md:75-76` | 둘 다 allow |
| e | ②-3 Pexels | `PEXELS_API_KEY` 가 env 에도 `.env` 에도 없으면 `kind:"config"` 로 실패 | `scripts/photos.mjs:188-193`, `AGENTS.md:32` | 시크릿을 env 로 주입 |
| f | ②-4 미리보기 | `/tmp/c.json`·`/tmp/previews` 로 리다이렉트·쓰기, 이어서 이미지 Read — 작업 디렉터리 밖 | `SKILL.md:217-220`, permissions §Redirections | `--add-dir /tmp` |
| g | web-capture | Playwright headless shell 로 페이지 녹화, 다크 모드·스크롤 판정 등 실측 함정 다수 | `scripts/photos.mjs:248-299`, `AGENTS.md:74-75` | 스모크 범위에서 뺀다(전부 사진) |
| h | ⑤ 렌더 | `chromium-headless-shell` 채널로 띄움. 없으면 `internal`/설치 안내로 실패. 우분투는 시스템 라이브러리도 필요 | `scripts/render.mjs:25,507-509`, `AGENTS.md:33` | `npx playwright install --with-deps chromium --only-shell` |
| i | 폰트 | Pretendard 가 번들이고 글리프 판정은 fontkit cmap → **시스템 폰트 의존 없음**. 러너에 한글 폰트 설치 불필요 | `scripts/render.mjs:22`, `AGENTS.md:41,46-47` | 없음 |
| j | 영상 카드 합성 | 시스템 `ffmpeg` 필요, 설치 안내가 macOS(`brew`) 전용 | `scripts/compose.mjs:30`, `SKILL.md:315`, `AGENTS.md:71` | 스모크는 영상 0장. 영상 쓸 때 `apt-get install ffmpeg` |
| k | Node | `^24 \|\| >=26` 밖이면 각 스크립트가 `internal` 로 죽는다. AGENTS 의 PATH 안내는 macOS keg-only 전용 | `package.json:7-9`, `scripts/*.mjs` 첫 줄 검사, `AGENTS.md:25-29` | `actions/setup-node` 24 |
| l | ⑥ 재시도 | `font`·`internal` 은 "고치지 말고 사용자에게 보여라", 3회 초과면 멈춤 → 헤드리스에선 그 텍스트가 result 로 나오고 exit 0 일 수 있다 | `SKILL.md:329-332` | exit 코드 말고 산출물로 판정 |
| m | ⑧-1 `npm run review && open …` | 우분투의 `open` 은 macOS `open` 이 아니다. 스킬 스스로 "실패해도 무시"라 했지만, 복합 명령이라 `open` 부분이 allow 에 없으면 **명령 전체가 거부**돼 review.html 도 안 생길 수 있다 | `SKILL.md:371-380` | 프롬프트로 "`npm run review` 만, `open` 은 부르지 마라" |
| n | ⑧-2 사람의 결정 | 두 답(승인/재생성)을 기다린다 — 헤드리스엔 사람이 없다. 모델은 질문으로 턴을 끝내고 exit 0 | `SKILL.md:382-387`, 스파인 AD-16(`ARCHITECTURE-SPINE.md:131-135`) | **여기서 멈추는 게 정답.** 승인 대체는 다음 결정(#45) |
| o | ⑧-3 `npm run approve` | 부르면 `APPROVED.json` + `state/used-photos.json` 기록 — 사람 승인 없이 장부가 소진된다(AD-16·AD-13 위반) | `SKILL.md:400-415` | `--disallowedTools "Bash(npm run approve *)"` + 프롬프트 금지 |
| p | 산출물 | `output/*` 가 gitignore → 러너가 끝나면 사라진다 | `.gitignore:2` | `actions/upload-artifact` 로 `output/` 보관 |

## 스모크 명령 (card-news `.github/workflows/smoke.yml` 용)

앞 단계: `actions/checkout` → `actions/setup-node`(24) → `npm ci` → `npx playwright install --with-deps chromium --only-shell` → `npm install -g @anthropic-ai/claude-code` → 심링크. env: `CLAUDE_CODE_OAUTH_TOKEN`, `PEXELS_API_KEY`(시크릿), `TOPIC`(dispatch 입력).

```bash
mkdir -p .claude/skills && ln -sfn ../../skill .claude/skills/card-news
```

명령 한 줄:

```bash
timeout 40m claude -p "/card-news ${TOPIC} — 헤드리스 스모크다. 8장, 전부 사진(영상 카드 없음). 사람이 없으니 질문하지 말고 기본값으로 진행하라. 작업 디렉터리가 이미 저장소 루트이므로 ①의 cd 는 생략하고 npm run bootstrap --silent 부터 부른다. ⑧-1 은 npm run review --silent -- <덱 폴더> 까지만 하고 open 은 부르지 마라. npm run approve 는 절대 부르지 말고, 마지막 줄에 덱 폴더 경로와 '승인 대기' 를 출력하고 끝내라." --permission-mode dontAsk --permission-prompts none --allowedTools "Bash(npm run *)" "Bash(mkdir *)" "Bash(cp *)" "Read" "Write" "Edit" "Glob" "Grep" "WebSearch" "WebFetch" --disallowedTools "Bash(npm run approve *)" "Bash(git *)" --add-dir /tmp --max-turns 100 --output-format stream-json --verbose > claude.jsonl
```

뒤 단계(`if: always()`): `claude.jsonl`·`output/` 를 artifact 로 올리고 아래 신호를 요약.

## 실패 시 볼 신호

| 신호 | 어디서 | 뜻 |
|---|---|---|
| init 의 `skills`(또는 `slash_commands`)에 `card-news` 없음 | `jq 'select(.type=="system" and .subtype=="init") \| .skills'` | 심링크 단계 누락 — 이후는 평문 대화라 무의미. **첫 게이트** |
| exit 124 | `timeout` | 40분 초과(벽시계) |
| exit ≠0, result `subtype:"error_max_turns"` | 마지막 줄 | 턴 부족 — `num_turns` 보고 상향 |
| result 에 `limit`·`429`·`rate` | 마지막 줄 stdout | 구독 한도(선례와 같은 모양) |
| `api_retry` 의 `error:"authentication_failed"` / result 에 로그인 오류 | stream | 토큰 시크릿 누락·만료 |
| result 의 `permission_denials` 비어 있지 않음 | 마지막 줄 | 어느 명령이 막혔는지 목록 — allow 목록 보강 재료 |
| `npm run photos` 의 `kind:"config"` | tool_result | `PEXELS_API_KEY` 미주입 |
| `npm run render` 의 `kind:"internal"`+"chromium headless shell을 띄우지 못했다" | tool_result | playwright 설치/`--with-deps` 누락 |
| `Node v…는 package.json의 engines…` | tool_result | setup-node 버전 |
| **성공 판정(산출물)** | 파일 | `output/*/deck.json`·`photo-candidates.json`·`01.png`~`08.png`·`caption.txt`·`review.html` 존재, **`APPROVED.json` 없음**, `git diff --exit-code state/` 깨끗 |

exit 0 은 성공의 증거가 아니다 — ⑥ 3회 실패나 ⑧-2 질문도 exit 0 으로 끝난다(`SKILL.md:329-332,382-387`). 판정은 마지막 행(산출물)으로 한다.

## 가장 큰 리스크

**⑧ 이 구조적으로 사람을 요구한다(AD-16).** 헤드리스는 "review.html 까지"가 최대이고, 승인 대체·축소는 #45 의 다음 결정이다. 그 다음 리스크: 심링크를 빼먹으면 v2.1.274 가 **에러 없이** 평문으로 돌려 "도구를 안 쓰고 끝났다"가 스킬 문제처럼 보인다 — init `skills` 게이트가 필수.

## 미검증 (스모크 #50 이 확인)

1. WebSearch 가 구독 토큰+Actions 에서 되는지
2. ① 의 명령 치환 `cd` 가 dontAsk 에서 거부되는지(프롬프트로 우회했지만 모델이 그대로 칠 수 있다)
3. `ubuntu-latest` 에서 `--with-deps` 없이도 headless shell 이 뜨는지(넣었으니 확인만)
4. 8장 풀런의 실제 턴 수·소요 시간·구독 사용량
