#!/usr/bin/env python3
"""내 해석 카드 — 소재 하나로 나를 인터뷰해 카드 원고의 '내 한 줄'을 뽑는다 (D38 · D41, 2026-11-05 grill).

D38: 내 한 줄이 없으면 카드를 만들지 않는다. 이 스크립트는 그 한 줄을 **내 답에서만** 뽑는다.
  1. 소재 URL 을 읽고 질문을 **하나씩** 최대 3개 묻는다(빈 줄 = 그만). 답이 다 비면 원고를 안 만든다.
  2. Claude 가 내 답 문장 중 후보 2~3개를 번호로 고르고, 내가 하나 고른다. 후보는 답 문장 그대로다.
  3. 원고 = original(원본 주장, 내 말로 바꿔 씀) · mine(내 답 문장 그대로) · line · quotes(인용, URL 필수 · 캡처 필요).
     original 의 수치가 소재·답에 없으면 "(확인 필요)" 를 붙인다. → drafts/takes/<날짜>-<슬러그>.json
  4. 검수: --approve / --reject 가 state/takes.jsonl 에 원고째 남긴다. 반려는 지난 이유를 번호로 고르거나 새로 쓴다.
     같은 이유가 2번이 되면 "규칙으로 옮길 것" 을 알린다 — 옮기는 건 사람이 아래 RULES 에 한다.

캡처 찍기 · 카드 렌더 · 카드 끝 검수 표시(「inpilot.dev 검수」)는 card-news 몫이다. 디스코드 창구는 SideHustle 허브 몫이다.
state/takes.jsonl 은 공개 repo 에 커밋된다 — 답·반려 이유가 공개된다(2026-11-05 사용자 선택).

사용:
  python3 scripts/my_take.py <소재 URL>
  python3 scripts/my_take.py --check   drafts/takes/<파일>.json
  python3 scripts/my_take.py --approve drafts/takes/<파일>.json
  python3 scripts/my_take.py --reject  drafts/takes/<파일>.json
  python3 scripts/my_take.py --selftest
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TAKES_DIR = ROOT / "drafts" / "takes"
LOG = ROOT / "state" / "takes.jsonl"
MAX_Q = 3        # 영상은 8개였다 — 카드 한 장에는 많다(요청서 표 1)
WIN = 20         # 원본과 이만큼(공백 정리 후 글자 수) 똑같이 이어지면 옮겨 적은 것으로 본다
CHECK = "확인 필요"
KST = timezone(timedelta(hours=9))
# 반려 이유가 2번 나오면 사람이 여기에 한 줄로 옮긴다(요청서 표 3). 질문·원고 프롬프트 둘 다에 들어간다.
RULES: list[str] = []


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _vals(text: str) -> set[str]:
    # grade.numbers 는 한 자리 수를 안 본다(목록 번호 때문). 카드 주장 줄엔 목록이 없고 "3배" 가 바로 지어낸 수치라 전부 본다
    return {m.replace(",", "").rstrip(".") for m in re.findall(r"\d[\d,.]*", text)}


def sentences(answers: list[str]) -> list[str]:
    return [s.strip() for a in answers for s in re.split(r"(?<=[.!?。])\s+|\n+", a) if s.strip()]


def copied(item: str, src: str) -> bool:
    n, s = _norm(item), _norm(src)
    return any(n[i:i + WIN] in s for i in range(len(n) - WIN + 1))


def check(take: dict, src: str) -> list[str]:
    """탈락 사유 목록. 비어 있으면 통과."""
    said = _norm(" ".join(take.get("answers", [])))
    if not said:
        return ["인터뷰 답이 비었다 — 내 한 줄이 없으면 카드를 만들지 않는다(D38)"]
    fails = []
    line = _norm(take.get("line", ""))
    if not line or line not in said:
        fails.append(f"내 한 줄이 내 답에 없다: {line[:60]!r}")
    fails += [f"내 의견 칸에 내가 안 한 말: {m[:60]!r}" for m in take.get("mine", []) if _norm(m) not in said]
    known = _vals(src) | _vals(said)
    for o in take.get("original", []):
        if copied(o, src):
            fails.append(f"원본 문장을 그대로 옮겼다: {o[:60]!r}")
        if CHECK not in o and (_vals(o) - known):
            fails.append(f"출처 없는 수치 {sorted(_vals(o) - known)}: {o[:60]!r}")
    fails += [f"인용에 URL 이 없다: {q.get('text', '')[:60]!r}"
              for q in take.get("quotes", []) if not str(q.get("url", "")).startswith("http")]
    return fails


def mark(take: dict, src: str) -> dict:
    """소재·답에 없는 수치가 든 original 줄에 "(확인 필요)" 를 붙인다. 지우지 않는다 — 사람이 확인한다."""
    known = _vals(src) | _vals(" ".join(take.get("answers", [])))
    orig = [o if CHECK in o or not (_vals(o) - known) else f"{o} ({CHECK})" for o in take.get("original", [])]
    return {**take, "original": orig}


def _rules() -> str:
    return "\n".join(f"- {r}" for r in RULES)


def _qa_text(qa: list[tuple[str, str]]) -> str:
    return "\n".join(f"Q{i}. {q}\nA{i}. {a}" for i, (q, a) in enumerate(qa, 1)) or "(아직 없음)"


def question_prompt(url: str, src: str, qa: list[tuple[str, str]]) -> str:
    return f"""너는 인터뷰어다. 아래 소재를 읽은 사람에게서 그 사람만의 해석 한 줄을 끌어내려 한다.
