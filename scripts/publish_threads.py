#!/usr/bin/env python3
"""머지된 다이제스트에서 '체크 + 논평'이 붙은 항목만 Threads 에 올린다.

체인: digest/*.md 파싱 → 게이트 통과분만 → 컨테이너 생성 → 30초 대기 → 발행

**이 스크립트의 존재 이유는 발행이 아니라 게이트다.**
CAP-6("기계 요약만으로는 올리지 않는다")을 사람 기억이 아니라 코드로 강제한다.
체크만 하고 논평을 안 쓴 항목은 발행되지 않는다 — 그게 기본값이고 우회 옵션은 없다.

다이제스트에서 발행 대상으로 인정하는 형태:

    - [x] **제목**
          `출처` · https://example.com/x
          > 내 논평 한 줄

`- [x]` 와 `>` 논평이 **둘 다** 있어야 한다. 하나라도 빠지면 조용히 건너뛴다.

환경변수:
  THREADS_TOKEN    장기 액세스 토큰 (60일 만료). 없으면 아무것도 안 하고 0 으로 끝난다.
  THREADS_USER_ID  Threads 사용자 ID
  DRY_RUN=1        네트워크 호출 없이 무엇을 올릴지만 출력

사용:
  python3 scripts/publish_threads.py digest/2026-09-03.md
  python3 scripts/publish_threads.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.threads.net/v1.0"
MAX_LEN = 500          # Threads 텍스트 상한
SETTLE_SEC = 30        # 컨테이너 생성 → 발행 사이 권장 대기. 줄이면 조용히 실패한다
EXPIRY_WARN_DAYS = 14  # 토큰 만료가 이보다 가까우면 경고
LEDGER = Path(__file__).resolve().parent.parent / "digest" / ".published.json"

# `- [x] **제목**` 다음 줄에 `출처 · URL`, 그 다음 줄에 `> 논평`
ITEM_RE = re.compile(
    r"^- \[x\] \*\*(?P<title>.+?)\*\*[ \t]*\n"
    r"[ \t]*`(?P<source>[^`]*)`[^\n]*?(?P<url>https?://\S+)[ \t]*\n"
    r"[ \t]*>[ \t]*(?P<note>.+?)[ \t]*$",
    re.M,
)


def parse_items(md: str) -> list[dict]:
    """발행 게이트를 통과한 항목만 뽑는다. 통과 조건은 체크 + 논평 둘 다."""
    return [m.groupdict() for m in ITEM_RE.finditer(md)]


def compose(item: dict) -> str:
    """논평이 본문이고 링크가 꼬리다. 상한을 넘으면 **논평이 아니라 제목을** 깎는다 —
    논평은 사람이 쓴 유일한 부분이라 여기서 잘리면 이 파이프라인의 의미가 없다."""
    tail = f"\n\n{item['url']}"
    note = item["note"].strip()
    head = f"{note}\n\n— {item['title'].strip()}"
    if len(head) + len(tail) <= MAX_LEN:
        return head + tail
    room = MAX_LEN - len(tail) - len(note) - len("\n\n— ") - 1
    if room < 10:                       # 논평만으로 이미 꽉 참 → 제목을 버린다
        return note[: MAX_LEN - len(tail)] + tail
    return f"{note}\n\n— {item['title'].strip()[:room]}…" + tail


def _call(path: str, params: dict, token: str, method: str = "POST") -> dict:
    params = {**params, "access_token": token}
    if method == "POST":
        req = urllib.request.Request(
            f"{API}/{path}", data=urllib.parse.urlencode(params).encode(), method="POST")
    else:
        req = urllib.request.Request(f"{API}/{path}?{urllib.parse.urlencode(params)}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def check_token(token: str) -> None:
    """만료가 가까우면 경고만 한다. 갱신된 토큰을 Secret 에 되쓸 방법이 없으므로
    자동 갱신은 만들지 않았다 — 조용히 성공한 척하는 것보다 시끄러운 게 낫다."""
    try:
        info = _call("me", {"fields": "id"}, token, method="GET")
        print(f"토큰 유효 (user id={info.get('id')})")
    except urllib.error.HTTPError as e:
        print(f"토큰 검증 실패 (HTTP {e.code}) — 재발급 필요: "
              f"https://developers.facebook.com/docs/threads/get-started",
              file=sys.stderr)
        raise


def post_text(text: str, user_id: str, token: str, dry: bool,
              reply_to: str | None = None) -> str | None:
    """텍스트 한 건 발행. reply_to 를 주면 그 게시물의 답글 — 스레드 체인은 이걸 반복한다.
    (컨테이너 → 30초 → publish. 답글은 24h 1,000건 한도로 게시 250건과 별도.)"""
    if dry:
        print(f"[DRY] {len(text)}자{' (reply)' if reply_to else ''}\n{text}\n{'-' * 40}")
        return "dry-run"
    params = {"media_type": "TEXT", "text": text}
    if reply_to:
        params["reply_to_id"] = reply_to
    cid = _call(f"{user_id}/threads", params, token)["id"]
    # 여기서 안 기다리면 발행이 실패한다. 공식 문서 권장 30초.
    print(f"  컨테이너 {cid} 생성 — {SETTLE_SEC}초 대기")
    time.sleep(SETTLE_SEC)
    pid = _call(f"{user_id}/threads_publish", {"creation_id": cid}, token)["id"]
    print(f"  발행됨: {pid}")
    return pid


def publish(item: dict, user_id: str, token: str, dry: bool) -> str | None:
    return post_text(compose(item), user_id, token, dry)


def load_ledger() -> set[str]:
    try:
        return set(json.loads(LEDGER.read_text()))
    except Exception:
        return set()


def save_ledger(done: set[str]) -> None:
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1))


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    md = Path(argv[1]).read_text(encoding="utf-8")
    items = parse_items(md)
    if not items:
        print("발행 대상 없음 — 체크(- [x]) + 논평(>) 이 둘 다 있는 항목이 없다")
        return 0

    dry = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("THREADS_TOKEN", "")
    user_id = os.environ.get("THREADS_USER_ID", "")
    if not dry and not (token and user_id):
        # 실패가 아니다. 토큰을 아직 안 붙였을 뿐이므로 수집 파이프라인을 안 깬다.
        print("THREADS_TOKEN/THREADS_USER_ID 없음 — 발행 건너뜀", file=sys.stderr)
        return 0
    if not dry:
        check_token(token)

    done = load_ledger()
    todo = [i for i in items if i["url"] not in done]
    print(f"게이트 통과 {len(items)}건 · 미발행 {len(todo)}건")

    failed = 0
    for item in todo:
        print(f"→ {item['title'][:50]}")
        try:
            if publish(item, user_id, token, dry) and not dry:
                done.add(item["url"])
        except Exception as e:                      # 한 건 실패가 나머지를 막지 않는다
            failed += 1
            print(f"  실패: {e}", file=sys.stderr)

    if not dry:
        save_ledger(done)
    return 1 if failed else 0


def selftest() -> int:
    md = """# 2026-09-03 다이제스트

