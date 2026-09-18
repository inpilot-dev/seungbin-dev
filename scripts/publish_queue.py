#!/usr/bin/env python3
"""승인된 Threads 원고를 채널 시각에 낸다 — 월·수·금 09:00 KST (publish-queue.yml, 증분 2 2026-09-18).

main 의 `drafts/threads/<slug>.md` 중
  - 사이드카 `<slug>.json` 의 publish_on 이 **오늘(KST)** 이고
  - 장부 `drafts/threads/.published.json` 에 없는 것만 → write_thread.publish_chain 으로 발행 → 장부 기록.
main 에 있다 = 사람이 merge 했다(승인). `.FAIL` 원고는 대상이 아니다.

publish_on 이 **지난** 미발행 원고는 내지 않는다 — 발행 시각까지 결정이 없던 것이라 그 주는 보류다
(2026-09-18 계획: "발행 시각까지 결정 없으면 그 주 보류"). 목록에만 찍어 슬롯에서 보이게 한다.

체인이 중간에 끊기면 장부에 failed 로 적는다. 다음 실행이 처음부터 다시 올려 앞부분이 중복되는 것보다,
사람이 publish-thread 워크플로로 이어 붙이는 게 낫다(write_thread 가 이어붙이기 명령을 찍는다).

사용:
  python3 scripts/publish_queue.py                  # 오늘 것 발행 (THREADS_TOKEN 없으면 DRY)
  DRY_RUN=1 python3 scripts/publish_queue.py --date 2026-09-28
  python3 scripts/publish_queue.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import write_thread as wt  # noqa: E402

KST = timezone(timedelta(hours=9))
DIR = wt.OUT
LEDGER = DIR / ".published.json"


def queue(today: date) -> tuple[list[Path], list[Path]]:
    """(오늘 낼 것, 날짜 지난 미발행) — 둘 다 장부에 없는 통과 원고만."""
    done = load_ledger()
    due, missed = [], []
    for side in sorted(DIR.glob("*.json")):
        if side.name.startswith("."):
            continue
        draft = side.with_suffix(".md")
        if not draft.exists() or draft.stem in done:
            continue            # .FAIL 만 있는 원고 · 이미 나간 원고
        on = date.fromisoformat(json.loads(side.read_text(encoding="utf-8"))["publish_on"])
        (due if on == today else missed if on < today else []).append(draft)
    return due, missed


def load_ledger() -> dict:
    if not LEDGER.exists():
        return {}
    # 장부가 깨졌는데 {} 로 읽으면 전부 "미발행" 이라 한 번 더 나간다 — 죽는다
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def record(slug: str, entry: dict) -> None:
    led = load_ledger()
    led[slug] = entry
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (기본 오늘 KST)")
    a = ap.parse_args(argv[1:])
    today = date.fromisoformat(a.date) if a.date else datetime.now(KST).date()
    dry = os.environ.get("DRY_RUN") == "1" or not os.environ.get("THREADS_TOKEN")
    due, missed = queue(today)
    for d in missed:
        print(f"보류(날짜 지남, 안 냄): {d.stem}")
    if not due:
        print(f"{today}: 낼 원고 없음")
        return 0
    rc = 0
    for d in due:
        parts = wt.split_parts(d.read_text(encoding="utf-8"))
        fails = [w for p in parts for w in wt.grade.deterministic("thread", p, [])]
        if fails:   # merge 뒤 사람이 손댔을 수 있다 — write_thread --draft 와 같은 검사
            print(f"FAIL {d.stem}: {fails[0]}")
            record(d.stem, {"status": "failed", "at": str(today), "why": fails[0][:200]})
            rc = 1
            continue
        try:
            ids = wt.publish_chain(parts, dry=dry)
        except Exception as e:  # noqa: BLE001  체인 중간 실패 — 이어붙이기는 사람이 한다
            print(f"FAIL {d.stem}: {e}")
            record(d.stem, {"status": "failed", "at": str(today), "why": str(e)[:200]})
            rc = 1
            continue
        if dry:
            print(f"DRY {d.stem}: 글 {len(parts)}개 (장부 안 씀)")
        else:
            record(d.stem, {"status": "published", "at": str(today), "ids": ids})
            print(f"발행 {d.stem}: {ids}")
    return rc


def selftest() -> int:
    import tempfile
    global DIR, LEDGER
    DIR = Path(tempfile.mkdtemp())
    LEDGER = DIR / ".published.json"
    t = date(2026, 9, 28)
    for slug, on in [("a", "2026-09-28"), ("b", "2026-09-25"), ("c", "2026-10-02"), ("d", "2026-09-28")]:
        (DIR / f"{slug}.json").write_text(json.dumps({"publish_on": on}), encoding="utf-8")
    for slug in ("a", "b", "c"):
        (DIR / f"{slug}.md").write_text("하나\n---\n둘\n", encoding="utf-8")
    (DIR / "d.FAIL.md").write_text("탈락\n", encoding="utf-8")   # 통과 원고 없음 → 대상 아님
    due, missed = queue(t)
    assert [p.stem for p in due] == ["a"] and [p.stem for p in missed] == ["b"], (due, missed)
    record("a", {"status": "published"})
    assert queue(t)[0] == []                                      # 장부에 있으면 다시 안 낸다
    assert main(["", "--date", "2026-09-28"]) == 0
    LEDGER.write_text("{깨짐", encoding="utf-8")
    try:
        queue(t)
        raise AssertionError("깨진 장부를 빈 장부로 읽었다")
    except ValueError:
        pass
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
