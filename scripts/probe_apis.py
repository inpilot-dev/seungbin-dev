#!/usr/bin/env python3
"""Resend·Threads 실호출로 '문서로는 못 닫은 사실'을 닫는다 (지도 #55).

**읽기 전용이다.** GET 만 한다 — 발행·발송·생성·삭제 없음. 그래서 아무 때나 다시 돌려도 안전하고,
60일마다 토큰이 바뀔 때 "권한이 그대로인가"를 다시 재는 도구로 쓴다.

왜 스크립트로 남기나: 답이 한 번 필요한 게 아니다. Threads 토큰은 60일마다 재발급되고 그때마다
권한이 빠질 수 있다(2026-09-14 실측: 토큰은 있는데 "API access blocked"). 그때 이걸 돌린다.

출력 규칙 — 공개 레포다:
- 토큰 값은 절대 안 찍는다. 있으면 `set`, 없으면 `unset` 으로만 말한다.
- keyword_search 는 **남의 글**을 돌려준다. 본문·작성자를 찍지 않고 건수와 필드 이름만 센다
  (CONTEXT 규칙: 공개 로그에 남의 글을 싣지 않는다).

자체 점검: python3 scripts/probe_apis.py --selftest
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RESEND = "https://api.resend.com"
THREADS = "https://graph.threads.net/v1.0"
TIMEOUT = 20


def get(url: str, token: str) -> tuple[int, dict | list | str]:
    """GET 한 번. (상태코드, 파싱된 본문). 죽지 않는다 — 프로브가 한 칸 때문에 멈추면 안 된다."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def err(payload) -> str:
    """API 가 돌려준 사유 한 줄. 모양이 제각각이라 알려진 자리만 훑는다."""
    if isinstance(payload, dict):
        for k in ("message", "error"):
            v = payload.get(k)
            if isinstance(v, str):
                return v[:120]
            if isinstance(v, dict) and isinstance(v.get("message"), str):
                return v["message"][:120]
    return str(payload)[:120]


def row(label: str, verdict: str, detail: str = "") -> None:
    print(f"  {label:<34} {verdict:<10} {detail}")


def probe_resend(key: str, audience: str) -> None:
    print("\n## Resend")
    if not key:
        row("RESEND_API_KEY", "unset", "— 나머지 전부 건너뜀")
        return
    row("RESEND_API_KEY", "set", f"RESEND_AUDIENCE_ID={'set' if audience else 'unset'}")

    # 1. 기존 AUDIENCE_ID 값이 segments 쪽 segment_id 로 먹는가 (#47 이 문서로만 답한 것)
    if audience:
        code, body = get(f"{RESEND}/contacts?segment_id={urllib.parse.quote(audience)}", key)
        n = len(body.get("data", [])) if isinstance(body, dict) and isinstance(body.get("data"), list) else None
        row("GET /contacts?segment_id=", str(code),
            f"연락처 {n}건" if code == 200 else err(body))

        # 2. 구독 폼(app/api/subscribe)이 아직 쓰는 deprecated 경로가 사는가
        code, body = get(f"{RESEND}/audiences/{urllib.parse.quote(audience)}/contacts", key)
        n = len(body.get("data", [])) if isinstance(body, dict) and isinstance(body.get("data"), list) else None
        row("GET /audiences/{id}/contacts", str(code),
            f"연락처 {n}건 — 구독 폼 살아 있음" if code == 200
            else f"{err(body)} ← app/api/subscribe 가 깨진다")

    # 3. 키가 full access 인가. broadcasts 는 sending 전용 키로는 못 읽는다(#47)
    code, body = get(f"{RESEND}/broadcasts", key)
    row("GET /broadcasts", str(code),
        "full access ✅ 뉴스레터 가능" if code == 200
        else f"{err(body)} ← sending 전용이면 증분 4 가 막힌다")


# 권한 → 그 권한이 있어야 열리는 읽기 엔드포인트. 쓰기 권한(content_publish·manage_replies)은
# 읽기로 확인할 수 없어 뺐다 — 없는 걸 있다고 적느니 모른다고 둔다.
THREADS_PROBES = [
    ("threads_basic", "/me?fields=id,username"),
    ("threads_manage_insights", "/me/threads_insights?metric=views"),
    ("threads_read_replies", "/me/replies?fields=id&limit=1"),
]


def probe_threads(token: str) -> None:
    print("\n## Threads")
    if not token:
        row("THREADS_TOKEN", "unset", "— 나머지 전부 건너뜀")
        return
    row("THREADS_TOKEN", "set")

    for perm, path in THREADS_PROBES:
        code, body = get(THREADS + path, token)
        row(perm, str(code), "✅" if code == 200 else err(body))

    # keyword_search: 승인 전엔 본인 글만 준다는 게 #46 의 문서 답이다. 실제로 뭘 주는지 본다.
    # ⚠️ 남의 글이 섞여 오므로 본문·작성자를 찍지 않는다 — 건수와 필드 이름만.
    code, body = get(
        f"{THREADS}/keyword_search?q={urllib.parse.quote('claude code')}&search_type=TOP", token)
    if code != 200:
        row("threads_keyword_search", str(code), err(body))
        return
    data = body.get("data", []) if isinstance(body, dict) else []
    fields = sorted({k for it in data if isinstance(it, dict) for k in it})
    row("threads_keyword_search", "200", f"{len(data)}건 · 필드 {', '.join(fields) or '없음'}")
    print("     ↑ 본문·작성자는 일부러 안 찍는다(공개 로그). 남의 글이 오는지는 필드로 판단할 것")


def main() -> int:
    print("# API 프로브 — 읽기 전용(GET), 발행·발송·생성·삭제 없음")
    probe_resend(os.environ.get("RESEND_API_KEY", ""), os.environ.get("RESEND_AUDIENCE_ID", ""))
    probe_threads(os.environ.get("THREADS_TOKEN", ""))
    print("\n끝. 200 이 아닌 칸이 지도 #45 의 열린 결정으로 간다.")
    return 0


def selftest() -> int:
    assert err({"message": "bad"}) == "bad"
    assert err({"error": {"message": "nope"}}) == "nope"
    assert err({"error": "flat"}) == "flat"
    assert err("plain") == "plain"
    # 토큰이 없으면 네트워크를 안 친다 — CI 에서 Secret 이 빠져도 조용히 성공하지 않게 화면에 남는다
    probe_resend("", "")
    probe_threads("")
    # get() 은 죽지 않는다: 닿을 수 없는 호스트도 (0, 사유) 로 돌려준다
    code, body = get("http://127.0.0.1:1/nope", "x")
    assert code == 0 and isinstance(body, str), (code, body)
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
