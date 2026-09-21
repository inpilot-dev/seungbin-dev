import { NextRequest, NextResponse } from "next/server";

// 입력 검증(400)과 다운스트림 실패(502/503)를 분리 — 400 vs 500 구분 유지.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(req: NextRequest) {
  const { email } = (await req.json().catch(() => ({}))) as { email?: string };

  // 신뢰 경계 입력 검증
  if (typeof email !== "string" || !EMAIL_RE.test(email)) {
    return NextResponse.json({ error: "올바른 이메일을 입력해주세요." }, { status: 400 });
  }

  const key = process.env.RESEND_API_KEY;
  const audience = process.env.RESEND_AUDIENCE_ID;
  if (!key || !audience) {
    return NextResponse.json(
      { error: "구독 기능이 아직 설정되지 않았어요. (docs/SETUP-features.md)" },
      { status: 503 },
    );
  }

  const headers = { Authorization: `Bearer ${key}`, "Content-Type": "application/json" };
  let alreadySubscribed = false;

  try {
    // 기존 구독자면 환영 메일 재발송 금지 — 타인 이메일 반복 제출로 인한 메일 폭탄 차단.
    //
    // 2026-09-21 실측(지도 #55): 옛 경로 `/audiences/{id}/contacts/{email}` 는 실제 구독자
    // 주소에도 **404** 를 준다(Audiences → Segments 이관, 같은 ID 로 옛 목록 1건 vs 새 목록 7건).
    // 404 면 여기서 "신규" 가 되어 아래 환영 메일이 다시 나갔다 — 위 주석이 막겠다던 바로 그 폭탄이
    // 구독자 7명 중 6명에게 열려 있었다.
    //
    // 대체 경로는 후보 셋을 실호출해 골랐다. `?segment_id=&email=` 는 email 필터를 무시하고
    // 전건(7건)을 주므로 못 쓴다. 아래 경로만 **기존 200 · 없는 주소 404** 를 둘 다 만족한다 —
    // "있으면 200" 만 보고 바꿨다면 신규 구독자가 죄다 "이미 구독중" 이 되어 구독이 통째로 막혔다.
    const dup = await fetch(
      `https://api.resend.com/contacts/${encodeURIComponent(email)}?segment_id=${audience}`,
      { headers, signal: AbortSignal.timeout(5000) },
    );
    alreadySubscribed = dup.ok;

    if (!alreadySubscribed) {
      const res = await fetch(`https://api.resend.com/audiences/${audience}/contacts`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email, unsubscribed: false }),
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) {
        return NextResponse.json({ error: "구독 처리 중 문제가 생겼어요." }, { status: 502 });
      }
    }
  } catch {
    return NextResponse.json({ error: "구독 처리 중 문제가 생겼어요." }, { status: 502 });
  }

  // CAP-2 환영 메일(리드마그넷) — best-effort: 실패해도 구독 자체는 성공 처리.
  // RESEND_FROM 미설정(도메인 미인증) 시 조용히 스킵 — 발송 배관의 스왑 경계.
  const from = process.env.RESEND_FROM;
  const willEmail = Boolean(from) && !alreadySubscribed;
  if (willEmail) {
    try {
      const sent = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers,
        body: JSON.stringify({
          from,
          to: [email],
          // 답장이 발신 주소로 오면 받을 편지함이 없다 — 실제 읽는 주소로 돌린다.
          reply_to: process.env.RESEND_REPLY_TO,
          subject: "구독 감사해요 — SQL 인덱스 치트시트 드려요",
          html: welcomeHtml(),
        }),
        signal: AbortSignal.timeout(5000),
      });
      if (!sent.ok) {
        console.error("welcome email failed:", sent.status, await sent.text().catch(() => ""));
      }
    } catch (e) {
      // 메일 실패는 구독 실패가 아님 — Audience 적재는 이미 완료. 로그로만 관측.
      console.error("welcome email error:", e);
    }
  }

  return NextResponse.json({
    message: alreadySubscribed
      ? "이미 구독 중이세요. 감사해요!"
      : willEmail
        ? "구독 완료! 자료 메일을 보내드렸어요."
        : "구독 완료! 새 글이 올라오면 소식 드릴게요.",
  });
}

// CAP-4 star-gate: STAR_GATE_URL 설정 시에만 유도 블록 노출 — env 제거로 즉시 off.
function welcomeHtml(): string {
  const leadMagnet =
    process.env.LEAD_MAGNET_URL ?? "https://inpilot.dev/posts/sql-index-cheatsheet";
  const starGate = process.env.STAR_GATE_URL;
  return [
    `<p>구독해주셔서 감사해요!</p>`,
    `<p>약속드린 자료입니다: <a href="${leadMagnet}">SQL 인덱스 치트시트</a></p>`,
    starGate
      ? `<p>도움이 되셨다면 <a href="${starGate}">GitHub에서 스타 하나</a> 눌러주시면 큰 힘이 돼요 ⭐</p>`
      : "",
    `<p>새 글이 올라올 때만 메일 드릴게요. 스팸 없음.</p>`,
  ]
    .filter(Boolean)
    .join("\n");
}