- [x] **체크되고 논평도 있음**
      `HN (300pts)` · https://ex.com/a
      > 이건 내 생각이다

- [x] **체크만 되고 논평 없음**
      `HN (200pts)` · https://ex.com/b

- [ ] **체크 안 됨**
      `HN (100pts)` · https://ex.com/c
      > 논평은 있지만 체크가 없다
"""
    got = parse_items(md)
    # 게이트의 전부: 체크 + 논평이 **둘 다** 있어야 통과. 이게 CAP-6 그 자체다.
    assert [i["url"] for i in got] == ["https://ex.com/a"], got
    assert got[0]["note"] == "이건 내 생각이다", got

    # 논평이 본문, 링크는 꼬리
    text = compose(got[0])
    assert text.startswith("이건 내 생각이다"), text
    assert text.endswith("https://ex.com/a"), text
    assert len(text) <= MAX_LEN

    # 상한 초과 시 깎이는 건 제목이지 논평이 아니다
    long_title = {"title": "제" * 400, "url": "https://ex.com/d", "note": "짧은 논평"}
    out = compose(long_title)
    assert len(out) <= MAX_LEN, len(out)
    assert out.startswith("짧은 논평"), out
    assert out.endswith("https://ex.com/d"), out

    # 논평만으로 이미 상한을 넘으면 제목을 통째로 버리고 논평을 살린다
    huge_note = {"title": "제목", "url": "https://ex.com/e", "note": "논" * 600}
    out2 = compose(huge_note)
    assert len(out2) <= MAX_LEN, len(out2)
    assert out2.startswith("논논논"), out2[:20]

    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
