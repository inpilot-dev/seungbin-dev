#!/usr/bin/env python3
"""검수 PR 댓글 한 줄을 명령으로 풀어 write_post 를 다시 돌린다 (docs/adr/0001).

    /변경 <지시 한 줄>         같은 주제·출처로 재생성. 지시는 프롬프트에 '반드시 반영' 으로 들어간다
    /주제 N                    PR 본문 맨 위 후보 N번으로 재생성
    /주제 <URL> [제목]         후보 밖 주제. 출처 URL 이 없으면 거부한다 — 출처 없는 글은 만들지 않는다

주제·출처는 PR 브랜치에 있는 원고의 frontmatter(`topic:`·`sources:`)에서 읽는다. 후보 번호는 PR 본문에서
읽는다 — 다이제스트는 매일 바뀌어 "오늘의 3번" 은 토요일의 3번과 다를 수 있다. 본문이 진실이다.

사용 (review.yml 이 부른다):
  python3 scripts/review_cmd.py run --comment "/변경 훅을 수치로" --pr-body pr.md --mdx cur.mdx --onto post/foo
  python3 scripts/review_cmd.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CMD_RE = re.compile(r"^\s*/(변경|주제)\b[ \t]*(.*?)\s*$", re.S)
CAND_RE = re.compile(r"^(\d+)\. \*\*(.+?)\*\*(?:  ← 이번 원고)?[ \t]*\n[ \t]+(https?://\S+)", re.M)
URL_RE = re.compile(r"https?://\S+")


def parse(comment: str) -> dict | None:
    """댓글 첫 줄이 명령이 아니면 None. 명령이면 {"cmd": ..., ...}."""
    m = CMD_RE.match(comment or "")
    if not m:
        return None
    cmd, rest = m.group(1), m.group(2).strip()
    if cmd == "변경":
        return {"cmd": "변경", "instruction": rest} if rest else {"cmd": "변경", "error": "/변경 뒤에 지시 한 줄이 필요하다 (예: /변경 훅을 수치로 시작)"}
    if re.fullmatch(r"\d+", rest):
        return {"cmd": "주제", "pick": int(rest)}
    u = URL_RE.search(rest)
    if u:
        title = (rest[:u.start()] + rest[u.end():]).strip(" -—·|")
        return {"cmd": "주제", "url": u.group(0).rstrip(".,;:)"), "title": title}
    return {"cmd": "주제", "error": "/주제 는 후보 번호(/주제 3) 또는 출처 URL(/주제 https://… 제목) 이어야 한다 — 출처 없는 글은 만들지 않는다"}


def candidates_from_body(body: str) -> list[tuple[str, str]]:
    return [(t, u) for _, t, u in CAND_RE.findall(body or "")]


MARK = "  ← 이번 원고"


def remark(body: str, url: str, title: str) -> str:
    """`/주제` 재생성 뒤 PR 본문의 `← 이번 원고` 를 새 출처로 옮긴다. 후보 밖 출처(/주제 URL)면 목록 끝에 한 줄 붙인다.
    2026-09-18 실측: 표시가 옛 후보에 남아 write_post.queued_urls() 가 새 출처를 몰랐고, 같은 날 논평(#59)이
    블로그 #42 가 /주제 3 으로 바꾼 출처를 또 골랐다."""
    body = body.replace(MARK, "")
    for t, u in candidates_from_body(body):
        if u == url:
            return body.replace(f"**{t}**", f"**{t}**{MARK}", 1)
    head = "## 원고"
    line = f"- **{title or url}**{MARK}  \n   {url}\n\n"
    return body.replace(head, line + head, 1) if head in body else body + "\n" + line


def topic_sources(mdx: str) -> tuple[str, list[str]]:
    """frontmatter 의 topic·sources. topic 이 없는 옛 원고는 title 로 대신한다."""
    head = mdx.split("\n---", 2)[0] if mdx.startswith("---") else ""
    topic = re.search(r'^topic:\s*(".*")\s*$', head, re.M)
    srcs = re.search(r"^sources:\s*(\[.*\])\s*$", head, re.M)
    title = re.search(r'^title:\s*"(.*)"\s*$', head, re.M)
    t = json.loads(topic.group(1)) if topic else (title.group(1) if title else "")
    return t, (json.loads(srcs.group(1)) if srcs else [])


def build_argv(cmd: dict, pr_body: str, mdx: str, slug: str, onto: str, replace: str = "") -> list[str] | str:
    """write_post.main 에 줄 argv, 또는 사람에게 돌려줄 오류 문장. replace = 브랜치의 옛 원고 경로."""
    if cmd.get("error"):
        return cmd["error"]
    tail = ["--publish", "--onto", onto] + (["--replace", replace] if replace else [])
    if cmd["cmd"] == "변경":
        topic, srcs = topic_sources(mdx)
        if not (topic and srcs):
            return "이 PR 의 원고에서 주제·출처를 못 읽었다 — /주제 N 으로 다시 만들어라"
        argv = ["", "--topic", topic]
        for s_ in srcs:
            argv += ["--source", s_]
        return argv + ["--instruction", cmd["instruction"], "--slug", slug] + tail
    if "pick" in cmd:
        cands = candidates_from_body(pr_body)
        if not 1 <= cmd["pick"] <= len(cands):
            return f"/주제 {cmd['pick']}: 후보는 1~{len(cands)}번이다"
        t, u = cands[cmd["pick"] - 1]
        return ["", "--topic", t, "--source", u] + tail
    return ["", "--topic", cmd["title"] or cmd["url"], "--source", cmd["url"]] + tail


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "plan"], help="plan 은 argv 만 출력(테스트용)")
    ap.add_argument("--comment", required=True)
    ap.add_argument("--pr-body", required=True, help="PR 본문 파일")
    ap.add_argument("--mdx", required=True, help="PR 브랜치의 원고 내용을 받아 둔 로컬 파일(없으면 빈 파일)")
    ap.add_argument("--mdx-path", default="", help="그 원고의 브랜치 안 경로(content/x.mdx) — slug 가 바뀌면 지운다")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--onto", required=True, help="PR 브랜치")
    a = ap.parse_args(argv[1:])
    cmd = parse(a.comment)
    if not cmd:
        print("명령이 아니다 — 무시", file=sys.stderr)
        return 0
    mdx = Path(a.mdx).read_text(encoding="utf-8") if Path(a.mdx).exists() else ""
    plan = build_argv(cmd, Path(a.pr_body).read_text(encoding="utf-8"), mdx, a.slug, a.onto, a.mdx_path)
    if isinstance(plan, str):
        print(f"REJECT: {plan}")
        return 3
    print("ARGV:", json.dumps(plan[1:], ensure_ascii=False))
    if a.mode == "plan":
        return 0
    import write_post  # noqa: E402  LLM 호출은 여기서만
    rc = write_post.main(plan)
    if cmd["cmd"] == "주제" and rc in (0, 1):   # 브랜치가 새 원고로 바뀌었다 — 본문 표시도 따라간다(워크플로가 gh pr edit)
        src, topic = plan[plan.index("--source") + 1], plan[plan.index("--topic") + 1]
        Path(a.pr_body).write_text(remark(Path(a.pr_body).read_text(encoding="utf-8"), src, topic), encoding="utf-8")
    return rc


