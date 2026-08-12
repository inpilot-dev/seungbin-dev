// 콘텐츠 도메인 타입 단일 출처 (규칙 #5: 여기 정의된 것만 사용, 새로 만들지 말 것)

export interface Post {
  slug: string;
  title: string;
  description: string;
  /** ISO 날짜 문자열 "YYYY-MM-DD" */
  date: string;
  tags: string[];
  /** Build | Automate | Grow 슈퍼카테고리 */
  category?: string;
  /** 예: "5 min read" — lib/content 에서 본문 길이로 계산 */
  readingTime: string;
  /** 터미널 커버에 찍을 명령 한 줄 (글에서 실제로 나오는 것) */
  coverCmd?: string;
  /** 그 명령의 출력 한 줄. 없으면 명령만 */
  coverOut?: string;
}

export interface Author {
  name: string;
  avatar?: string;
  url?: string;
  bio?: string;
}

export interface Tag {
  name: string;
  count: number;
}

export interface TOCItem {
  id: string;
  text: string;
  /** 헤딩 레벨 (2 = h2, 3 = h3) */
  level: number;
}
