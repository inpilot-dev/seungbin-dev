"""LLM 한 콜 — claude -p(구독) 우선, 없거나 실패하면 ollama(qwen2.5:7b) 로컬 폴백.

scripts/ 의 다섯 도구가 전부 같은 두 줄을 복붙하고 있어서 여기로 모았다.
반환은 문자열 또는 None. None 이면 호출자가 "LLM 없이" 경로로 내려간다 —
요약·판정은 부가가치지 전제가 아니다 (collect_digest.py 원칙 그대로).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

# 구독(CLAUDE_CODE_OAUTH_TOKEN)이라 토큰당 청구가 없다 — 싼 모델을 고를 이유가 없어 전부 이 한 모델로 (2026-09-24 사용자 결정).
# 대가는 구독 사용량 한도가 더 빨리 찬다는 것뿐이고, 한도에 걸리면 아래 재시도 → 실패 알림으로 끝난다(대충 만든 글이 나가진 않는다).
CLAUDE_MODEL = "claude-opus-5-5"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_URL = "http://localhost:11434/api/generate"
# 2026-09-18 실측: 구독 사용량 한도에 걸리면 `claude -p` 가 exit 1 로 **즉시** 죽고 사유는 stdout 에 쓴다.
# stderr 만 찍던 로그는 빈 줄이었고, 호출자는 "주제에 맞는 항목이 없다" 로 오진했다. 한도는 시간이 풀어 주는
# 문제라 몇 분 뒤 재시도한다. 로컬 테스트가 느려지지 않게 횟수는 env 로 끈다 (LLM_LIMIT_RETRIES=0).
LIMIT_RE = re.compile(r"limit|rate|429|overloaded|capacity|too many", re.I)
LIMIT_RETRIES = int(os.environ.get("LLM_LIMIT_RETRIES", "2"))
LIMIT_WAIT_SEC = 300


def ask(prompt: str, timeout: int = 300, model: str = CLAUDE_MODEL) -> str | None:
    if shutil.which("claude"):
        for attempt in range(LIMIT_RETRIES + 1):
            try:
                r = subprocess.run(["claude", "-p", "--model", model], input=prompt,
                                   capture_output=True, text=True, timeout=timeout)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout
                msg = (r.stderr.strip() or r.stdout.strip())[:200]
                print(f"claude -p 실패 (exit {r.returncode}): {msg}", file=sys.stderr)
                if attempt < LIMIT_RETRIES and LIMIT_RE.search(msg):
                    print(f"  한도로 보인다 — {LIMIT_WAIT_SEC}초 뒤 재시도 ({attempt + 1}/{LIMIT_RETRIES})", file=sys.stderr)
                    time.sleep(LIMIT_WAIT_SEC)
                    continue
                break
            except Exception as e:
                print(f"claude -p 예외 ({e})", file=sys.stderr)
                break
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["response"]
    except Exception as e:
        print(f"ollama 폴백 실패 ({e})", file=sys.stderr)
        return None


def which() -> str:
    """무엇이 응답할지 미리 알려준다 (로그·한계 문서용)."""
    if shutil.which("claude"):
        return "claude -p"
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return "ollama"
    except Exception:
        return "none"