질문 하나만 한 문장으로 출력해라. 다른 말은 쓰지 마라.
- 소재를 요약하거나 네 의견을 말하지 않는다.
- 그 사람의 경험 · 판단 · 반대 의견을 묻는다. 예/아니오로 끝나는 질문은 피한다.
- 앞 질문과 겹치지 않는다. 앞 답에 더 파고들 곳이 있으면 거기를 묻는다.
{_rules()}

[소재 {url}]
{src}

[지금까지 문답]
{_qa_text(qa)}"""


def draft_prompt(url: str, src: str, qa: list[tuple[str, str]], sents: list[str]) -> str:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sents))
    return f"""아래 소재와 인터뷰 답으로 카드 원고 재료를 JSON 하나로만 출력해라. 다른 말은 쓰지 마라.
{{"candidates": [번호, ...], "original": ["...", ...], "quotes": [{{"text": "...", "url": "..."}}]}}
- candidates: [답 문장] 중 카드의 '내 한 줄'로 쓸 만한 것 2~3개의 번호. 문장은 고치지 않는다.
- original: 소재의 핵심 주장 2~4개. 네 말로 바꿔 쓴다 — 소재 문장을 그대로 옮기지 않는다. 소재에 없는 수치는 쓰지 않는다.
- quotes: 원문 그대로 인용해야 하는 문장이 있을 때만. url 은 그 문장이 실린 곳. 없으면 [].
- 답에 없는 경험 · 수치를 지어내지 않는다.
{_rules()}

[소재 {url}]
{src}

[문답]
{_qa_text(qa)}

