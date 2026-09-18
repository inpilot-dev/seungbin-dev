#!/usr/bin/env python3
"""주간 뉴스레터 한 주치를 Resend 로 보낸다 (증분 4 — 발송기만. 원고 작성기는 설계 결정 대기).

2026-09-18. 근거: 이슈 #47 조사(docs/research/resend-api-2026-09.md, 브랜치 research/resend-api).
Audiences 는 Segments 로 이름이 바뀌었다 — RESEND_AUDIENCE_ID 값을 segment_id 로 보낸다.

순서: 구독자 수를 먼저 센다(GET /contacts?segment_id=… , unsubscribed==false 만).
  > 0 → POST /broadcasts (draft) → POST /broadcasts/{id}/send
  = 0 → 브로드캐스트하지 않는다(0명 세그먼트 동작은 미확인). RESEND_FROM 주소로 테스트 메일 1통만.
장부 drafts/newsletter/.published.json 에 주차별로 남기고, 장부에 있는 주차는 다시 안 보낸다.
실패도 기록한다 — draft 가 이미 만들어졌을 수 있어서 자동 재시도는 이중 발송 위험이다.
다시 보내려면 장부에서 그 주차를 손으로 지운다.

환경변수:
  RESEND_API_KEY      full access 키. 없으면 DRY.
  RESEND_AUDIENCE_ID  segment_id 로 보낸다
  RESEND_FROM         "이름 <a@b>" — broadcast from, 0명일 때 테스트 수신자
  RESEND_REPLY_TO     선택
  DRY_RUN=1           네트워크 없이 out/newsletter-<주차>.html 만 쓰고 무엇을 보낼지 출력

사용:
  python3 scripts/send_newsletter.py --md drafts/newsletter/2026-W39.md \\
      --html drafts/newsletter/2026-W39.html --subject "..."
  python3 scripts/send_newsletter.py ... --to me@example.com   # 테스트 1통, 장부 안 씀
  python3 scripts/send_newsletter.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

API = "https://api.resend.com"
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "drafts" / "newsletter" / ".published.json"
OUT = ROOT / "out"
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def _http(method: str, path: str, key: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        # 기본 Python-urllib UA 는 Cloudflare 에 막히는 일이 있다
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "seungbin-dev-newsletter/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        # Resend 는 403/422 원인을 본문 JSON 으로 준다. 키 값은 절대 안 찍는다.
        raise RuntimeError(f"Resend {method} {path} → HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'ignore')[:500]}") from None


def count_subscribers(key: str, segment: str) -> int:
    # ponytail: 개수 전용 엔드포인트가 없어 전량 순회 — 100명당 1요청, 팀 한도 10 req/s.
    # 수천 명이 되면 429 가 날 수 있다 → 그때 페이지 사이 sleep 또는 발송 직전 카운트 생략.
    n, after = 0, None
    while True:
        q = {"segment_id": segment, "limit": 100, **({"after": after} if after else {})}
        page = _http("GET", "/contacts?" + urllib.parse.urlencode(q), key)
        data = page.get("data", [])
        n += sum(1 for c in data if c.get("unsubscribed") is False)
        if not page.get("has_more") or not data:
            return n
        after = data[-1]["id"]


def send_email(key: str, frm: str, to: str, subject: str, html: str, text: str,
               reply_to: str | None) -> str:
    body = {"from": frm, "to": [to], "subject": subject, "html": html, "text": text}
    if reply_to:
        body["reply_to"] = reply_to
    return _http("POST", "/emails", key, body)["id"]


def broadcast(key: str, segment: str, frm: str, subject: str, html: str, text: str,
              reply_to: str | None, ids: dict) -> str:
    body = {"segment_id": segment, "from": frm, "subject": subject, "html": html, "text": text}
    if reply_to:
        body["reply_to"] = reply_to
    # ids 에 먼저 적어 둔다 — /send 가 실패해도 장부에 draft id 가 남아 대시보드에서 찾을 수 있다
    ids["broadcast_id"] = bid = _http("POST", "/broadcasts", key, body)["id"]
    _http("POST", f"/broadcasts/{bid}/send", key, {})
    return bid


def load_ledger() -> dict:
    if not LEDGER.exists():
        return {}
    # 깨진 장부를 {} 로 읽으면 이미 나간 주차가 한 번 더 나간다 — 죽는다 (publish_queue.py 와 같은 규칙)
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def record(week: str, entry: dict) -> None:
    led = load_ledger()
    led[week] = entry
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser(description="주간 뉴스레터 발송 (Resend)")
    ap.add_argument("--md", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--to", help="이 주소로 테스트 메일 1통만 (구독자 수·장부 무관)")
    a = ap.parse_args(argv[1:])

    week = Path(a.md).stem
    if not WEEK_RE.match(week):
        print(f"주차 id 를 파일명에서 못 읽음: {a.md} (기대: YYYY-Www.md)", file=sys.stderr)
        return 2
    text = Path(a.md).read_text(encoding="utf-8")
    html = Path(a.html).read_text(encoding="utf-8")

    # --to 는 사람이 보는 시험 발송이라 장부를 안 본다. 장부를 쓰면 진짜 발송이 막힌다.
    if not a.to and week in load_ledger():
        print(f"{week} 는 이미 장부에 있음 — 발송 거부 ({load_ledger()[week].get('status')})",
              file=sys.stderr)
        return 1

    key = os.environ.get("RESEND_API_KEY", "")
    segment = os.environ.get("RESEND_AUDIENCE_ID", "")
    frm = os.environ.get("RESEND_FROM", "")
    reply_to = os.environ.get("RESEND_REPLY_TO") or None

    if not key or os.environ.get("DRY_RUN") == "1":
        OUT.mkdir(exist_ok=True)
        out = OUT / f"newsletter-{week}.html"
        out.write_text(html, encoding="utf-8")
        route = (f"POST /emails → {a.to} (테스트 1통)" if a.to else
                 f"구독자 >0: POST /broadcasts segment={segment or '(미설정)'} → /send · "
                 f"0명: POST /emails → {parseaddr(frm)[1] or '(RESEND_FROM 미설정)'}")
        print(f"[DRY] {week}\n  제목: {a.subject}\n  수신 경로: {route}\n"
              f"  본문: {out.relative_to(ROOT)} ({len(html)}자 html · {len(text)}자 text)\n"
              f"  장부: 안 씀")
        return 0

    if not frm or (not a.to and not segment):
        print("RESEND_FROM / RESEND_AUDIENCE_ID 필요", file=sys.stderr)
        return 2

    if a.to:
        eid = send_email(key, frm, a.to, a.subject, html, text, reply_to)
        print(f"테스트 메일 발송: {a.to} (email_id={eid}) — 장부 안 씀")
        return 0

    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids: dict = {}
    try:
        n = count_subscribers(key, segment)
        print(f"구독자 {n}명")
        if n > 0:
            broadcast(key, segment, frm, a.subject, html, text, reply_to, ids)
            status = "sent"
        else:
            self_addr = parseaddr(frm)[1]
            ids["email_id"] = send_email(key, frm, self_addr, a.subject, html, text, reply_to)
            print(f"0명 — 브로드캐스트 안 함, {self_addr} 로 테스트 1통")
            status = "test-sent"
    except Exception as e:
        record(week, {"status": "failed", "at": at, **ids, "error": str(e)[:300]})
        print(f"실패: {e}", file=sys.stderr)
        return 1
    record(week, {"status": status, "at": at, **ids})
    print(f"{week}: {status} {ids}")
    return 0


def selftest() -> int:
    import tempfile
    global LEDGER, OUT, ROOT
    calls: list[tuple] = []
    state = {"contacts": [], "fail_send": False}

    class Resp:
        def __init__(self, obj): self.b = json.dumps(obj).encode()
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        u = urllib.parse.urlsplit(req.full_url)
        body = json.loads(req.data) if req.data else None
        calls.append((req.get_method(), u.path, dict(urllib.parse.parse_qsl(u.query)), body))
        if u.path == "/contacts":
            q = dict(urllib.parse.parse_qsl(u.query))
            assert q["segment_id"] == "seg1", q
            cs = state["contacts"]
            i = next((k + 1 for k, c in enumerate(cs) if c["id"] == q.get("after")), 0)
            chunk = cs[i:i + 2]                        # 페이지 크기 2 로 페이지네이션을 강제
            return Resp({"data": chunk, "has_more": i + 2 < len(cs)})
        if u.path == "/broadcasts":
            assert body["segment_id"] == "seg1" and "audience_id" not in body, body
            return Resp({"id": "b1"})
        if u.path.endswith("/send"):
            if state["fail_send"]:
                raise urllib.error.HTTPError(req.full_url, 422, "x", {}, None)
            return Resp({"id": "b1"})
        if u.path == "/emails":
            return Resp({"id": "e1"})
        raise AssertionError(u.path)

    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    saved_env = {k: os.environ.get(k) for k in
                 ("RESEND_API_KEY", "RESEND_AUDIENCE_ID", "RESEND_FROM", "RESEND_REPLY_TO", "DRY_RUN")}
    saved_paths = (LEDGER, OUT, ROOT)
    try:
        with tempfile.TemporaryDirectory() as d:
            ROOT = Path(d)
            LEDGER, OUT = ROOT / "led.json", ROOT / "out"
            md, html = ROOT / "2026-W39.md", ROOT / "2026-W39.html"
            md.write_text("본문", encoding="utf-8")
            html.write_text("<p>본문</p>", encoding="utf-8")
            args = ["x", "--md", str(md), "--html", str(html), "--subject", "제목"]
            for k in saved_env:
                os.environ.pop(k, None)

            # DRY (키 없음): 네트워크 0, html 파일만, 장부 안 씀
            assert main(args) == 0
            assert calls == [] and (OUT / "newsletter-2026-W39.html").exists()
            assert not LEDGER.exists()

            os.environ.update(RESEND_API_KEY="k", RESEND_AUDIENCE_ID="seg1",
                              RESEND_FROM="승빈 <me@inpilot.dev>")
            # DRY_RUN=1 은 키가 있어도 네트워크 0
            os.environ["DRY_RUN"] = "1"
            assert main(args) == 0 and calls == []
            del os.environ["DRY_RUN"]

            # 0명(구독 해지자만 있음) → 브로드캐스트 없이 RESEND_FROM 주소로 테스트 1통
            state["contacts"] = [{"id": "c1", "unsubscribed": True}]
            assert main(args) == 0
            assert not any(c[1].startswith("/broadcasts") for c in calls), calls
            assert calls[-1][1] == "/emails" and calls[-1][3]["to"] == ["me@inpilot.dev"]
            led = json.loads(LEDGER.read_text())
            assert led["2026-W39"]["status"] == "test-sent" and led["2026-W39"]["email_id"] == "e1"

            # 장부에 있는 주차는 거부 — 네트워크 0
            calls.clear()
            assert main(args) == 1 and calls == []

            # --to 는 장부 무관 1통, 장부 안 바꿈
            assert main(args + ["--to", "t@x.com"]) == 0
            assert [c[1] for c in calls] == ["/emails"] and calls[0][3]["to"] == ["t@x.com"]
            assert json.loads(LEDGER.read_text()) == led

            # 페이지네이션: 5명 중 구독 중 3명 → broadcast → send, text 도 같이
            LEDGER.unlink()
            calls.clear()
            state["contacts"] = [{"id": f"c{i}", "unsubscribed": i % 2 == 1} for i in range(5)]
            assert count_subscribers("k", "seg1") == 3
            assert sum(c[1] == "/contacts" for c in calls) == 3, calls
            calls.clear()
            assert main(args) == 0
            assert [c[1] for c in calls if c[0] == "POST"] == ["/broadcasts", "/broadcasts/b1/send"]
            b = next(c[3] for c in calls if c[1] == "/broadcasts")
            assert b["text"] == "본문" and b["html"] == "<p>본문</p>" and b["subject"] == "제목"
            assert json.loads(LEDGER.read_text())["2026-W39"] == {
                "status": "sent", "at": json.loads(LEDGER.read_text())["2026-W39"]["at"],
                "broadcast_id": "b1"}

            # /send 실패 → failed + draft id 기록, 재실행 거부
            LEDGER.unlink()
            state["fail_send"] = True
            assert main(args) == 1
            e = json.loads(LEDGER.read_text())["2026-W39"]
            assert e["status"] == "failed" and e["broadcast_id"] == "b1", e
            assert main(args) == 1

            # 깨진 장부는 빈 장부가 아니다 — 죽는다
            LEDGER.write_text("{깨짐")
            try:
                main(args)
                raise AssertionError("깨진 장부를 통과함")
            except json.JSONDecodeError:
                pass

            # 파일명이 주차 형식이 아니면 거부
            bad = ROOT / "draft.md"
            bad.write_text("x")
            assert main(["x", "--md", str(bad), "--html", str(html), "--subject", "s"]) == 2
    finally:
        urllib.request.urlopen = real
        LEDGER, OUT, ROOT = saved_paths
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
