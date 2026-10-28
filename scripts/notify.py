#!/usr/bin/env python3
"""알림 한 통 — 디스코드 웹후크(기본) / 텔레그램 / 둘 다 (2026-10-28, 디스코드 이전 2단계).

.github/actions/telegram 과 comment_assist.py 가 이것 하나로 보낸다. 어디로 보낼지는 값 하나로 고른다:
  NOTIFY_CHANNEL        discord(비면 이것) · telegram · both — 1주 같이 켜기·되돌리기용(계획 §5)
  DISCORD_WEBHOOK_URL   채널 웹후크. **주소 자체가 쓰기 권한이다** — secret·.env 에만. 로그·예외에 한 글자도 안 찍는다
  TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID   telegram·both 일 때
고른 곳의 값이 없으면 조용히 생략한다 — 알림은 부가가치지 전제가 아니다.

디스코드: 2000자를 넘으면 줄 단위로 나눠 여러 통(글자를 버리지 않는다) · 멘션 끔 · 링크 미리보기 끔 ·
글자는 마크다운 이스케이프(텔레그램 때처럼 평문으로 보이게, URL 은 그대로) · 429 는 retry_after 만큼 쉬고 한 번 더.
참고 구현: brain-secretary/secretary.py 의 _split·_md_escape·discord_send·_discord.

사용:
  NOTIFY_TEXT="…" python3 scripts/notify.py   # 문장은 env 로만 받는다(argv 는 프로세스 목록에 보인다). 항상 0
  python3 scripts/notify.py --selftest         # 127.0.0.1 가짜 서버만 쓴다 — 진짜 웹후크·.env 는 안 읽는다
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ENV_KEYS = ("NOTIFY_CHANNEL", "DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
TG_API = "https://api.telegram.org"
UA = "DiscordBot (https://github.com/inpilot-dev/seungbin-dev, 1)"   # 기본 Python-urllib UA 는 Cloudflare 가 403 으로 막는다
DISCORD_LIMIT, TG_LIMIT = 2000, 4000
SUPPRESS_EMBEDS = 1 << 2
_MD = re.compile(r"([\\*_~`|<>\[\]#])")
_URL = re.compile(r"(https?://\S+)")
FAKE_SECRET = "hook-SECRET-do-not-print"


def split(text: str, limit: int) -> list[str]:
    """줄 단위로 limit 안에 담는다. 줄 하나가 limit 를 넘으면 그 줄만 자른다 — 어느 경우에도 글자를 버리지 않는다."""
    out, cur = [], None
    for line in text.split("\n"):
        while len(line) > limit:   # ponytail: 이스케이프 `\` 와 그 글자 사이에서 잘릴 수 있다 — 2000자 줄은 없다
            if cur is not None:
                out.append(cur)
                cur = None
            out.append(line[:limit])
            line = line[limit:]
        if cur is not None and len(cur) + 1 + len(line) > limit:
            out.append(cur)
            cur = line
        else:
            cur = line if cur is None else f"{cur}\n{line}"
    return out + [cur] if cur else out


def md_escape(text: str) -> str:
    """텔레그램 때처럼 평문으로 보이게 — `#` 제목·`[a](b)` 링크 가리기·`<@id>` 까지. URL 조각은 그대로 둔다(눌려야 한다)."""
    return "".join(p if i % 2 else _MD.sub(r"\\\1", p) for i, p in enumerate(_URL.split(text)))


def _post(url: str, body: bytes, ctype: str, what: str) -> None:
    """POST 한 번. url 에 비밀(웹후크 주소·봇 토큰)이 있다 — 예외 문장엔 `what` 과 상태 코드·예외 타입만 싣는다.
    셋 다 `from None`: 체이닝하면 원인 예외(HTTPError.url·InvalidURL 문장)에 주소가 살아 있다. 429 는 retry_after 만큼 쉬고 한 번 더."""
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype, "User-Agent": UA}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
            return
        except urllib.error.HTTPError as e:
            wait = None
            if e.code == 429 and attempt == 1:
                try:   # ponytail: 60초에서 자른다 — 그보다 길면 다시 해도 429 라 실패로 끝난다
                    wait = min(float(json.loads(e.read())["retry_after"]), 60.0)
                except Exception:  # noqa: BLE001
                    wait = 1.0
            e.close()
            if wait is None:
                raise RuntimeError(f"{what} HTTP {e.code}") from None
        except Exception as e:  # noqa: BLE001 — URLError·타임아웃·InvalidURL. 문장에 주소가 섞일 수 있어 타입만
            raise RuntimeError(f"{what} 실패 ({type(e).__name__})") from None
        time.sleep(wait)


def _discord(text: str, url: str) -> None:
    for part in split(md_escape(text), DISCORD_LIMIT):
        payload = {"content": part, "allowed_mentions": {"parse": []}, "flags": SUPPRESS_EMBEDS}
        _post(url, json.dumps(payload).encode(), "application/json", "discord")


def _telegram(text: str, token: str, chat: str) -> None:
    for part in split(text, TG_LIMIT):   # 평문(parse_mode 없음) — 이스케이프가 필요 없다
        body = urllib.parse.urlencode({"chat_id": chat, "text": part, "disable_web_page_preview": "true"}).encode()
        _post(f"{TG_API}/bot{token}/sendMessage", body, "application/x-www-form-urlencoded", "telegram")


def _channels() -> list[str]:
    ch = os.environ.get("NOTIFY_CHANNEL", "").strip().lower() or "discord"
    return {"discord": ["discord"], "telegram": ["telegram"], "both": ["discord", "telegram"]}.get(ch, [ch])


def send(text: str) -> tuple[list[str], list[str]]:
    """(보낸 곳, 실패 사유). 고른 곳의 값이 없으면 둘 다 비어 있다 = 미연결. 한쪽이 죽어도 다른 쪽은 보낸다."""
    sent, errors = [], []
    if not text.strip():
        return sent, errors
    env = {k: os.environ.get(k, "").strip() for k in ENV_KEYS}   # secret 끝에 붙어 온 줄바꿈은 떼어 낸다
    for ch in _channels():
        try:
            if ch == "discord" and env["DISCORD_WEBHOOK_URL"]:
                _discord(text, env["DISCORD_WEBHOOK_URL"])
            elif ch == "telegram" and env["TELEGRAM_BOT_TOKEN"] and env["TELEGRAM_CHAT_ID"]:
                _telegram(text, env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"])
            elif ch not in ("discord", "telegram"):
                errors.append(f"NOTIFY_CHANNEL={ch} 은 모른다 — discord·telegram·both")
                continue
            else:
                continue
            sent.append(ch)
        except RuntimeError as e:
            errors.append(str(e))
    return sent, errors


def main(argv: list[str]) -> int:
    """액션에서 부른다. 알림 실패로 워크플로를 빨갛게 만들지 않는다 — 항상 0, 결과만 한 줄씩."""
    sent, errors = send(os.environ.get("NOTIFY_TEXT", ""))
    for ch in sent:
        print(f"{ch} 보냄")
    for e in errors:
        print(f"::warning title=알림 실패::{e}")
    if not sent and not errors:
        need = {"discord": "DISCORD_WEBHOOK_URL", "telegram": "TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID"}
        print(f"::notice title=알림 생략::{' · '.join(need[c] for c in _channels())} 가 없다(NOTIFY_CHANNEL)")
    return 0


class FakeHook:
    """selftest 용 127.0.0.1 가짜 서버 — 진짜 디스코드·텔레그램엔 닿지 않는다.
    받은 POST 는 posts 에 (경로, 헤더, 본문)으로 쌓고, replies 의 (코드, 본문)을 차례로 돌려준다 — 비면 204."""

    def __enter__(self):
        hook, self.posts, self.replies = self, [], []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                hook.posts.append((self.path, dict(self.headers), raw))
                code, body = hook.replies.pop(0) if hook.replies else (204, b"")
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):   # 기본 접근 로그는 경로(=웹후크 비밀)를 stderr 에 찍는다
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"
        self.url = f"{self.base}/api/webhooks/1/{FAKE_SECRET}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()
        return False


def selftest() -> int:
    import contextlib
    import io

    saved = ({k: os.environ.get(k) for k in ENV_KEYS}, TG_API)
    for k in ENV_KEYS:
        os.environ.pop(k, None)

    def cli(text: str) -> str:
        """CLI 한 번 — stdout·stderr 를 같이 잡는다(Actions 로그에는 둘 다 실린다)."""
        buf = io.StringIO()
        os.environ["NOTIFY_TEXT"] = text
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            assert main(["x"]) == 0
        return buf.getvalue()

    def t_split():
        # 줄 단위로 나눈다 · 한 줄이 한도를 넘으면 그 줄만 자른다 · 어느 경우에도 글자를 버리지 않는다
        text = "\n".join(["가" * 900] * 5 + ["나" * 4500] + ["끝"])
        parts = split(text, 2000)
        assert all(len(p) <= 2000 for p in parts), [len(p) for p in parts]
        assert "".join(parts).replace("\n", "") == text.replace("\n", "")   # 자른 줄은 조각 사이에 줄이 바뀔 뿐
        assert parts[0] == "\n".join(["가" * 900] * 2) and parts[-1] == "나" * 500 + "\n끝"
        short = "\n".join(["다" * 300] * 20)
        assert "\n".join(split(short, 2000)) == short   # 자를 줄이 없으면 그대로 이어 붙는다
        assert split("", 2000) == [] and split("a\n\nb", 2000) == ["a\n\nb"]

    def t_md_escape():
        # 남이 쓴 글자가 마크다운으로 읽히지 않게 — URL 은 그대로 둬야 눌린다
        assert md_escape("# 제목 *굵게* [a](b) <@1> under_score") == r"\# 제목 \*굵게\* \[a\](b) \<@1\> under\_score"
        assert md_escape("PR https://github.com/x/y_z/pull/1 끝_") == r"PR https://github.com/x/y_z/pull/1 끝\_"

    def t_discord_payload():
        with FakeHook() as hook:
            os.environ["DISCORD_WEBHOOK_URL"] = hook.url
            text = "[슬롯] *별*\n" + "\n".join(f"{i:04d} " + "가" * 95 for i in range(50))   # 약 5,000자
            assert send(text) == (["discord"], [])
            bodies = [json.loads(b) for _, _, b in hook.posts]
            assert len(bodies) == 3 and all(len(b["content"]) <= DISCORD_LIMIT for b in bodies)
            assert "\n".join(b["content"] for b in bodies) == md_escape(text)   # 버린 글자 없음
            assert all(b["allowed_mentions"] == {"parse": []} and b["flags"] == SUPPRESS_EMBEDS for b in bodies)
            path, headers, _ = hook.posts[0]
            assert path == f"/api/webhooks/1/{FAKE_SECRET}" and headers["Content-Type"] == "application/json"
            assert headers["User-Agent"].startswith("DiscordBot")
            hook.posts.clear()
            assert send(" \n ") == ([], []) and not hook.posts   # 빈 글은 안 보낸다

    def t_retry_429():
        with FakeHook() as hook:
            os.environ["DISCORD_WEBHOOK_URL"] = hook.url
            hook.replies[:] = [(429, b'{"retry_after": 0.05}')]
            t0 = time.monotonic()
            assert send("한 번 더") == (["discord"], []) and len(hook.posts) == 2
            assert time.monotonic() - t0 >= 0.05
            hook.posts.clear()
            hook.replies[:] = [(429, b'{"retry_after": 0.01}')] * 2   # 두 번째도 429 면 실패로 끝난다(세 번은 안 한다)
            assert send("또") == ([], ["discord HTTP 429"]) and len(hook.posts) == 2

    def t_no_leak():
        # 주소 비노출: 성공·404·429×2·연결 거부·제어문자 섞인 주소 — 어떤 결과·CLI 출력에도 웹후크 비밀이 없다
        with FakeHook() as hook:
            outs = []
            os.environ["DISCORD_WEBHOOK_URL"] = hook.url
            outs.append(cli("성공"))
            hook.replies[:] = [(404, b'{"message": "Unknown Webhook"}')]
            outs.append(cli("404"))
            hook.replies[:] = [(429, b'{"retry_after": 0.01}')] * 2
            outs.append(cli("429"))
            os.environ["DISCORD_WEBHOOK_URL"] = hook.url + "\r\nX: y"   # secret 에 줄바꿈이 섞여 들어간 경우
            res = send("제어문자")
            outs.append(repr(res))
            assert res[0] == [] and res[1] and res[1][0].startswith("discord 실패"), res
            outs.append(cli("제어문자"))
        os.environ["DISCORD_WEBHOOK_URL"] = f"http://127.0.0.1:1/api/webhooks/1/{FAKE_SECRET}"   # 아무도 안 듣는 포트
        res = send("연결 거부")
        outs.append(repr(res))
        assert res[0] == [] and res[1][0].startswith("discord 실패"), res
        outs.append(cli("연결 거부"))
        assert "discord 보냄" in outs[0] and "discord HTTP 404" in outs[1] and "discord HTTP 429" in outs[2], outs
        for o in outs:
            assert FAKE_SECRET not in o and "/api/webhooks/" not in o, o

    def t_channel():
        # NOTIFY_CHANNEL 하나로 고른다 — 비면 discord · telegram · both · 모르는 값은 실패로 알린다
        global TG_API
        with FakeHook() as hook:
            TG_API = hook.base
            os.environ.update(DISCORD_WEBHOOK_URL=hook.url, TELEGRAM_BOT_TOKEN="BOT-SECRET", TELEGRAM_CHAT_ID="42")
            assert send("기본") == (["discord"], []) and len(hook.posts) == 1
            os.environ["NOTIFY_CHANNEL"] = "telegram"
            hook.posts.clear()
            assert send("*평문*") == (["telegram"], [])
            path, _, raw = hook.posts[0]
            form = dict(urllib.parse.parse_qsl(raw.decode()))
            assert path == "/botBOT-SECRET/sendMessage" and form == {"chat_id": "42", "text": "*평문*", "disable_web_page_preview": "true"}
            os.environ["NOTIFY_CHANNEL"] = "both"
            hook.posts.clear()
            assert send("둘 다") == (["discord", "telegram"], []) and len(hook.posts) == 2
            hook.replies[:] = [(500, b"")]   # 한쪽이 죽어도 다른 쪽은 보낸다
            assert send("반쪽") == (["telegram"], ["discord HTTP 500"])
            hook.replies[:] = [(204, b""), (401, b"")]
            out = cli("텔레그램 401")
            assert "telegram HTTP 401" in out and "BOT-SECRET" not in out, out
            os.environ["NOTIFY_CHANNEL"] = "slack"
            assert send("x") == ([], ["NOTIFY_CHANNEL=slack 은 모른다 — discord·telegram·both"])
            os.environ["NOTIFY_CHANNEL"] = " Discord "
            assert send("대소문자") == (["discord"], [])
        # 고른 곳의 값이 없으면 조용히 생략 — 실패가 아니다
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        assert send("미연결") == ([], [])
        out = cli("미연결")
        assert "알림 생략" in out and "DISCORD_WEBHOOK_URL" in out, out

    def t_action():
        # 액션 배선 + set -x 비노출: action.yml 의 run 줄을 bash -x 로 그대로 돌린다 — 주소는 env 로만 흘러 명령줄에 안 실린다
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        action = os.path.join(root, ".github", "actions", "telegram")
        run = re.search(r"^\s*run: (.+)$", open(os.path.join(action, "action.yml"), encoding="utf-8").read(), re.M).group(1)
        with FakeHook() as hook:
            env = {"PATH": os.environ.get("PATH", ""), "GITHUB_ACTION_PATH": action,
                   "DISCORD_WEBHOOK_URL": hook.url, "NOTIFY_CHANNEL": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
                   "NOTIFY_TEXT": "[액션] 한 줄"}
            p = subprocess.run(["bash", "-xc", run], env=env, capture_output=True, text=True, timeout=30)
            out = p.stdout + p.stderr
            assert p.returncode == 0 and "discord 보냄" in out and len(hook.posts) == 1, out
            assert json.loads(hook.posts[0][2])["content"] == r"\[액션\] 한 줄"
            assert FAKE_SECRET not in out and "/api/webhooks/" not in out, out

    try:
        for t in (t_split, t_md_escape, t_discord_payload, t_retry_429, t_no_leak, t_channel, t_action):
            t()
            print(f"ok {t.__name__}")
    finally:
        os.environ.pop("NOTIFY_TEXT", None)
        for k, v in saved[0].items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        globals()["TG_API"] = saved[1]
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv))
