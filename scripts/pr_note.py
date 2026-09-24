#!/usr/bin/env python3
"""원고 PR 이 열렸을 때 폰으로 가는 알림 한 통 — 무엇을, 언제까지, 어떻게 결정하나 (2026-09-24).

재료는 PR 본문 하나다. 본문이 이미 후보·원고·발행일을 다 싣고 있고(write_post.pr_body · open_thread_pr.sh),
/주제 N 도 본문을 진실로 읽는다(review_cmd). 알림이 따로 계산하면 둘이 어긋난다.
이모지 없이, 결정에 필요한 것만: 제목 → 채점·기한 → (Threads 는 본문 전문 / 블로그는 후보) → 버튼 뜻 → 링크.

사용 (auto-post.yml · review.yml 이 PR 을 연 직후 부른다):
  python3 scripts/pr_note.py https://github.com/…/pull/89
  python3 scripts/pr_note.py --selftest
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_cmd import CAND_RE  # noqa: E402

RULE = "―" * 12
ON_RE = re.compile(r"\*\*발행 예정: \d{4}-0?(\d+)-0?(\d+)\((.)\) 09:00 KST\*\*")
CODE_RE = re.compile(r"^```\n(.*?)\n```$", re.S | re.M)
FIELD_RE = re.compile(r"^- (제목|요약|채점): (.*)$", re.M)


def thread(title: str, body: str, failed: bool) -> list[str]:
    derived = "의 파생" in body.split("\n", 1)[0]
    topic = title.removeprefix("thread: ").removeprefix("c-").replace("-", " ")
    on = ON_RE.search(body)
    when = f"{on.group(1)}/{on.group(2)}({on.group(3)}) 09:00" if on else "?"
    code = CODE_RE.search(body)
    parts = [p.strip() for p in re.split(r"^---$", code.group(1), flags=re.M)] if code else []
    out = [f"[Threads {'파생' if derived else '논평'}] 결정 필요", topic, "",
           f"채점: {'탈락 — Merge 해도 안 나간다. Close 하면 된다' if failed else '통과'}",
           f"발행: {when}",
           "기한: 발행 시각 전에 Merge. 안 하면 안 나간다", "", RULE]
    for i, p in enumerate(parts, 1):
        out += [f"({i}/{len(parts)})", p, ""]
    out += [RULE, "", "Merge = 이대로 발행", "Close = 버리기"]
    return out


def blog(body: str, failed: bool) -> list[str]:
    f = dict(FIELD_RE.findall(body))
    verdict = f.get("채점", "").split(" ", 1)[0]
    failed = failed or verdict == "FAIL"
    out = ["[블로그] 결정 필요", f.get("제목", "(제목 없음)")]
    if f.get("요약"):
        out.append(f["요약"])
    out += ["", f"채점: {'탈락 — /주제 N · /변경 으로 다시 쓰거나 Close' if failed else '통과'}",
            "기한: 일요일 슬롯. 두 슬롯 지나면 자동 반려"]
    cands = [(m.group(1), m.group(2), "← 이번 원고" in m.group(0)) for m in CAND_RE.finditer(body)]
    if cands:
        out += ["", "주제 후보"] + [f"{n}. {t}{'  (지금 원고)' if cur else ''}" for n, t, cur in cands]
    out += ["", "Merge = 이대로 게시 (바로 나간다)", "Close = 버리기",
            "댓글 /주제 N = N번 주제로 다시 쓰기", "댓글 /변경 <한 줄> = 지시대로 고쳐 쓰기"]
    return out


def note(pr: dict) -> str:
    labels = {lb["name"] for lb in pr.get("labels", [])}
    failed = "탈락" in labels
    if "원고:thread" in labels:
        lines = thread(pr["title"], pr["body"], failed)
    elif "원고:blog" in labels:
        lines = blog(pr["body"], failed)
    else:
        lines = ["[원고] 결정 필요", pr["title"], "", "Merge = 승인", "Close = 버리기"]
    return "\n".join(lines + [pr["url"]])


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    url = argv[1]
    try:
        raw = subprocess.run(["gh", "pr", "view", url, "--json", "title,body,labels,url"],
                             capture_output=True, text=True, check=True).stdout
        print(note(json.loads(raw)))
    except Exception as e:  # 알림 조립이 깨져도 링크는 간다 — 결정할 PR 이 있다는 사실이 본문보다 중요하다
        print(f"원고 PR — 결정 필요 (알림 조립 실패: {e.__class__.__name__})\n{url}")
    return 0


def selftest() -> int:
    t = note({"title": "thread: c-radicle-보안-취약점", "url": "U", "labels": [{"name": "원고:thread"}], "body":
              "## Threads 원고 — 다이제스트 논평 (2026-09-25 발행)\n\n**발행 예정: 2026-09-25(금) 09:00 KST** — merge\n\n"
              "```\n첫 글\n둘째 줄\n---\n둘째 글\n\nhttps://x\n```\n\n체인은 `---` 로 나뉜다."})
    assert t.startswith("[Threads 논평] 결정 필요\nradicle 보안 취약점\n"), t
    assert "발행: 9/25(금) 09:00" in t and "채점: 통과" in t, t
    assert "(1/2)\n첫 글\n둘째 줄\n" in t and "(2/2)\n둘째 글\n\nhttps://x\n" in t and t.endswith("\nU"), t

    d = note({"title": "thread: slug-x", "url": "U", "labels": [{"name": "원고:thread"}, {"name": "탈락"}], "body":
              "## Threads 원고 — 블로그 https://g/pull/62 의 파생 (2026-09-23 발행)\n\n```\n글\n```"})
    assert d.startswith("[Threads 파생]") and "채점: 탈락" in d and "(1/1)\n글" in d, d

    b = note({"title": "post: s", "url": "U", "labels": [{"name": "원고:blog"}], "body":
              "## 주제 후보 — 검수자가 고른다\n\n1. **첫 주제**  ← 이번 원고  \n   https://a\n2. **둘째**  \n   https://b\n\n"
              "## 원고\n\n- 제목: 글 제목\n- 요약: 한 줄 요약\n- 채점: PASS — 규칙 준수\n"})
    assert b.startswith("[블로그] 결정 필요\n글 제목\n한 줄 요약\n"), b
    assert "1. 첫 주제  (지금 원고)\n2. 둘째\n" in b and "채점: 통과" in b and "/주제 N" in b, b
    assert "탈락" in note({"title": "p", "url": "U", "labels": [{"name": "원고:blog"}], "body": "- 채점: FAIL — x"})
    assert not any(ord(c) > 0x1F000 for c in t + d + b), "이모지 금지"
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
