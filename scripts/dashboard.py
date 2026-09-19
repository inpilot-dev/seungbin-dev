#!/usr/bin/env python3
"""주간 계기판 — 슬롯 메시지에 붙일 짧은 숫자 묶음 (증분 3, 2026-09-19).

정의는 이슈 #53 결정(2026-09-19) 그대로다. 창 = 지금(KST)에서 거꾸로 7일.
  결정      창 안에 merge·close 된 `원고:*` PR (라벨 `만료` 로 닫힌 것 제외)
  수시 결정  그중 슬롯(일 20:00~21:00 KST) **밖**에서 닫힌 것
  자동 반려  창 안에 `만료` 로 닫힌 원고 PR
  발행 실패  창 안에 failure 로 끝난 publish-queue 실행 수
  게시      머지된 `원고:blog` + 장부 3개(threads·cards·newsletter)의 published/sent 항목
  구독자    Resend 세그먼트의 unsubscribed==false (send_newsletter.count_subscribers 재사용)
  Threads   /me/threads_insights 7일 합 + followers_count 스냅숏(since/until 안 받음, #46)

왜: 개입 시간(≤30분/주)은 잴 수 없다. 결정·수시 결정 건수를 대리 지표로 남겨 10/18·12/06 판정에 쓴다.
출처 하나가 죽어도 슬롯 메시지는 나가야 한다 — gh 실패는 "조회 실패", Secret 없음은 "미연결", 항상 exit 0.

환경변수 (전부 선택):
  GH_TOKEN                          gh CLI 가 읽는다
  RESEND_API_KEY, RESEND_AUDIENCE_ID  없으면 구독자 "미연결"
  THREADS_TOKEN                     없으면 Threads "미연결"

사용:
  python3 scripts/dashboard.py                       # stdout 에 계기판
  python3 scripts/dashboard.py --append              # + state/dashboard.jsonl 에 한 줄
  python3 scripts/dashboard.py --now 2026-09-20T20:00:00+09:00
  python3 scripts/dashboard.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_threads as pt  # noqa: E402
import send_newsletter as sn  # noqa: E402

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "state" / "dashboard.jsonl"
LEDGERS = {  # 채널: (장부, 게시로 치는 status)
    "threads": (ROOT / "drafts" / "threads" / ".published.json", {"published"}),
    "cards": (ROOT / "drafts" / "cards" / ".published.json", {"published"}),
    "newsletter": (ROOT / "drafts" / "newsletter" / ".published.json", {"sent", "test-sent"}),
}
METRICS = ("views", "likes", "replies", "reposts", "quotes")


def gh(*args: str):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(out)


def ts(s: str) -> datetime:
    if len(s) == 10:
        # ponytail: publish_queue 장부는 날짜만 적는다 — 그 채널 발행 시각(09:00 KST)으로 본다
        return datetime.fromisoformat(s + "T09:00:00+09:00")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def pr_metrics(prs: list[dict], frm: datetime, to: datetime) -> dict:
    m = {"decisions": 0, "adhoc": 0, "auto_rejected": 0, "blog": 0}
    for p in prs:
        names = {lb["name"] for lb in p.get("labels", [])}
        if not any(n.startswith("원고:") for n in names) or not p.get("closedAt"):
            continue
        closed = ts(p["closedAt"]).astimezone(KST)
        if not frm <= closed <= to:
            continue
        if "만료" in names:
            m["auto_rejected"] += 1
            continue
        m["decisions"] += 1
        # ponytail: 슬롯 = 일요일 20시대(20:00:00~20:59:59). 21:00 정각은 수시로 센다
        if not (closed.weekday() == 6 and closed.hour == 20):
            m["adhoc"] += 1
        if p.get("mergedAt") and "원고:blog" in names:
            m["blog"] += 1
    return m


def ledger_count(path: Path, ok: set, frm: datetime, to: datetime) -> int:
    if not path.exists():
        return 0
    led = json.loads(path.read_text(encoding="utf-8"))
    return sum(1 for e in led.values()
               if isinstance(e, dict) and e.get("status") in ok and e.get("at")
               and frm <= ts(e["at"]) <= to)


def subscribers() -> int | str:
    key, seg = os.environ.get("RESEND_API_KEY"), os.environ.get("RESEND_AUDIENCE_ID")
    if not key or not seg:
        return "미연결"
    try:
        return sn.count_subscribers(key, seg)
    except Exception as e:  # noqa: BLE001 — sn._http 오류문엔 키가 없다(헤더로 보냄)
        print(f"구독자 조회 실패: {str(e)[:200]}", file=sys.stderr)
        return "조회 실패"


def _metric_value(item: dict) -> int:
    if "total_value" in item:
        return int(item["total_value"].get("value", 0))
    return sum(int(v.get("value", 0)) for v in item.get("values", []))   # views 는 일별 time series


def threads(frm: datetime, to: datetime) -> dict | str:
    token = os.environ.get("THREADS_TOKEN")
    if not token:
        return "미연결"
    try:
        # pt._call 은 오류에 경로만 싣는다 — 쿼리의 토큰이 안 샌다
        r = pt._call("me/threads_insights", {"metric": ",".join(METRICS), "since": int(frm.timestamp()),
                                             "until": int(to.timestamp())}, token, method="GET")
        out = {i["name"]: _metric_value(i) for i in r.get("data", []) if i.get("name") in METRICS}
        f = pt._call("me/threads_insights", {"metric": "followers_count"}, token, method="GET")
        out["followers"] = next((_metric_value(i) for i in f.get("data", [])
                                 if i.get("name") == "followers_count"), None)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"Threads 조회 실패: {str(e)[:200].replace(token, '***')}", file=sys.stderr)
        return "조회 실패"


def collect(now: datetime) -> dict:
    frm = now - timedelta(days=7)
    d: dict = {"frm": frm, "to": now}
    try:
        prs = gh("pr", "list", "--state", "closed", "--search", f"closed:>={(frm - timedelta(days=1)):%Y-%m-%d}",
                 "--json", "number,labels,closedAt,mergedAt", "--limit", "200")
        d.update(pr_metrics(prs, frm, now))
    except Exception as e:  # noqa: BLE001 — gh 없음·인증 실패·타임아웃 전부 "조회 실패"
        print(f"PR 조회 실패: {str(e)[:200]}", file=sys.stderr)
        d.update(decisions=None, adhoc=None, auto_rejected=None, blog=None)
    try:
        runs = gh("run", "list", "--workflow", "publish-queue.yml", "--json", "conclusion,createdAt",
                  "--limit", "50")
        d["publish_failures"] = sum(1 for r in runs if r.get("conclusion") == "failure"
                                    and frm <= ts(r["createdAt"]) <= now)
    except Exception as e:  # noqa: BLE001
        print(f"실행 조회 실패: {str(e)[:200]}", file=sys.stderr)
        d["publish_failures"] = None
    try:
        d["channels"] = {"blog": d["blog"], **{k: ledger_count(p, ok, frm, now)
                                               for k, (p, ok) in LEDGERS.items()}}
    except Exception as e:  # noqa: BLE001 — 깨진 장부. 발행기는 죽지만 계기판은 줄 하나만 포기한다
        print(f"장부 읽기 실패: {e}", file=sys.stderr)
        d["channels"] = None
    ch = d["channels"]
    d["published"] = None if ch is None or None in ch.values() else sum(ch.values())
    d["subscribers"] = subscribers()
    d["threads"] = threads(frm, now)
    return d


def _delta(cur, prev) -> str:
    return f" ({cur - prev:+d})" if isinstance(cur, int) and isinstance(prev, int) else ""


def render(d: dict, prev: dict | None = None) -> str:
    prev = prev or {}
    fail = "조회 실패"
    lines = [f"📊 계기판 ({d['frm']:%m/%d}~{d['to']:%m/%d})"]
    lines.append(f"결정 {fail}" if d["decisions"] is None else
                 f"결정 {d['decisions']}건 (수시 {d['adhoc']}건) · 자동 반려 {d['auto_rejected']}건")
    lines.append(f"발행 실패 {fail}" if d["publish_failures"] is None else f"발행 실패 {d['publish_failures']}건")
    ch = d["channels"]
    lines.append(f"게시 {fail}" if d["published"] is None else
                 f"게시 {d['published']}건 (" + " · ".join(f"{k} {v}" for k, v in ch.items()) + ")")
    s = d["subscribers"]
    lines.append(f"구독자 {s}명{_delta(s, prev.get('subscribers'))}" if isinstance(s, int) else f"구독자 {s}")
    t = d["threads"]
    if isinstance(t, dict):
        pf = (prev.get("threads") or {}).get("followers")
        lines.append("Threads 7일 조회 {views} · 좋아요 {likes} · 답글 {replies} · 리포스트 {reposts} · 인용 {quotes}"
                     .format(**{k: t.get(k, 0) for k in METRICS})
                     + f" · 팔로워 {t.get('followers')}{_delta(t.get('followers'), pf)}")
    else:
        lines.append(f"Threads {t}")
    lines.append("※ 개입 시간은 재지 않는다 — 결정·수시(슬롯 밖) 결정 건수가 대리 지표다.")
    return "\n".join(lines)


def row(d: dict) -> dict:
    num = lambda v: v if isinstance(v, int) else None  # noqa: E731 — "미연결"/"조회 실패" 는 null
    return {"week_end": f"{d['to']:%Y-%m-%d}", "decisions": d["decisions"], "adhoc": d["adhoc"],
            "auto_rejected": d["auto_rejected"], "publish_failures": d["publish_failures"],
            "published": d["published"], "subscribers": num(d["subscribers"]),
            "threads": d["threads"] if isinstance(d["threads"], dict) else None}


def last_row() -> dict | None:
    try:
        r = json.loads(JSONL.read_text(encoding="utf-8").strip().splitlines()[-1])
    except Exception:  # noqa: BLE001 — 없음·빈 파일·깨진 줄이면 증감만 생략
        return None
    # 파싱은 되지만 모양이 다른 줄(손 편집·스키마 변경)도 증감만 생략 — render() 가 죽으면 슬롯 메시지에서 계기판이 빠진다
    if not isinstance(r, dict):
        return None
    if not isinstance(r.get("threads"), (dict, type(None))):
        r["threads"] = None
    return r


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser(description="주간 계기판")
    ap.add_argument("--now", help="ISO 시각 (기본 지금). 시간대 없으면 KST")
    ap.add_argument("--append", action="store_true", help="state/dashboard.jsonl 에 한 줄 추가")
    a = ap.parse_args(argv[1:])
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(KST)
    now = (now if now.tzinfo else now.replace(tzinfo=KST)).astimezone(KST)
    d = collect(now)
    print(render(d, last_row()))
    if a.append:
        JSONL.parent.mkdir(parents=True, exist_ok=True)
        with JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row(d), ensure_ascii=False) + "\n")
    return 0


def selftest() -> int:
    import io
    import tempfile
    import urllib.parse
    import urllib.request
    from contextlib import redirect_stderr, redirect_stdout
    global ROOT, JSONL, LEDGERS

    now = datetime(2026, 9, 20, 20, 30, tzinfo=KST)          # 일요일 슬롯 안
    L = lambda *n: [{"name": x} for x in n]  # noqa: E731
    prs = [
        {"number": 1, "labels": L("원고:blog"), "closedAt": "2026-09-20T11:10:00Z", "mergedAt": "x"},  # 일 20:10 KST 슬롯
        {"number": 2, "labels": L("원고:thread"), "closedAt": "2026-09-16T03:00:00Z", "mergedAt": None},  # 수 12:00 반려·수시
        {"number": 3, "labels": L("원고:blog", "만료"), "closedAt": "2026-09-18T00:00:00Z", "mergedAt": None},
        {"number": 4, "labels": L("원고:blog"), "closedAt": "2026-09-13T12:00:00Z", "mergedAt": "x"},  # 일 21:00 KST 수시
        {"number": 5, "labels": L("원고:blog"), "closedAt": "2026-09-10T00:00:00Z", "mergedAt": "x"},  # 창 밖
        {"number": 6, "labels": L("bug"), "closedAt": "2026-09-19T00:00:00Z", "mergedAt": "x"},       # 원고 아님
    ]
    runs = [{"conclusion": "failure", "createdAt": "2026-09-18T00:05:00Z"},
            {"conclusion": "success", "createdAt": "2026-09-16T00:05:00Z"},
            {"conclusion": "failure", "createdAt": "2026-09-01T00:05:00Z"}]    # 창 밖
    gh_calls: list[list] = []
    state = {"gh_fail": False}

    def fake_run(cmd, **kw):
        gh_calls.append(cmd)
        if state["gh_fail"]:
            raise FileNotFoundError("gh")
        out = prs if cmd[1] == "pr" else runs
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

    net: list[str] = []

    class Resp:
        def __init__(self, obj): self.b = json.dumps(obj).encode()
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        u = urllib.parse.urlsplit(req.full_url)
        q = dict(urllib.parse.parse_qsl(u.query))
        net.append(req.full_url)
        if u.netloc == "api.resend.com":
            return Resp({"data": [{"id": "a", "unsubscribed": False}, {"id": "b", "unsubscribed": True},
                                  {"id": "c", "unsubscribed": False}], "has_more": False})
        if q["metric"] == "followers_count":
            assert "since" not in q and "until" not in q, q                   # #46: 스냅숏은 기간 없음
            return Resp({"data": [{"name": "followers_count", "total_value": {"value": 42}}]})
        if q["access_token"] == "BAD":
            raise urllib.error.HTTPError(req.full_url, 400, "x", {}, None)
        assert int(q["until"]) - int(q["since"]) == 7 * 86400, q
        return Resp({"data": [
            {"name": "views", "values": [{"value": 10}, {"value": 5}]},        # time series → 합
            {"name": "likes", "total_value": {"value": 3}},
            {"name": "replies", "total_value": {"value": 1}},
            {"name": "reposts", "total_value": {"value": 0}},
            {"name": "quotes", "total_value": {"value": 2}}]})

    import urllib.error
    real = (subprocess.run, urllib.request.urlopen)
    saved = (ROOT, JSONL, LEDGERS)
    envk = ("RESEND_API_KEY", "RESEND_AUDIENCE_ID", "THREADS_TOKEN")
    saved_env = {k: os.environ.get(k) for k in envk}
    subprocess.run, urllib.request.urlopen = fake_run, fake_urlopen

    def run(args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["x", "--now", now.isoformat(), *args])
        return code, out.getvalue(), err.getvalue()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            ROOT = Path(tmp)
            JSONL = ROOT / "state" / "dashboard.jsonl"
            LEDGERS = {k: (ROOT / p.relative_to(saved[0]), ok) for k, (p, ok) in saved[2].items()}
            for k in envk:
                os.environ.pop(k, None)
            (ROOT / "drafts" / "threads").mkdir(parents=True)
            (ROOT / "drafts" / "newsletter").mkdir(parents=True)
            LEDGERS["threads"][0].write_text(json.dumps({
                "a": {"status": "published", "at": "2026-09-16"},              # 날짜만 → 09:00 KST, 창 안
                "b": {"status": "failed", "at": "2026-09-18"},
                "c": {"status": "published", "at": "2026-09-13"}}))            # 09-13 09:00 < 09-13 20:30 → 창 밖
            LEDGERS["newsletter"][0].write_text(json.dumps({
                "2026-W38": {"status": "test-sent", "at": "2026-09-19T00:00:00+00:00"}}))

            # Secret 없음: 운영 지표는 gh 로, 외부 둘은 미연결 — 네트워크 0
            code, out, _ = run([])
            assert code == 0 and net == [], net
            lines = out.splitlines()
            assert lines[0] == "📊 계기판 (09/13~09/20)", lines
            assert "결정 3건 (수시 2건) · 자동 반려 1건" in out, out
            assert "발행 실패 1건" in out, out
            assert "게시 4건 (blog 2 · threads 1 · cards 0 · newsletter 1)" in out, out
            assert "구독자 미연결" in out and "Threads 미연결" in out and "대리 지표" in out, out
            assert len(lines) <= 12
            assert not JSONL.exists()                                          # --append 없으면 안 쓴다
            q = gh_calls[0][gh_calls[0].index("--search") + 1]
            assert q == "closed:>=2026-09-12", q

            # Secret 있음 + --append: jsonl 한 줄, 다음 실행에 증감
            os.environ.update(RESEND_API_KEY="k", RESEND_AUDIENCE_ID="seg", THREADS_TOKEN="SECRET-TOK")
            code, out, err = run(["--append"])
            assert code == 0 and "구독자 2명" in out, out
            assert "조회 15 · 좋아요 3 · 답글 1 · 리포스트 0 · 인용 2 · 팔로워 42" in out, out
            r = json.loads(JSONL.read_text().splitlines()[-1])
            assert r == {"week_end": "2026-09-20", "decisions": 3, "adhoc": 2, "auto_rejected": 1,
                         "publish_failures": 1, "published": 4, "subscribers": 2,
                         "threads": {"views": 15, "likes": 3, "replies": 1, "reposts": 0, "quotes": 2,
                                     "followers": 40 + 2}}, r
            JSONL.write_text(json.dumps({**r, "subscribers": 5, "threads": {"followers": 40}}) + "\n")
            _, out, _ = run([])
            assert "구독자 2명 (-3)" in out and "팔로워 42 (+2)" in out, out

            # gh 실패·API 실패·깨진 장부: 해당 줄만 "조회 실패", exit 0, 토큰 안 샘
            state["gh_fail"] = True
            os.environ["THREADS_TOKEN"] = "BAD"
            LEDGERS["cards"][0].parent.mkdir(parents=True)
            LEDGERS["cards"][0].write_text("{깨짐")
            code, out, err = run(["--append"])
            assert code == 0, code
            assert "결정 조회 실패" in out and "발행 실패 조회 실패" in out and "게시 조회 실패" in out, out
            assert "Threads 조회 실패" in out and "구독자 2명" in out, out
            assert "BAD" not in out + err and "access_token" not in err, err
            r = json.loads(JSONL.read_text().splitlines()[-1])
            assert r["decisions"] is None and r["published"] is None and r["threads"] is None, r
    finally:
        subprocess.run, urllib.request.urlopen = real
        ROOT, JSONL, LEDGERS = saved
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    # 모양이 다른 이전 줄은 증감만 생략하고 죽지 않는다 (리뷰 2026-09-19)
    real_jsonl, JSONL = JSONL, Path(tempfile.mkdtemp()) / "d.jsonl"
    for bad in ("[1]", '{"threads": "조회 실패"}', "5"):
        JSONL.write_text(bad + "\n", encoding="utf-8")
        r = last_row()
        assert r is None or r.get("threads") is None, (bad, r)
    JSONL = real_jsonl
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
