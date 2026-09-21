#!/usr/bin/env python3
"""일 20:00 슬롯 알림 한 통 — 열린 원고 PR 과 발행 예정 (slot-notify.yml, 증분 2 2026-09-18).

입력은 `gh pr list --state open --json number,title,url,labels` 의 JSON(stdin 또는 파일).
라벨 `원고:*` 인 PR 만 라벨별로 묶고 `탈락`·`보류` 를 표시한다. 그 아래에 main 의 승인된 Threads 원고 중
아직 안 나간 것의 발행 예정일을 붙인다. 계기판·댓글 대상은 증분 3 에서 같은 메시지에 붙인다.

Telegram 4,096자 상한은 .github/actions/telegram 이 나눠 보낸다 — 여기선 길이를 신경 쓰지 않는다.

사용:
  gh pr list --state open --json number,title,url,labels | python3 scripts/slot_notify.py
  python3 scripts/slot_notify.py --selftest
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_instagram as ig  # noqa: E402
import publish_queue as pq  # noqa: E402
import send_newsletter as sn  # noqa: E402

DAYS = "월화수목금토일"


def message(prs: list[dict], today: date) -> str:
    groups: dict[str, list[str]] = {}
    for p in prs:
        names = [lb["name"] for lb in p.get("labels", [])]
        kind = next((n for n in names if n.startswith("원고:")), None)
        if not kind:
            continue
        flags = "".join(f" [{f}]" for f in ("탈락", "보류") if f in names)
        groups.setdefault(kind, []).append(f"· #{p['number']} {p['title']}{flags}\n  {p['url']}")
    total = sum(len(v) for v in groups.values())
    out = [f"🗳 슬롯 {today:%m/%d} — 결정할 원고 {total}건", "merge=승인 · close=반려 · /변경 · /주제 N", ""]
    for kind in sorted(groups):
        out += [f"{kind} {len(groups[kind])}건", *groups[kind], ""]
    if not total:
        out += ["열린 원고 없음 — 이번 주는 아무것도 안 나간다(의도된 동작).", ""]
    sched = upcoming(today)
    out += ["발행 예정 (승인됨)", *(sched or ["· 없음"])]
    return "\n".join(out).rstrip() + "\n"


def upcoming(today: date) -> list[str]:
    done = pq.load_ledger()
    rows = []
    for side in sorted(pq.DIR.glob("*.json")):
        if side.name.startswith(".") or not side.with_suffix(".md").exists() or side.stem in done:
            continue
        on = date.fromisoformat(json.loads(side.read_text(encoding="utf-8"))["publish_on"])
        if on >= today:
            rows.append((on, f"· {on:%m/%d}({DAYS[on.weekday()]}) 09:00 Threads — {side.stem}"))
    rows += newsletter_rows(today)
    return [r for _, r in sorted(rows)] + cards_upcoming()


def newsletter_rows(today: date) -> list[tuple[date, str]]:
    """승인된 뉴스레터 원고 — 파일명이 곧 ISO 주차라 그 주 금요일이 발행일이다(Threads 와 같이 정렬된다).
    장부에 있으면 이미 나갔다. 장부가 깨져도 슬롯 메시지는 나가야 하니 그때는 이 줄만 포기한다."""
    try:
        done = sn.load_ledger()
    except Exception as e:  # noqa: BLE001
        print(f"뉴스레터 장부 읽기 실패 — 그 줄은 생략: {e}", file=sys.stderr)
        return []
    rows = []
    for md in sorted(sn.LEDGER.parent.glob("*.md")):
        week = md.stem
        if week in done or not sn.WEEK_RE.match(week) or not md.with_suffix(".html").exists():
            continue
        fri = datetime.strptime(week + "-5", "%G-W%V-%u").date()
        if fri >= today:
            rows.append((fri, f"· {fri:%m/%d}({DAYS[fri.weekday()]}) 09:00 뉴스레터 — {week}"))
    return rows


def cards_upcoming() -> list[str]:
    """승인된 덱의 줄. 날짜가 없어 Threads 와 같이 정렬하지 못한다 — 목요일마다 앞에서 하나씩 나간다."""
    done = ig.load_ledger()
    queued, seen = [], set()
    while (slug := ig.next_deck(done, seen)) is not None:
        seen.add(slug)
        queued.append(slug)
    return [f"· 목 09:00 Instagram — {s}" + (" (다음 차례)" if i == 0 else f" (앞에 {i}개)")
            for i, s in enumerate(queued)]


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    src = open(argv[1], encoding="utf-8") if len(argv) > 1 else sys.stdin
    sys.stdout.write(message(json.load(src), datetime.now(pq.KST).date()))
    return 0


def selftest() -> int:
    import tempfile
    pq.DIR = Path(tempfile.mkdtemp())
    pq.LEDGER = pq.DIR / ".published.json"
    (pq.DIR / "c-a.json").write_text('{"publish_on": "2026-09-28"}', encoding="utf-8")
    (pq.DIR / "c-a.md").write_text("글\n", encoding="utf-8")
    (pq.DIR / "c-old.json").write_text('{"publish_on": "2026-09-01"}', encoding="utf-8")
    (pq.DIR / "c-old.md").write_text("글\n", encoding="utf-8")
    # 승인된 덱 둘 — 폴더 이름의 날짜가 발행 순서다(publish_instagram.next_deck 의 이름순 가정)
    ig.CARDS = Path(tempfile.mkdtemp())
    ig.LEDGER = ig.CARDS / ".published.json"
    for name in ("2026-09-14-old-deck", "2026-09-21-new-deck", "2026-09-07-gone"):
        (ig.CARDS / name).mkdir()
        (ig.CARDS / name / "01.jpg").write_bytes(b"x")
        (ig.CARDS / name / "caption.txt").write_text("캡션\n", encoding="utf-8")
    ig.LEDGER.write_text('{"2026-09-07-gone": {"status": "published"}}', encoding="utf-8")
    # 승인된 뉴스레터 — 파일명이 ISO 주차고 그 주 금요일이 발행일이다. 장부에 있으면 이미 나갔다
    sn.LEDGER = Path(tempfile.mkdtemp()) / ".published.json"
    for week in ("2026-W40", "2026-W35", "2026-W41"):
        (sn.LEDGER.parent / f"{week}.md").write_text("# 제목\n", encoding="utf-8")
        (sn.LEDGER.parent / f"{week}.html").write_text("<p>x</p>", encoding="utf-8")
    (sn.LEDGER.parent / "2026-W42.md").write_text("# html 짝이 없다\n", encoding="utf-8")
    sn.LEDGER.write_text('{"2026-W41": {"status": "sent"}}', encoding="utf-8")
    prs = [{"number": 42, "title": "post: x", "url": "https://g/42", "labels": [{"name": "원고:blog"}, {"name": "탈락"}]},
           {"number": 43, "title": "thread: y", "url": "https://g/43", "labels": [{"name": "원고:thread"}]},
           {"number": 44, "title": "cards: z", "url": "https://g/44", "labels": [{"name": "원고:card"}, {"name": "보류"}]},
           {"number": 46, "title": "newsletter: 2026-W40", "url": "https://g/46", "labels": [{"name": "원고:newsletter"}]},
           {"number": 45, "title": "지도", "url": "https://g/45", "labels": [{"name": "wayfinder:map"}]}]
    m = message(prs, date(2026, 9, 27))
    assert "결정할 원고 4건" in m and "#42 post: x [탈락]" in m and "#45" not in m, m
    assert "원고:card 1건" in m and "#44 cards: z [보류]" in m, m
    assert "원고:newsletter 1건" in m and "#46 newsletter: 2026-W40" in m, m
    assert "09/28(월) 09:00 Threads — c-a" in m and "c-old" not in m, m
    assert "10/02(금) 09:00 뉴스레터 — 2026-W40" in m, m          # W40 의 금요일
    assert "2026-W35" not in m and "2026-W41" not in m, m         # 지난 주차 · 이미 나간 주차
    assert "2026-W42" not in m, m                                 # .html 짝이 없으면 발행기가 안 본다
    assert "Instagram — 2026-09-14-old-deck (다음 차례)" in m, m
    assert "Instagram — 2026-09-21-new-deck (앞에 1개)" in m, m
    assert "2026-09-07-gone" not in m, m          # 이미 나간 덱
    assert "아무것도 안 나간다" in message([], date(2026, 9, 27))
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
