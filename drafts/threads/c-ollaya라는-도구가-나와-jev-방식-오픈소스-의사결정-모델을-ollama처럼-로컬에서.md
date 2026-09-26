"README 오타 고쳐줘"라는 요청에 에이전트가 `git push --force origin main`을 내밀었다. 로컬 모델은 178ms 만에 판정을 냈다. destructive yes 0.90, action block 0.53.

Ollaya가 하는 일이다. Jev 방식 오픈소스 의사결정 모델을 Ollama처럼 `ollaya run laya` 한 줄로 내 하드웨어에서 돌린다.

의사결정 모델은 토큰을 하나씩 생성하지 않는다. **한 번의 forward pass**로 답한다. RTX 4090에서 Laya에 질문 5개를 HTTP API로 보내면 8–10ms가 걸린다. TypeSafe Jev 호스티드 API의 중앙값은 236–276ms다. 다만 이쪽은 네트워크를 포함한 수치이고 환경도 다르다. 자릿수 비교로만 읽어야 한다.
---
TypeSafe API와 호환된다. /v1/systemone 요청을 같은 형태로 받고, 공식 Python SDK 0.7.1이 수정 없이 붙는다. base URL만 바꾸면 된다.

서버는 기본값으로 127.0.0.1에서 뜬다. 가중치는 원저자의 Hugging Face 저장소에서 받는데, 커밋을 고정하고 sha256으로 검증한다. 토큰당 과금은 없다. 확률은 모델마다 캘리브레이션돼 있고, Modelfile로 갖고 있는 라벨 데이터에 다시 맞출 수 있다.

티켓이나 이메일처럼 민감한 텍스트를 외부 API로 보내 분류하고 있다면 로컬로 옮길 이유는 충분하다. 핵심은 속도보다 **임계값을 걸 수 있는 확률**이다.

https://ollaya.dev/
