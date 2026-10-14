Anthropic의 Scion 소개 글에 Mononoke라는 이름은 한 번도 나오지 않는다.

Mononoke는 Meta 팀이 2017-18년에 구상한 소스 컨트롤 서버다. 그 팀에 있던 sunshowers가 Anthropic의 Scion 설명과 자신이 2022년에 쓴 문서를 나란히 놓았다. 겹치는 건 blame 같은 연산을 효율화하는 "derived data" 개념만이 아니다. 그걸 설명하는 방식까지 같다.

Sapling은 "hard-won lessons" 한 줄로만 언급됐다. 글쓴이는 이걸 표절에 가깝다고 본다. Claude가 전부 설계한 것처럼 읽히기 때문이다.
---
다만 글쓴이가 문제 삼는 건 복제가 아니라 출처 누락이다. 좋은 아이디어를 퍼뜨리려고 오픈소스로 공개했으니 설계를 가져다 쓰는 건 괜찮다고 직접 적었다.

Mononoke는 오픈소스라서 모든 LLM의 학습 데이터에 들어 있다. 글쓴이에 따르면 Opus 5.5와 GPT-6 Astra에 선행 사례를 물으면 둘 다 곧바로 Mononoke와 닮은 점을 짚는다.

LLM이 설계를 거들수록 기존 설계를 더 많이 참조한다. 선행 사례 확인은 이제 모델에게 한 번 물어보면 끝난다. 출처를 빼먹을 핑계가 없어졌다.

https://sunshowers.io/posts/anthropic-mononoke/
