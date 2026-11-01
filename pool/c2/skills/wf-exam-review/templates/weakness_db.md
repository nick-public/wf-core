# 약점 DB — 레코드와 불변 규칙

파일 하나(`entries.json`, 배열 `entries` + `counts`)를 git으로 추적한다. 몇 백 건까지 서버 없이 충분하다. 경로는 그 주제 repo 루트 기준 상대 경로로 적는다(학기 폴더가 옮겨져도 한 번에 고친다).

```jsonc
{
  "id": "<시험일>_<과목>_Q<번호>",       // 고유. 재사용하지 않는다
  "exam": { "id": "<학기 코드>", "date": "YYYY-MM-DD", "subject": "<과목>", "scope": "<범위>" },
  "q": "Q12",
  "source_type": "exam",                 // exam | bank(문제은행) — 같은 사다리, 통계에서만 분리
  "format": "선다",                       // 선다 | 합답형 | 서술형 | 논술형
  "result": "wrong",                     // wrong | partial(부분점수) | guess_correct(찍어서 맞음)
  "points": 0,                           // 배점 — 우선순위 보정에 쓴다
  "gaps": ["my_answer", "confidence"],   // 비어 있는 정보를 숨기지 않고 적는다
  "topic": ["<과목>:<단원>"],             // 내용 축 — 통제 어휘(topics.json)에서만
  "cause": { "primary": "C4", "secondary": ["C5"], "detail": "<판단 근거 한 줄>" },
  "confidence": "sure",                  // sure | half | guess | timeout | unknown — 학생이 답한다
  "confused_with": null,                 // C3이면 필수: 무엇과 헷갈렸나
  "links": { "source": "<원문>", "note": "<오답 노트>", "app": "<풀이 앱>" },
  "extra": {},                           // 과목별 추가 칸(근거 문장, 모르는 어휘 등)
  "retest": { "state": "scheduled", "rung": 0, "streak": 0, "due": "YYYY-MM-DD", "history": [] },
  "created": "YYYY-MM-DD", "updated": "YYYY-MM-DD"
}
```

## 불변 규칙
1. 같은 문항을 다시 틀리면 새 레코드가 아니라 기존 레코드의 `retest.history`에 쌓는다. history는 덮어쓰지 않는다 — 몇 번 만에 넘었는지가 정보다.
2. 지우지 않는다. 넘은 것은 `mastered`로 남긴다.
3. 찍어서 맞은 것도 넣는다. 정답률은 실력을 과대평가한다.
4. `cause`가 없으면 미완성 레코드다.
5. 정렬은 `exam.date` → `subject` → `q`(diff 안정). 스키마를 바꾸면 같은 commit에 이관 메모.

## 내용 태그는 통제 어휘로
자유 생성한 태그는 집계를 무너뜨린다(같은 것이 다른 이름으로 흩어진다). 과목마다 canonical 목록 + alias 표를 두고 새 태그를 임의로 만들지 않는다. "조건해석 · 계산실수 · 경우분류" 같은 말은 단원이 아니라 원인이다 — 내용 축에 넣지 말고 `not_topics` 표로 원인 코드에 옮긴다.

## 이 DB로만 보이는 신호
- C1 · C3 · C7이 세 과목 이상에서 뜬다 → 과목 문제가 아니라 읽기 · 구별 습관.
- C5가 한 과목에서 3회 이상 → 실수가 아니라 습관, 체크리스트로.
- `sure` 오답 → 오개념 목록.
- 같은 topic이 다른 시험에서 다시 → 보강 방법을 바꿔야 한다.
- `mastered`인데 다시 wrong → 간격이 길었거나 처치가 표면적이었다.
