# 국내 의류 브랜드·쇼핑몰 DB와 경쟁사 모니터링

MD 업무(이벤트·프로모션 기획, 가격·할인율 결정, 재고 처리)의 비교 기준과 근거를 만드는 프로젝트입니다.

```text
① 국내 의류 브랜드·쇼핑몰 DB 구축   ← 지금 단계
② 관심 리스트 선정 (DB에서 조건에 맞는 곳 선택)
③ AI 에이전트가 관심 리스트만 매일 확인 (프로모션, 할인, 신상품, 가격, 품절)
④ 업무에 활용 (벤치마킹, 근거 자료)
```

방향과 결정의 원본은 [기획서](planning/korea-fashion-monitoring-plan.md)입니다. 지금 숫자, 최근 작업, 남은 일은 [STATUS.md](STATUS.md)에 있습니다.

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `planning/` | 기획서. 목적, 단계, DB 방침, 결정 기록(§10), 다음 단계 |
| `research/fashion-commerce-map/` | ① DB. 쇼핑몰·기업·브랜드·관계 CSV(`data/curated/`)와 수집 기준(`docs/`) |
| `research/fashion-industry-map/` | 대한민국 패션산업 지도 조사 문서와 정적 화면 |
| `samples/` | ③·④ 화면 샘플 (블루팝스 BEST·전체 상품 가격 비교) |
| `archive/` | 초기 자료. URL 입력식 경쟁사 프로토타입, 옛 작업지침·메모. 참고용 |

## AI로 작업할 때

AI(Claude, Codex, Cursor 등)는 [`AGENTS.md`](AGENTS.md)를 먼저 읽고 작업합니다.
