Termux에서 Sentinel-IR-MCP 0.4 setup을 돌리면 설치가 끝나지 않는다. 도구가 스스로 멈춘다.

한 개발자가 PC 없이 휴대폰에서 `npx -y sentinel-ir-mcp@0.4 setup`을 실행했다. 클라이언트 선택 메뉴에서 4(VS Code)를 누르자 바로 거절이 떴다.

"Refusing to give the agent access to your whole home folder (/data/data/com.termux/files/home). Pass a project folder with --project."

실행 위치가 홈 폴더였다. 그대로 설정 파일을 썼다면 에이전트가 홈 전체를 보게 된다. 셸 히스토리도, 설정 키도. 도구는 설정 파일을 쓰기 전에 막았다.
---
이 사례에서 볼 건 휴대폰에서 돌아갔다는 사실이 아니라 **범위가 없으면 거절하는 기본값**이다. 댓글에도 같은 지적이 있었다. 대부분의 도구는 로그만 남기고 그냥 진행한다.

다만 이 동작 하나로 "제로 트러스트가 모바일에서도 견고하다"고 결론 내리는 건 과하다. 확인된 건 두 가지다. 홈 폴더를 통째로 넘기지 않는다. --project로 범위를 좁히라고 요구한다.

에이전트에 파일 접근 권한을 준다면 범위를 지정하지 않은 설정이 조용히 통과되는지부터 확인한다.

https://dev.to/jackymencz/i-tried-running-sentinel-ir-mcp-on-my-phone-via-termux-it-stopped-me-2j41