def selftest() -> int:
    assert parse("/변경 훅을 수치로 시작") == {"cmd": "변경", "instruction": "훅을 수치로 시작"}
    assert parse("  /변경\n") == {"cmd": "변경", "error": parse("/변경")["error"]} and "지시" in parse("/변경")["error"]
    assert parse("/주제 3") == {"cmd": "주제", "pick": 3}
    assert parse("/주제 https://ex.com/p?a=1. 새 제목") == {"cmd": "주제", "url": "https://ex.com/p?a=1", "title": "새 제목"}
    assert parse("/주제 아무 말") == {"cmd": "주제", "error": parse("/주제 아무 말")["error"]}
    assert parse("LGTM /변경 아님") is None and parse("") is None and parse(None) is None
    body = ("## 주제 후보 — 검수자가 고른다\n\n1. **첫 항목**  ← 이번 원고  \n   https://ex.com/a\n"
            "2. **둘째 항목**  \n   https://ex.com/c\n\n## 원고\n")
    assert candidates_from_body(body) == [("첫 항목", "https://ex.com/a"), ("둘째 항목", "https://ex.com/c")]
    mdx = '---\ntopic: "X 크롤링은 되는가"\nsources: ["docs/a.md", "https://ex.com/z"]\ntitle: "T — U"\n---\n본문\n'
    assert topic_sources(mdx) == ("X 크롤링은 되는가", ["docs/a.md", "https://ex.com/z"])
    assert topic_sources('---\ntitle: "옛 글"\n---\n') == ("옛 글", [])
    argv = build_argv(parse("/변경 더 짧게"), body, mdx, "x-crawl", "post/x-crawl", "drafts/x-crawl.mdx")
    assert argv[1:] == ["--topic", "X 크롤링은 되는가", "--source", "docs/a.md", "--source", "https://ex.com/z",
                        "--instruction", "더 짧게", "--slug", "x-crawl", "--publish", "--onto", "post/x-crawl",
                        "--replace", "drafts/x-crawl.mdx"], argv
    assert build_argv(parse("/주제 2"), body, mdx, "s", "b")[1:] == ["--topic", "둘째 항목", "--source", "https://ex.com/c", "--publish", "--onto", "b"]
    assert "1~2번" in build_argv(parse("/주제 7"), body, mdx, "s", "b")
    assert build_argv(parse("/주제 https://ex.com/n 새 주제"), body, mdx, "s", "b")[1:3] == ["--topic", "새 주제"]
    assert "출처" in build_argv(parse("/변경 x"), body, "", "s", "b")   # 원고에서 주제·출처를 못 읽으면 거부
    # /주제 뒤 표시 이동 — write_post.queued_urls() 가 읽는 모양(`← 이번 원고` 다음 줄 URL)이어야 한다
    import re as _re
    moved = remark(body, "https://ex.com/c", "둘째 항목")
    assert moved.count(MARK) == 1 and "2. **둘째 항목**  ← 이번 원고" in moved, moved
    assert _re.findall(r"← 이번 원고\s*\n\s*(https?://\S+)", moved) == ["https://ex.com/c"]
    free = remark(body, "https://ex.com/n", "새 주제")
    assert _re.findall(r"← 이번 원고\s*\n\s*(https?://\S+)", free) == ["https://ex.com/n"], free
    assert candidates_from_body(free) == candidates_from_body(body)   # 후보 번호는 안 바뀐다
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
