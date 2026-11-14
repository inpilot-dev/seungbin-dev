AI 탐지기가 내는 0~100 점수는 그 글을 AI가 썼을 확률이 아니다. 학습 분포 안에서 분류기가 추정한 **AI 클래스 확률**일 뿐이다.

Sebastian Raschka가 Substack의 AI 탐지 기능 출시를 계기로 탐지기를 처음부터 만드는 과정을 공개했다. DistilBERT 분류기를 파인튜닝하고, 글 전체 점수와 청크별 점수를 로컬 UI에 띄운다.

재밌는 건 그다음이다. 이 탐지기를 verifier로 두고 작은 언어 모델이 탐지를 피하는 글을 쓰도록 RLVR로 학습시킨다. 보상이 정답이 아니라 탐지 점수다.

저자는 한계도 먼저 적는다. 탐지는 고양이와 쥐 게임이고, 사람이 쓴 글을 AI로 잡는 오탐도 생긴다. 그래서 탐지 점수는 판정이 아니라 신호로 읽어야 한다.

https://magazine.sebastianraschka.com/p/ai-detector-from-scratch
