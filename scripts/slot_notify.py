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
import publish_queue as pq  # noqa: E402

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
    return [r for _, r in sorted(rows)]


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
    prs = [{"number": 42, "title": "post: x", "url": "https://g/42", "labels": [{"name": "원고:blog"}, {"name": "탈락"}]},
           {"number": 43, "title": "thread: y", "url": "https://g/43", "labels": [{"name": "원고:thread"}]},
           {"number": 45, "title": "지도", "url": "https://g/45", "labels": [{"name": "wayfinder:map"}]}]
    m = message(prs, date(2026, 9, 27))
    assert "결정할 원고 2건" in m and "#42 post: x [탈락]" in m and "#45" not in m, m
    assert "09/28(월) 09:00 Threads — c-a" in m and "c-old" not in m, m
    assert "아무것도 안 나간다" in message([], date(2026, 9, 27))
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
