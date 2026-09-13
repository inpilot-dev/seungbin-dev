"""LLM 한 콜 — claude -p(구독) 우선, 없거나 실패하면 ollama(qwen2.5:7b) 로컬 폴백.

scripts/ 의 다섯 도구가 전부 같은 두 줄을 복붙하고 있어서 여기로 모았다.
반환은 문자열 또는 None. None 이면 호출자가 "LLM 없이" 경로로 내려간다 —
요약·판정은 부가가치지 전제가 아니다 (collect_digest.py 원칙 그대로).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request

CLAUDE_MODEL = "claude-haiku-4-5"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_URL = "http://localhost:11434/api/generate"


def ask(prompt: str, timeout: int = 300, model: str = CLAUDE_MODEL) -> str | None:
    if shutil.which("claude"):
        try:
            r = subprocess.run(["claude", "-p", "--model", model], input=prompt,
                               capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
            print(f"claude -p 실패 (exit {r.returncode}): {r.stderr[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"claude -p 예외 ({e})", file=sys.stderr)
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
