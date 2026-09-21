#!/usr/bin/env python3
"""주간 뉴스레터 원고 한 통을 조립해 검수 PR 로 올린다 (증분 4 — 지도 #52 「뉴스레터 한 통의 모양」).

**LLM 을 부르지 않는다.** 이 통에 들어가는 문장은 전부 이미 채점을 통과한 것이다 —
글 요약은 각 글 frontmatter 의 `description`(그 글이 통과할 때 같이 통과했다), 읽을거리 줄은
다이제스트 수집기가 쓴 제목이다. 새로 짓는 문장이 없으니 채점할 것도, 재시도 루프도, 비용도 없다.
  # ponytail: 조립기다. 인트로를 모델에게 쓰게 하려면 llm.ask 한 줄이면 되지만, 지금 통에서
  # 사람이 쓴 문장은 0 이고 그래도 읽을 값이 있다. 열람률이 "목록처럼 읽힌다" 고 말하면 그때 붙인다.

모양 (지도 #52 결정, 2026-09-22):
  ① 그 주에 나간 글 — 제목 · 요약 · 링크. **0편이면 통을 만들지 않는다**(발행할 게 없다).
     "나간" = 그 `원고:blog` PR 이 **merge 된** 것이다. frontmatter `date`(생성일)로 자르지 않는다 — posts() 참조.
  ② 읽고 안 쓴 것 — 그 주 블로그 원고 PR 본문의 후보 중 고르지 않은 것. 이미 `on_topic` 판정을
     통과한 것들이라 여기서 LLM 을 다시 부르지 않는다. gh 가 죽으면 이 칸만 빠진다.

발행 시각: `drafts/newsletter/<ISO 주차>.md`·`.html` 이 main 에 있으면 publish-queue 가 **금 09:00 KST**
에 낸다. 주차는 **다음 금요일**의 ISO 주차다 — 일요일 슬롯(20:00)에 승인해도 그 주 금요일은 이미
지났기 때문이다. 제목은 첫 `# ` 줄이다(publish-queue.yml 의 `grep -m1 '^# '`).

사용:
  python3 scripts/write_newsletter.py                  # 최근 승인된 글 → 다음 금요일 주차, PR 까지
  python3 scripts/write_newsletter.py --dry-run        # 파일만 쓰고 git 은 안 건드린다 (gh 조회는 한다)
  python3 scripts/write_newsletter.py --now 2026-10-04T11:00:00 --dry-run
  python3 scripts/write_newsletter.py --selftest
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_cmd as rc  # noqa: E402
import write_post as wp  # noqa: E402

ROOT = wp.ROOT
OUT = ROOT / "drafts" / "newsletter"
SITE = "https://inpilot.dev"
WINDOW = 7          # 일. 「읽고 안 쓴 것」 후보를 보는 창
LOOKBACK = 14       # 일. 글을 찾는 창 — 넉넉히 보고, 이미 실린 글은 sent_urls() 로 뺀다 (posts() 참조)
MAX_READS = 5       # 「읽고 안 쓴 것」 줄 수. 더 넣으면 내 글이 목록에 묻힌다
# Resend 가 브로드캐스트에서 치환하는 자리표시. 대량 메일에 수신 거부가 없으면 안 된다.
# ⚠️ 아직 실제 브로드캐스트를 보낸 적이 없다 — 첫 발송에서 치환이 되는지 눈으로 확인할 것.
# 치환이 안 되면 구독자에게 중괄호가 그대로 보인다(0명일 때 타는 /emails 경로는 치환하지 않는다).
UNSUB = "{{{RESEND_UNSUBSCRIBE_URL}}}"


def target_week(today: date) -> tuple[str, date]:
    """(<ISO 주차>, 그 주 금요일) — 오늘을 뺀 다음 금요일. 지난 금요일을 겨냥하면 영영 안 나간다."""
    fri = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
    return fri.strftime("%G-W%V"), fri


def sent_urls() -> set[str]:
    """이미 뉴스레터 원고에 실린 글 URL — main 의 drafts/newsletter/*.md 전부에서."""
    return {u for f in OUT.glob("*.md")
            for u in re.findall(rf"{re.escape(SITE)}/posts/[\w-]+", f.read_text(encoding="utf-8"))}


def posts(now: datetime) -> list[dict]:
    """최근 LOOKBACK 일 안에 **merge 된** `원고:blog` PR 이 올린 글 중 아직 안 실린 것 — 새 글부터.

    게시 = merge 다(블로그는 승인 즉시 나간다, CONTEXT.md). `dashboard.py` 가 게시를 세는 것과 같은 정의다.
    frontmatter `date` 로 자르면 안 된다 (2026-09-22, 첫 구현이 그렇게 했다): `date` 는 **생성일**(토 06:00)
    이고 승인은 일 20:00 이다. 그 일요일 11:00 실행 땐 글이 아직 main 에 없고, 다음 일요일 실행 땐 `date` 가
    7일 창 밖이다 → 정상 흐름의 글이 **한 번도 안 실리고** 매주 "새 글 0편" 으로 exit 0 했다.

    창을 7일로 꼭 맞추지 않는 이유: cron 이 빠지거나 손으로 하루 늦게 돌리면 지난 슬롯의 승인이 창 밖으로
    나간다. 넉넉히 보고 이미 실린 글을 빼면 언제 돌려도 같은 답이 나온다.
    gh 가 죽으면 **죽는다** — 여기서 빈 목록을 돌려주면 "새 글 0편" 과 구별이 안 된다(조용한 실패)."""
    since = now - timedelta(days=LOOKBACK)
    r = subprocess.run(["gh", "pr", "list", "--state", "merged", "--label", "원고:blog", "--limit", "50",
                        "--search", f"merged:>={since - timedelta(days=1):%Y-%m-%d}",   # 검색은 날짜 단위라 하루 넉넉히
                        "--json", "number,mergedAt,files"],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise SystemExit(f"merge 된 블로그 원고 PR 조회 실패 — 뉴스레터를 만들지 않는다: {r.stderr.strip()[:300]}")
    done, got = sent_urls(), []
    for pr in json.loads(r.stdout or "[]"):
        merged = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
        if not since <= merged <= now:
            continue
        for path in (f["path"] for f in pr.get("files", []) if re.fullmatch(r"content/[^/]+\.mdx", f["path"])):
            f = ROOT / path
            if not f.exists():          # merge 뒤 지워진 글(revert) — 2026-09-14 #16·#18 이 실제로 그랬다
                continue
            meta, _ = wp.grade.split_front(f.read_text(encoding="utf-8"))
            url = f"{SITE}/posts/{meta.get('slug') or f.stem}"
            if url in done:
                continue
            done.add(url)               # 같은 글을 두 PR 이 건드렸어도 한 번만
            got.append({"title": meta.get("title", f.stem), "desc": meta.get("description", ""),
                        "url": url, "merged": merged})
    return sorted(got, key=lambda p: p["merged"], reverse=True)


def reads(frm: date, limit: int = MAX_READS) -> list[tuple[str, str]]:
    """그 주 블로그 원고 PR 본문의 후보 중 **고르지 않았고 아직 안 쓴** 것 → [(제목, URL)].
    gh 가 없거나 실패하면 빈 목록 — 이 칸이 빠져도 통은 나간다(글이 본문이다)."""
    try:
        r = subprocess.run(["gh", "pr", "list", "--state", "all", "--label", "원고:blog",
                            "--limit", "30", "--json", "body,createdAt"],
                           cwd=ROOT, capture_output=True, text=True, timeout=30)
        prs = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else []
    except Exception as e:  # noqa: BLE001
        print(f"원고 PR 조회 실패 — 「읽고 안 쓴 것」 없이 진행: {e}", file=sys.stderr)
        return []
    written = wp.written_urls()
    out: list[tuple[str, str]] = []
    seen = set()
    for pr in prs:
        if str(pr.get("createdAt", ""))[:10] < frm.isoformat():
            continue
        body = pr.get("body") or ""
        # 고른 것은 `← 이번 원고` 다음 줄의 URL 이다 (write_post.queued_urls 와 같은 모양)
        chosen = {wp.norm_url(u) for u in re.findall(r"← 이번 원고\s*\n\s*(https?://\S+)", body)}
        for title, url in rc.candidates_from_body(body):
            n = wp.norm_url(url)
            if n in chosen or n in written or n in seen or re.fullmatch(r"\(.*\)", title.strip()):
                continue
            seen.add(n)
            out.append((title, url))
            if len(out) >= limit:
                return out
    return out


def render_md(subject: str, span: str, ps: list[dict], rs: list[tuple[str, str]]) -> str:
    """text 판. publish-queue 가 첫 `# ` 줄을 제목으로 읽는다 — 그 줄이 하나뿐이어야 한다."""
    lines = [f"# {subject}", "", f"{span} · 새 글 {len(ps)}편", ""]
    for p in ps:
        lines += [f"■ {p['title']}", p["desc"], p["url"], ""]
    if rs:
        lines += ["── 읽고 안 쓴 것 ──", ""]
        lines += [f"· {t}\n  {u}" for t, u in rs] + [""]
    lines += ["──", f"{SITE} · 구독 해지: {UNSUB}", ""]
    return "\n".join(lines)


def render_html(subject: str, span: str, ps: list[dict], rs: list[tuple[str, str]]) -> str:
    """html 판. 인라인 스타일만 — 메일 클라이언트는 <style> 을 자주 버린다. 의존성 0."""
    e = html.escape
    a = "color:#0b5fff;text-decoration:none"
    out = [f'<div style="max-width:600px;margin:0 auto;padding:24px 16px;'
           f'font:16px/1.7 -apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;color:#1a1a1a">',
           f'<h1 style="font-size:20px;line-height:1.4;margin:0 0 4px">{e(subject)}</h1>',
           f'<p style="color:#666;font-size:13px;margin:0 0 28px">{e(span)} · 새 글 {len(ps)}편</p>']
    for p in ps:
        out += [f'<div style="margin:0 0 28px">',
                f'<a href="{e(p["url"])}" style="{a};font-size:17px;font-weight:600">{e(p["title"])}</a>',
                f'<p style="margin:6px 0 0;color:#444">{e(p["desc"])}</p>', "</div>"]
    if rs:
        out += ['<hr style="border:0;border-top:1px solid #e5e5e5;margin:32px 0 20px">',
                '<p style="font-size:13px;color:#666;margin:0 0 12px">읽고 안 쓴 것</p>', "<ul style='padding-left:18px;margin:0'>"]
        out += [f'<li style="margin:0 0 8px"><a href="{e(u)}" style="{a}">{e(t)}</a></li>' for t, u in rs]
        out.append("</ul>")
    out += ['<hr style="border:0;border-top:1px solid #e5e5e5;margin:32px 0 16px">',
            f'<p style="font-size:12px;color:#888;margin:0">'
            f'<a href="{SITE}" style="color:#888">inpilot.dev</a> · '
            f'<a href="{UNSUB}" style="color:#888">구독 해지</a></p>', "</div>"]
    return "\n".join(out) + "\n"


def pr_body(week: str, fri: date, span: str, ps: list[dict], rs: list[tuple[str, str]]) -> str:
    out = [f"## 뉴스레터 원고 — {week}", "",
           f"**발행 예정: {fri:%Y-%m-%d}(금) 09:00 KST** — merge 하면 발행 대기, 그 시각에 publish-queue 가 낸다.",
           f"그 시각까지 결정이 없으면 그 주는 보류(안 나간다).", "",
           f"- 창: {span} · 새 글 {len(ps)}편 · 읽을거리 {len(rs)}줄",
           "- 채점 없음 — **새로 지은 문장이 없다.** 요약은 각 글 frontmatter 의 `description`(그 글이 "
           "통과할 때 같이 통과한 것), 읽을거리는 다이제스트가 쓴 제목이다", "",
           "## 들어간 글", ""]
    out += [f"- [{p['title']}]({p['url']})" for p in ps]
    if rs:
        out += ["", "## 읽고 안 쓴 것", ""] + [f"- [{t}]({u})" for t, u in rs]
    out += ["", "## 검수", "",
            "- **승인** = merge → 발행 대기", "- **반려** = close + 사유 한 줄",
            "- **변경** = 이 PR 브랜치의 `.md`·`.html` 을 직접 고치면 된다 — 조립기라 재생성 명령이 없다",
            "", "⚠️ 첫 발송이면 수신 거부 링크가 실제로 치환되는지 받은 메일에서 확인할 것 "
            f"(`{UNSUB}` — Resend 가 브로드캐스트에서만 치환한다).", "",
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)"]
    return "\n".join(out)


def open_pr(week: str, files: list[Path], body: str) -> str:
    """브랜치 → 커밋 → push → PR. write_post.publish 를 안 쓰는 이유: 저쪽은 `post/<슬러그>` 브랜치에
    파일 하나를 올린다. 여기는 두 개(.md·.html)고 브랜치 이름도 다르다."""
    base = wp.git("rev-parse", "--abbrev-ref", "HEAD")
    branch = f"newsletter/{week}"
    wp.git("checkout", "-b", branch)
    try:
        wp.ensure_labels()
        for f in files:
            wp.git("add", str(f.relative_to(ROOT)))
        wp.git("commit", "-m", f"newsletter: {week} 원고 (조립 · LLM 없음)" + wp.TRAILER)
        wp.git("push", "-u", "origin", branch)
        return subprocess.run(["gh", "pr", "create", "--title", f"newsletter: {week}",
                               "--body", body, "--label", "원고:newsletter"],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    finally:
        wp.git("checkout", base)


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser(description="주간 뉴스레터 원고 조립")
    ap.add_argument("--now", help="ISO 시각 또는 YYYY-MM-DD (기본 지금). 시간대 없으면 KST — dashboard.py 와 같은 규칙")
    ap.add_argument("--dry-run", action="store_true", help="파일만 쓰고 git 은 안 건드린다 (gh 조회는 한다)")
    a = ap.parse_args(argv[1:])
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(wp.KST)
    now = (now if now.tzinfo else now.replace(tzinfo=wp.KST)).astimezone(wp.KST)
    today = now.date()
    week, fri = target_week(today)

    if (OUT / f"{week}.md").exists():
        # 같은 주차를 두 번 만들면 브랜치도 PR 도 부딪힌다. 다시 만들려면 그 파일을 지워라.
        print(f"{week}: 이미 원고가 있다 ({OUT.name}/{week}.md) — 만들지 않는다")
        return 0

    ps = posts(now)
    if not ps:
        print(f"최근 {LOOKBACK}일 안에 승인(merge)됐고 아직 안 실린 글 0편 — 뉴스레터를 만들지 않는다(그 주는 안 나간다)")
        return 0
    frm = today - timedelta(days=WINDOW - 1)
    days = sorted(p["merged"].astimezone(wp.KST).date() for p in ps)   # 실린 글의 승인일 — 창이 아니라 사실을 적는다
    span = f"{days[0]:%m/%d}" + (f"~{days[-1]:%m/%d}" if days[-1] != days[0] else "")
    # 글 제목엔 대개 `본론 — 부연` 이 붙어 있다. 그대로 쓰면 줄표가 둘인 메일 제목이 되고
    # 받은편지함에서 뒤가 잘린다 — 앞 토막만 쓴다 (제목 전문은 본문 첫 줄에 그대로 있다)
    subject = f"이번 주 inpilot.dev — {ps[0]['title'].split(' — ')[0]}"
    rs = reads(frm)

    OUT.mkdir(parents=True, exist_ok=True)
    md, htm = OUT / f"{week}.md", OUT / f"{week}.html"
    md.write_text(render_md(subject, span, ps, rs), encoding="utf-8")
    htm.write_text(render_html(subject, span, ps, rs), encoding="utf-8")
    print(f"{week} (발행 {fri:%m/%d} 금): 글 {len(ps)}편 · 읽을거리 {len(rs)}줄 → {md.relative_to(ROOT)}")
    if a.dry_run:
        print("--dry-run: PR 안 엶")
        return 0
    print("PR:", open_pr(week, [md, htm], pr_body(week, fri, span, ps, rs)))
    return 0


def selftest() -> int:
    import tempfile
    global OUT, ROOT
    # 다음 금요일 — 오늘이 금요일이면 다음 주 금요일이다(지난 금요일을 겨냥하면 영영 안 나간다)
    assert target_week(date(2026, 9, 27)) == ("2026-W40", date(2026, 10, 2))   # 일
    assert target_week(date(2026, 9, 28)) == ("2026-W40", date(2026, 10, 2))   # 월
    assert target_week(date(2026, 10, 2)) == ("2026-W41", date(2026, 10, 9))   # 금 → 다음 주
    assert target_week(date(2026, 10, 1)) == ("2026-W40", date(2026, 10, 2))   # 목 → 내일
    for d in (date(2026, 9, 27), date(2026, 12, 28), date(2027, 1, 1)):        # 연말 ISO 주차
        w, f = target_week(d)
        assert f.weekday() == 4 and f > d and w == f.strftime("%G-W%V"), (d, w, f)

    utc = lambda s: datetime.fromisoformat(s + "+00:00")  # noqa: E731
    ps = [{"title": "압축이 과정을 지웠다", "desc": "요약이 코드를 삼켰다.", "url": "https://inpilot.dev/posts/a", "merged": utc("2026-09-27T11:10:00")},
          {"title": "429 는 무료의 값이다", "desc": "인증 없는 경로는 최신이 아니다.", "url": "https://inpilot.dev/posts/b", "merged": utc("2026-09-23T03:00:00")}]
    rs = [("안 쓴 소재 <하나>", "https://ex.com/1")]
    m = render_md("이번 주 inpilot.dev — 압축이 과정을 지웠다", "09/15~09/21", ps, rs)
    # publish-queue 는 `grep -m1 '^# '` 로 제목을 읽는다 — 그런 줄이 딱 하나여야 엉뚱한 제목이 안 나간다
    assert [ln for ln in m.splitlines() if ln.startswith("# ")] == ["# 이번 주 inpilot.dev — 압축이 과정을 지웠다"], m
    assert "■ 압축이 과정을 지웠다" in m and "https://inpilot.dev/posts/b" in m and UNSUB in m, m
    assert m.index("압축이 과정을 지웠다\n") < m.index("429 는")        # 새 글이 위
    h = render_html("제목 & <태그>", "09/15~09/21", ps, rs)
    assert "제목 &amp; &lt;태그&gt;" in h and "안 쓴 소재 &lt;하나&gt;" in h, h   # 이스케이프
    assert "<script" not in h and h.count("<div") == h.count("</div>"), h
    assert UNSUB in h

    # 글 0편이면 파일도 PR 도 없다
    saved_root, ROOT = ROOT, Path(tempfile.mkdtemp())
    OUT = ROOT / "drafts" / "newsletter"
    real_posts, real_reads = globals()["posts"], globals()["reads"]
    globals()["posts"] = lambda now: []                                        # noqa: E731
    globals()["reads"] = lambda frm, limit=MAX_READS: []                       # noqa: E731
    assert main(["", "--now", "2026-09-27", "--dry-run"]) == 0 and not OUT.exists()
    # 글이 있으면 두 파일. 같은 주차를 두 번 돌리면 안 덮는다 — 브랜치·PR 이 부딪힌다
    globals()["posts"] = lambda now: ps                                        # noqa: E731
    globals()["reads"] = lambda frm, limit=MAX_READS: rs                       # noqa: E731
    assert main(["", "--now", "2026-10-04T11:00:00", "--dry-run"]) == 0
    assert (OUT / "2026-W41.md").exists() and (OUT / "2026-W41.html").exists()
    assert "09/23~09/27 · 새 글 2편" in (OUT / "2026-W41.md").read_text(encoding="utf-8")   # 창이 아니라 실린 글의 승인일(KST)
    (OUT / "2026-W41.md").write_text("표시", encoding="utf-8")
    assert main(["", "--now", "2026-10-04T11:00:00", "--dry-run"]) == 0
    assert (OUT / "2026-W41.md").read_text(encoding="utf-8") == "표시"
    globals()["posts"], globals()["reads"] = real_posts, real_reads

    # posts(): **정상 주간 흐름의 글이 실려야 한다** — 토 06:00 생성(date=9/26) · 일 9/27 20:10 KST 승인.
    # 첫 구현은 frontmatter date 로 창을 잘라 이 글을 어느 일요일에도 못 실었다(2026-09-22 발견). 그 회귀를 막는다
    (OUT / "2026-W41.md").unlink(); (OUT / "2026-W41.html").unlink()
    (ROOT / "content").mkdir()
    front = '---\ntitle: "{t}"\ndescription: "요약"\ndate: "2026-09-26"\n---\n본문\n'
    (ROOT / "content" / "sat-post.mdx").write_text(front.format(t="토요일에 만든 글"), encoding="utf-8")
    (ROOT / "content" / "sent-post.mdx").write_text(front.format(t="이미 실린 글"), encoding="utf-8")
    F = lambda *p: [{"path": x} for x in p]  # noqa: E731
    prs = [{"number": 1, "mergedAt": "2026-09-27T11:10:00Z", "files": F("content/sat-post.mdx", "scripts/x.py")},
           {"number": 2, "mergedAt": "2026-09-27T11:20:00Z", "files": F("content/reverted.mdx")},     # merge 뒤 revert — 파일 없음
           {"number": 3, "mergedAt": "2026-09-27T11:30:00Z", "files": F("drafts/failed.mdx")},        # 탈락 원고 merge — 게시 아님
           {"number": 4, "mergedAt": "2026-09-27T11:40:00Z", "files": F("content/sent-post.mdx")},    # 지난 통에 이미 실림
           {"number": 5, "mergedAt": "2026-09-27T11:50:00Z", "files": F("content/sat-post.mdx")}]     # 같은 글을 또 건드린 PR
    (OUT / "2026-W39.md").write_text(f"# 지난 통\n{SITE}/posts/sent-post\n", encoding="utf-8")
    real_run = subprocess.run
    state = {"rc": 0}
    subprocess.run = lambda *a_, **k: subprocess.CompletedProcess([], state["rc"], json.dumps(prs), "boom")  # noqa: E731
    kst = lambda s: datetime.fromisoformat(s + "+09:00")  # noqa: E731
    assert posts(kst("2026-09-27T11:00:00")) == []                              # 승인 전(그날 11:00) — 아직 없다
    got = posts(kst("2026-10-04T11:00:00"))                                     # 다음 일요일 — **여기서 실려야 한다**
    assert [p["title"] for p in got] == ["토요일에 만든 글"], got
    assert got[0]["url"] == f"{SITE}/posts/sat-post"
    assert [p["title"] for p in posts(kst("2026-10-05T09:00:00"))] == ["토요일에 만든 글"]   # cron 이 빠져 월요일에 손으로 돌려도
    assert posts(kst("2026-10-12T11:00:00")) == []                              # LOOKBACK 밖
    (OUT / "2026-W41.md").write_text(f"{SITE}/posts/sat-post\n", encoding="utf-8")
    assert posts(kst("2026-10-04T11:00:00")) == []                              # 한 번 실린 글은 다시 안 실린다
    state["rc"] = 1                                                              # gh 가 죽으면 "0편" 이 아니라 죽는다
    try:
        posts(kst("2026-10-04T11:00:00"))
        raise AssertionError("gh 실패를 '새 글 0편' 으로 삼켰다")
    except SystemExit as e:
        assert "조회 실패" in str(e), e
    subprocess.run = real_run
    ROOT = saved_root

    # reads(): 고른 것(← 이번 원고)·이미 쓴 것·자리표시 제목은 빠진다. gh 실패는 빈 목록
    body = ("## 주제 후보 — 검수자가 고른다\n\n"
            "1. **고른 것**  ← 이번 원고  \n   https://ex.com/chosen\n"
            "2. **안 고른 것**  \n   https://ex.com/free\n"
            "3. **이미 쓴 것**  \n   https://ex.com/written\n"
            "4. **(제목만 확인됨)**  \n   https://ex.com/noname\n\n## 원고\n")
    real_run, real_written = subprocess.run, wp.written_urls
    subprocess.run = lambda *a_, **k: subprocess.CompletedProcess(  # noqa: E731
        [], 0, json.dumps([{"body": body, "createdAt": "2026-09-25T00:00:00Z"},
                           {"body": body, "createdAt": "2026-09-01T00:00:00Z"}]), "")
    wp.written_urls = lambda: {"https://ex.com/written"}                       # noqa: E731
    assert reads(date(2026, 9, 21)) == [("안 고른 것", "https://ex.com/free")], reads(date(2026, 9, 21))
    subprocess.run = lambda *a_, **k: (_ for _ in ()).throw(FileNotFoundError("gh"))  # noqa: E731
    assert reads(date(2026, 9, 21)) == []
    subprocess.run, wp.written_urls = real_run, real_written
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
