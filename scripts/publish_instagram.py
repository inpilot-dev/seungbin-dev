#!/usr/bin/env python3
"""머지된 카드뉴스 덱(public/cards/<slug>/)을 Instagram 캐러셀로 올린다. (증분 6, 2026-09-18)

왜: ADR-0002 — 카드 JPEG는 이 저장소 public/cards/ 에 PR로 들어오고, 머지·배포되면
https://inpilot.dev/cards/<slug>/NN.jpg 가 공개 URL이 된다. Meta는 그 URL을 직접 가져간다.
조사 근거: docs/research/instagram-carousel-2026-09.md (이슈 #48).

덱 형태:
  public/cards/<slug>/01.jpg … NN.jpg   (2~10장, 파일명 순서 = 카드 순서)
  public/cards/<slug>/caption.txt       (≤2,200자, 해시태그 ≤30개 — 넘으면 자르지 않고 거부)
  drafts/cards/.published.json          ({slug: {status, at, media_id, permalink}}) 장부
                                        — public/ 밑에 두면 inpilot.dev 로 공개돼 실패 사유까지 보인다(리뷰 2026-09-18)

흐름: HEAD로 모든 이미지 URL 200 + image/jpeg 확인 → 게시 한도 확인 → 장마다 자식 컨테이너
→ 캐러셀 컨테이너 → status_code 폴링(1분 간격, 최대 5분) → media_publish → 원장 기록.

환경변수:
  IG_ACCESS_TOKEN, IG_USER_ID   둘 중 하나라도 없으면 DRY (토큰은 2026-10-26 수령 예정)
  DRY_RUN=1                     네트워크 없이 보낼 내용만 출력

사용:
  python3 scripts/publish_instagram.py                 # 가장 오래된 미발행 덱 1개
  python3 scripts/publish_instagram.py --check-urls    # DRY에서도 HEAD 확인은 한다
  python3 scripts/publish_instagram.py --selftest
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.instagram.com/v1.0"
# apex만. www.inpilot.dev 는 308 리다이렉트라 Meta가 9004로 실패한다.
BASE = "https://inpilot.dev/cards"
CARDS = Path(__file__).resolve().parent.parent / "public" / "cards"
LEDGER = CARDS.parent.parent / "drafts" / "cards" / ".published.json"
MAX_CAPTION, MAX_TAGS = 2200, 30
MIN_CARDS, MAX_CARDS = 2, 10          # API 캐러셀 범위
POLL_SEC, POLL_TRIES = 60, 5          # 공식 권장: 1분에 한 번, 5분 이하
IMG_RE = re.compile(r"^\d\d\.jpg$")
TAG_RE = re.compile(r"#\w+")


def _http(url: str, method: str = "GET", data: dict | None = None):
    """(최종 URL, 헤더, 본문 dict|None). 오류 본문을 붙여 올린다 — Meta는 400 원인을 JSON으로 준다."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read() if method != "HEAD" else b""
            return r.geturl(), r.headers, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        # 토큰이 URL 쿼리에 있으므로 경로만 보여준다
        raise RuntimeError(f"{method} {url.split('?')[0]} → HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:     # 행사장·러너 네트워크 문제도 같은 실패 경로로
        raise RuntimeError(f"{method} {url.split('?')[0]} → {e.reason}") from None


def _graph(path: str, token: str, method: str = "GET", **params) -> dict:
    params["access_token"] = token
    if method == "POST":
        return _http(f"{API}/{path}", "POST", params)[2]
    return _http(f"{API}/{path}?{urllib.parse.urlencode(params)}")[2]


def load_ledger() -> dict:
    """없으면 빈 원장. 깨진 파일은 죽는다 — 빈 원장으로 넘어가면 이미 나간 덱이 다시 나간다."""
    try:
        led = json.loads(LEDGER.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(led, dict):   # `[]` 은 파싱은 되지만 "전부 미발행" 으로 읽힌다 — 같은 위험이다
        raise ValueError(f"{LEDGER}: 장부가 객체가 아니다 ({type(led).__name__})")
    return led


def save_ledger(ledger: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def next_deck(ledger: dict, skip: set[str] = frozenset()) -> str | None:
    # ponytail: 실행당 1덱, 슬러그 이름순을 "오래된 순"으로 본다 (슬러그가 날짜로 시작한다는 가정).
    # 하루 여러 덱이 필요해지면 루프를 돌리고, 슬러그 규칙이 바뀌면 커밋 시각으로 정렬할 것.
    if not CARDS.is_dir():
        return None
    for d in sorted(p for p in CARDS.iterdir() if p.is_dir()):
        if d.name not in ledger and d.name not in skip and (d / "caption.txt").is_file() and any(
                IMG_RE.match(f.name) for f in d.iterdir()):
            return d.name
    return None


def load_deck(slug: str) -> tuple[list[str], str]:
    """(이미지 URL 목록, 캡션). 한도를 넘으면 조용히 자르지 않고 ValueError."""
    d = CARDS / slug
    names = sorted(f.name for f in d.iterdir() if IMG_RE.match(f.name))
    if not MIN_CARDS <= len(names) <= MAX_CARDS:
        raise ValueError(f"{slug}: 카드 {len(names)}장 — 캐러셀은 {MIN_CARDS}~{MAX_CARDS}장")
    caption = (d / "caption.txt").read_text(encoding="utf-8").strip()
    tags = len(TAG_RE.findall(caption))
    if len(caption) > MAX_CAPTION:
        raise ValueError(f"{slug}: 캡션 {len(caption)}자 > {MAX_CAPTION}")
    if tags > MAX_TAGS:
        raise ValueError(f"{slug}: 해시태그 {tags}개 > {MAX_TAGS}")
    return [f"{BASE}/{slug}/{n}" for n in names], caption


def check_urls(urls: list[str]) -> None:
    """배포 전이면 404. 리다이렉트가 끼어도 Meta가 실패하므로 최종 URL이 같아야 한다."""
    for u in urls:
        final, headers, _ = _http(u, "HEAD")
        ctype = headers.get("content-type", "")
        if final != u or not ctype.startswith("image/jpeg"):
            raise ValueError(f"{u}: 최종 {final}, content-type {ctype!r} — apex 200 image/jpeg 필요")


def check_quota(user: str, token: str) -> None:
    """quota_total 은 문서끼리 100/50으로 어긋나서 응답값을 그대로 믿는다."""
    lim = _graph(f"{user}/content_publishing_limit", token, fields="quota_usage,config")["data"][0]
    used, total = lim.get("quota_usage", 0), lim.get("config", {}).get("quota_total", 0)
    if used >= total:
        raise RuntimeError(f"게시 한도 소진 {used}/{total} (24h 이동 창)")


def publish(urls: list[str], caption: str, user: str, token: str) -> str:
    children = [_graph(f"{user}/media", token, "POST", image_url=u, is_carousel_item="true")["id"]
                for u in urls]
    cid = _graph(f"{user}/media", token, "POST", media_type="CAROUSEL",
                 children=",".join(children), caption=caption)["id"]
    for _ in range(POLL_TRIES):
        time.sleep(POLL_SEC)
        status = _graph(cid, token, fields="status_code").get("status_code")
        print(f"  컨테이너 {cid}: {status}")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"컨테이너 {cid} {status}")
    else:
        raise RuntimeError(f"컨테이너 {cid} {POLL_TRIES}분 안에 FINISHED 안 됨")
    return _graph(f"{user}/media_publish", token, "POST", creation_id=cid)["id"]


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    token, user = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_USER_ID", "")
    dry = os.environ.get("DRY_RUN") == "1" or not token or not user

    ledger = load_ledger()
    # 한도를 넘는 덱(장수·캡션)은 건너뛰고 다음 덱으로 — 하나가 큐 전체를 막지 않게(리뷰 2026-09-18).
    # 원장엔 안 남긴다: 사람이 덱을 고치면 다음 실행이 그대로 집는다.
    bad: set[str] = set()
    while True:
        slug = next_deck(ledger, bad)
        if not slug:
            print("발행할 덱 없음" + (f" (한도 초과로 건너뜀: {', '.join(sorted(bad))})" if bad else ""))
            return 1 if bad else 0
        try:
            urls, caption = load_deck(slug)
            break
        except ValueError as e:
            print(f"건너뜀: {e}", file=sys.stderr)
            bad.add(slug)
    try:
        print(f"덱 {slug}: {len(urls)}장 · 캡션 {len(caption)}자 · 해시태그 "
              f"{len(TAG_RE.findall(caption))}개")
        for u in urls:
            print(f"  {u}")
        if not dry or "--check-urls" in argv:
            check_urls(urls)
            print("  이미지 URL 전부 200 image/jpeg")
        if not dry:
            check_quota(user, token)
    except (ValueError, RuntimeError) as e:
        print(f"거부: {e}", file=sys.stderr)
        return 1
    if dry:
        print(f"[DRY] 게시 안 함{'' if token and user else ' (IG_ACCESS_TOKEN/IG_USER_ID 없음)'}")
        return 0

    entry = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        mid = publish(urls, caption, user, token)
        entry.update(status="published", media_id=mid)
        try:
            entry["permalink"] = _graph(mid, token, fields="permalink").get("permalink", "")
        except Exception:  # noqa: BLE001  링크는 부가 정보 — 없어도 게시는 끝났다
            pass
        print(f"게시됨: {mid} {entry.get('permalink', '')}")
    except Exception as e:  # noqa: BLE001
        # urllib 은 응답 단계 오류(타임아웃·연결 끊김)를 URLError 로 감싸지 않고, 본문이 JSON 이 아닐 수도 있다.
        # 무엇이 터지든 원장에 남겨야 한다 — Meta 쪽은 게시됐는데 원장이 비면 다음 실행이 또 올린다(리뷰 2026-09-18).
        # 실패도 원장에 남긴다 → 다음 실행이 자동 재시도하지 않는다(중복 게시 방지).
        # 재시도하려면 원장에서 그 슬러그 항목을 지운다.
        entry.update(status="failed", media_id=None, error=str(e)[:300])
        print(f"실패: {e}", file=sys.stderr)
    ledger[slug] = entry
    save_ledger(ledger)
    return 0 if entry["status"] == "published" else 1


def selftest() -> int:
    import io
    import tempfile
    from contextlib import redirect_stderr, redirect_stdout
    from email.message import Message

    global CARDS, LEDGER, POLL_SEC
    calls: list[tuple[str, str, dict]] = []
    state = {"quota": 0, "status": ["IN_PROGRESS", "FINISHED"], "ctype": "image/jpeg", "redirect": False}

    class Resp:
        def __init__(self, url, body, ctype="application/json"):
            self._url, self._body = url, json.dumps(body).encode() if body is not None else b""
            self.headers = Message()
            self.headers["content-type"] = ctype
        def read(self): return self._body
        def geturl(self): return self._url
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        url, method = req.full_url, req.get_method()
        data = dict(urllib.parse.parse_qsl(req.data.decode())) if req.data else {}
        calls.append((method, url.split("?")[0], data))
        if method == "HEAD":
            final = url.replace("https://inpilot", "https://www.inpilot") if state["redirect"] else url
            return Resp(final, None, state["ctype"])
        path = url.split("?")[0].removeprefix(API + "/")
        if path.endswith("content_publishing_limit"):
            return Resp(url, {"data": [{"quota_usage": state["quota"], "config": {"quota_total": 100}}]})
        if path.endswith("/media"):
            return Resp(url, {"id": "car" if data.get("media_type") == "CAROUSEL" else f"c{len(calls)}"})
        if path.endswith("media_publish"):
            return Resp(url, {"id": "M1"})
        if "fields=status_code" in url:
            return Resp(url, {"status_code": state["status"].pop(0)})
        if "fields=permalink" in url:
            return Resp(url, {"permalink": "https://instagram.com/p/x"})
        raise AssertionError(url)

    real_urlopen, real_env = urllib.request.urlopen, dict(os.environ)
    urllib.request.urlopen, POLL_SEC = fake_urlopen, 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            CARDS = Path(tmp) / "public" / "cards"
            CARDS.mkdir(parents=True)
            LEDGER = Path(tmp) / "drafts" / "cards" / ".published.json"

            def deck(slug, n, caption="본문 #a #b"):
                (CARDS / slug).mkdir()
                for i in range(1, n + 1):
                    (CARDS / slug / f"{i:02d}.jpg").write_bytes(b"x")
                (CARDS / slug / "caption.txt").write_text(caption, encoding="utf-8")

            def run(*args):
                with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                    code = main(["x", *args])
                return code, out.getvalue() + err.getvalue()

            deck("2026-10-02-b", 3)
            deck("2026-10-01-a", 2)
            (CARDS / "2026-09-30-empty").mkdir()        # 카드 없는 폴더는 후보 아님

            # DRY(토큰 없음): 가장 오래된 덱, 네트워크 0회
            for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "DRY_RUN"):
                os.environ.pop(k, None)
            code, out = run()
            assert code == 0 and not calls, (code, calls)
            assert "https://inpilot.dev/cards/2026-10-01-a/01.jpg" in out and "캡션 8자" in out, out
            assert "해시태그 2개" in out and "[DRY]" in out, out
            assert not LEDGER.exists()

            # DRY + --check-urls: HEAD만, 리다이렉트·content-type 틀리면 거부
            code, _ = run("--check-urls")
            assert code == 0 and [c[0] for c in calls] == ["HEAD", "HEAD"], calls
            state["redirect"] = True
            assert run("--check-urls")[0] == 1
            state["redirect"], state["ctype"] = False, "text/html"
            assert run("--check-urls")[0] == 1
            state["ctype"] = "image/jpeg"

            # 실게시(가짜 네트워크): HEAD 2 → 한도 → 자식 2 → 캐러셀 → 폴링 2 → publish → permalink
            os.environ.update(IG_ACCESS_TOKEN="SECRET-TOK", IG_USER_ID="u")
            calls.clear()
            code, out = run()
            assert code == 0, out
            posts = [c[2] for c in calls if c[0] == "POST"]
            assert [p.get("is_carousel_item") for p in posts[:2]] == ["true", "true"], posts
            assert posts[2]["media_type"] == "CAROUSEL" and posts[2]["children"].count(",") == 1
            assert posts[2]["caption"] == "본문 #a #b" and posts[3]["creation_id"] == "car", posts
            led = json.loads(LEDGER.read_text())
            assert led["2026-10-01-a"]["status"] == "published", led
            assert led["2026-10-01-a"]["media_id"] == "M1" and led["2026-10-01-a"]["permalink"]
            assert "SECRET-TOK" not in LEDGER.read_text() + out   # 토큰이 원장·로그에 새지 않는다

            # 원장에 있는 덱은 건너뛰고 다음 덱. ERROR → failed 기록, exit 1
            state["status"] = ["ERROR"]
            calls.clear()
            code, out = run()
            assert code == 1 and "SECRET-TOK" not in out + LEDGER.read_text()
            assert json.loads(LEDGER.read_text())["2026-10-02-b"]["status"] == "failed"
            assert run()[1].strip() == "발행할 덱 없음"

            # 한도 소진이면 컨테이너를 만들지 않는다
            deck("2026-10-03-c", 2)
            state["quota"] = 100
            calls.clear()
            assert run()[0] == 1
            assert not [c for c in calls if c[0] == "POST"], calls
            assert "2026-10-03-c" not in json.loads(LEDGER.read_text())   # 아무것도 안 보냈으니 원장에 안 남긴다
            state["quota"] = 0

            # 응답 단계 예외(타임아웃 등 RuntimeError 가 아닌 것)도 failed 로 원장에 남는다
            real_publish = globals()["publish"]
            globals()["publish"] = lambda *a: (_ for _ in ()).throw(TimeoutError("read timed out"))
            code, _ = run()
            assert code == 1 and json.loads(LEDGER.read_text())["2026-10-03-c"]["status"] == "failed"
            globals()["publish"] = real_publish
            led = json.loads(LEDGER.read_text()); del led["2026-10-03-c"]; LEDGER.write_text(json.dumps(led))

            # 캡션·장수 한도: 자르지 않고 거부. 나쁜 덱은 건너뛰고 다음 덱은 나간다
            (CARDS / "2026-10-03-c" / "caption.txt").write_text("가" * 2201, encoding="utf-8")
            os.environ["DRY_RUN"] = "1"
            assert run()[0] == 1
            deck("2026-10-04-d", 2)
            code, out = run()
            assert code == 0 and "건너뜀" in out and "2026-10-04-d/01.jpg" in out, out
            import shutil; shutil.rmtree(CARDS / "2026-10-04-d")
            (CARDS / "2026-10-03-c" / "caption.txt").write_text(
                " ".join(f"#t{i}" for i in range(31)), encoding="utf-8")
            assert run()[0] == 1
            try:
                deck("x-11", 11); load_deck("x-11"); raise AssertionError("11장 통과")
            except ValueError:
                pass

            # 깨진 원장·객체 아닌 원장은 죽는다
            for bad_json in ("{broken", "[]"):
                LEDGER.write_text(bad_json)
                try:
                    load_ledger(); raise AssertionError(f"깨진 원장 통과: {bad_json}")
                except ValueError:   # JSONDecodeError 도 ValueError 다
                    pass
    finally:
        urllib.request.urlopen = real_urlopen
        os.environ.clear(); os.environ.update(real_env)
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