[답 문장]
{numbered}"""


def make(url: str, src: str, qa: list[tuple[str, str]], choose, ask=llm.ask) -> dict | None:
    """원고 dict. 답이 다 비면 None(LLM 도 안 부른다). choose(후보 문장 목록) → 고른 위치."""
    sents = sentences([a for _, a in qa])
    if not sents:
        return None
    out = ask(draft_prompt(url, src, qa, sents))
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:   # 무응답을 "후보 없음" 으로 바꾸지 않는다 — 판정 불가로 멈춘다
        raise RuntimeError(f"원고 재료를 못 받았다(LLM 응답이 JSON 이 아니다): {(out or '')[:120]!r}")
    data = json.loads(m.group(0))
    cands = [sents[i] for i in data.get("candidates", []) if isinstance(i, int) and 0 <= i < len(sents)][:3] or sents
    take = {"url": url, "at": datetime.now(KST).isoformat(timespec="seconds"),
            "questions": [q for q, _ in qa], "answers": [a for _, a in qa],
            "line": cands[choose(cands)], "mine": sents,
            "original": [str(o) for o in data.get("original", [])],
            "quotes": [{"text": q.get("text", ""), "url": q.get("url", ""), "capture": "필요"}
                       for q in data.get("quotes", []) if isinstance(q, dict)]}
    return mark(take, src)


def record(path: Path, take: dict, verdict: str, reason: str | None = None) -> int:
    """승인본·반려본을 한 줄로 남긴다. 반려이면 같은 이유가 몇 번째인지 돌려준다."""
    if verdict == "rejected" and not (reason or "").strip():
        raise ValueError("반려에는 이유 한 줄이 필요하다")
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(KST).isoformat(timespec="seconds"), "verdict": verdict,
           "reason": (reason or "").strip() or None, "draft": take}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return reasons(path)[row["reason"]] if row["reason"] else 0


def reasons(path: Path) -> Counter:
    if not path.exists():
        return Counter()
    rows = (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())
    return Counter(r["reason"] for r in rows if r.get("verdict") == "rejected" and r.get("reason"))


def _pick(cands: list[str]) -> int:
    for i, c in enumerate(cands, 1):
        print(f"  {i}. {c}")
    while True:
        a = input("내 한 줄 번호> ").strip()
        if a.isdigit() and 1 <= int(a) <= len(cands):
            return int(a) - 1


def interview(url: str) -> int:
    import write_post as wp   # 무겁다(다이제스트 수집기까지 딸려 온다) — 인터뷰 때만
    _, src = wp.load_source(url)
    if not src:
        print(f"소재를 못 읽었다: {url}", file=sys.stderr)
        return 1
    qa: list[tuple[str, str]] = []
    for n in range(1, MAX_Q + 1):
        q = llm.ask(question_prompt(url, src, qa))
        if not q:
            print("질문을 못 만들었다(LLM 무응답)", file=sys.stderr)
            return 1
        q = q.strip().splitlines()[0]
        print(f"\nQ{n}. {q}  (빈 줄 = 그만)")
        a = input("> ").strip()
        if not a:
            break
        qa.append((q, a))
    try:
        take = make(url, src, qa, _pick)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    if take is None:
        print("답이 없어 원고를 만들지 않는다(D38 — 내 한 줄이 없으면 카드를 만들지 않는다)")
        return 1
    TAKES_DIR.mkdir(parents=True, exist_ok=True)
    out = TAKES_DIR / f"{take['at'][:10]}-{wp.slugify(take['line'])[:40]}.json"
    out.write_text(json.dumps(take, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n원고: {out.relative_to(ROOT)}")
    return _report(check(take, src))


def _report(fails: list[str]) -> int:
    for f in fails:
        print(f"  탈락: {f}")
    print("검사 통과" if not fails else f"검사 탈락 {len(fails)}건")
    return 1 if fails else 0


def judge(path: Path, verdict: str) -> int:
    take = json.loads(path.read_text(encoding="utf-8"))
    reason = None
    if verdict == "rejected":
        past = list(reasons(LOG))
        for i, r in enumerate(past, 1):
            print(f"  {i}. {r}")
        a = input("같은 이유면 번호, 아니면 이유 한 줄> ").strip()
        reason = past[int(a) - 1] if a.isdigit() and 1 <= int(a) <= len(past) else a
    n = record(LOG, take, verdict, reason)
    print(f"기록: {LOG.relative_to(ROOT)} ({verdict})")
    if n >= 2:
        print(f"같은 이유 {n}번 — scripts/my_take.py 의 RULES 로 옮겨라: {reason}")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--selftest"]:
        return selftest()
    if len(argv) == 2 and argv[0] in ("--check", "--approve", "--reject"):
        p = Path(argv[1])
        if argv[0] == "--check":
            import write_post as wp
            take = json.loads(p.read_text(encoding="utf-8"))
            return _report(check(take, wp.load_source(take["url"])[1]))
        return judge(p, "approved" if argv[0] == "--approve" else "rejected")
    if len(argv) == 1 and argv[0].startswith("http"):
        return interview(argv[0])
    print(__doc__)
    return 2


def selftest() -> int:
    import tempfile

    src = "Acme 는 응답 지연을 120ms 에서 45ms 로 줄였다고 밝혔다. 캐시 계층을 하나 더 뒀다."
    calls = []

    # 체크 1 — 인터뷰 답이 비면 원고가 안 생기고, LLM 도 안 부른다
    def ask(p):
        calls.append(p)
        return None
    assert make("https://x.test/a", src, [("왜?", ""), ("그래서?", "  ")], lambda c: 0, ask) is None
    assert calls == [], "답이 비었는데 LLM 을 불렀다"
    assert check({"answers": ["", " "]}, src)[0].startswith("인터뷰 답이 비었다")

    # 체크 2 — 원고 수치마다 출처가 있거나 "확인 필요"
    take = {"url": "https://x.test/a", "answers": ["캐시보다 측정이 먼저다."],
            "line": "캐시보다 측정이 먼저다.", "mine": ["캐시보다 측정이 먼저다."],
            "original": ["지연을 45ms 로 줄였다", "비용은 30% 늘었다"], "quotes": []}
    assert any("30" in f for f in check(take, src)), check(take, src)
    fixed = mark(take, src)
    assert check(fixed, src) == [], check(fixed, src)
    assert fixed["original"][0] == "지연을 45ms 로 줄였다"   # 출처에 있는 수치는 그대로
    assert mark(fixed, src) == fixed                       # 두 번 붙이지 않는다

    # 체크 3 — 반려하면 이유 한 줄이 기록 파일에 남는다
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "takes.jsonl"
        assert record(p, fixed, "rejected", "원본 요약에 그쳤다") == 1
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["verdict"] == "rejected" and rows[-1]["reason"] == "원본 요약에 그쳤다"
        assert rows[-1]["draft"]["line"] == fixed["line"]   # 반려본이 같이 남는다
        assert record(p, fixed, "rejected", "원본 요약에 그쳤다") == 2   # 2번째 → 규칙으로 옮길 신호
        record(p, fixed, "approved")
        assert reasons(p) == Counter({"원본 요약에 그쳤다": 2})
        try:
            record(p, fixed, "rejected", "  ")
            raise AssertionError("이유 없는 반려가 기록됐다")
        except ValueError:
            pass

    # 내 말이 아닌 한 줄 · 원본 베끼기 · URL 없는 인용은 탈락
    bad = {**fixed, "line": "캐시는 언제나 옳다.", "quotes": [{"text": "x", "url": ""}],
           "original": ["Acme 는 응답 지연을 120ms 에서 45ms 로 줄였다고 밝혔다"]}
    joined = " ".join(check(bad, src))
    for key in ("내 한 줄이 내 답에 없다", "그대로 옮겼다", "URL 이 없다"):
        assert key in joined, (key, joined)

    # 정상 경로 — 한 줄은 내 답 문장 중 내가 고른 것, 지어낸 수치엔 표시가 붙는다
    qa = [("왜 캐시를?", "측정 없이 캐시부터 넣은 적이 있다. 결국 뺐다."), ("그래서?", "캐시보다 측정이 먼저다.")]
    fake = '{"candidates": [2, 0, 9], "original": ["캐시 계층을 더해 지연을 45ms 까지 낮췄다", "효과는 3배다"], "quotes": []}'
    t = make("https://x.test/a", src, qa, lambda c: 0, lambda p: "결과:\n" + fake)
    assert t["line"] == "캐시보다 측정이 먼저다.", t["line"]          # 범위 밖 번호 9 는 버린다
    assert t["mine"] == sentences([a for _, a in qa])
    assert t["original"][1].endswith(f"({CHECK})") and CHECK not in t["original"][0], t["original"]
    assert check(t, src) == [], check(t, src)
    try:
        make("https://x.test/a", src, qa, lambda c: 0, lambda p: None)
        raise AssertionError("LLM 무응답을 원고로 만들었다")
    except RuntimeError:
        pass

    print("my_take selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
