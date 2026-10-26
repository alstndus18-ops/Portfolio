# 작업 현황·인계

다른 PC·다른 AI가 대화 기록 없이 이어받기 위한 문서다. 결정은 [기획서](planning/korea-fashion-monitoring-plan.md) §10, 지난 이력은 `git log`.

작업을 끝내거나 중단하면 "최근 작업" 맨 위에 한두 줄(한 일·의도·다음)을 쓰고, 숫자와 남은 일을 고친다. 최근 작업은 5개만 둔다.

## 숫자 (2026-10-26)

쇼핑몰 249 · 기업·브랜드·쇼핑몰 엔터티 228 · 관계 168 · 근거 87 (`research/fashion-commerce-map/data/curated/`)

## 최근 작업

- 10-26 · choiseonho · Cursor: 미확인 쇼핑몰 96곳 확인 완료 → 93곳 유지, 3곳 제외(감탄 속옷, 언밸런스 남성·점검, 룩스 도매), `status` 열 삭제(§10-8). 남녀공용 3곳(엠플레이그라운드·0062·고룩)은 메모에 표시. 88곳은 오늘 앞선 확인 결과(`womenswear_site_verification_batch_20261026.csv`) 반영. 이 PC엔 agent-browser가 없어 HTML 직접 확인 + Cursor 브라우저·BrowserOS neo 사용.
- 10-26 · choiseonho · Cursor: 이 문서 신설, 문서 간 충돌·중복 정리(결정은 기획서 §10에만), 공정위 후보 9만 건 `.gitignore`. 결정 §10-8·9 (사용자 확인). 기업·브랜드 수를 DB 기준 17곳·127개로 문서·화면 통일.
- 10-26 · choiseonho: 패션 기업 10곳 브랜드 포트폴리오를 공식 회사 페이지 근거로 추가(§10-7 여성 라인 포함 방침), 여성의류 리스트 화면 `research/fashion-industry-map/women-fashion-list.html`.
- 10-26 · choiseonho: 쇼핑몰 직접 재검증으로 252곳, 여성의류몰 아닌 10곳 제외.
- 10-26 · choiseonho: 공정위 17개 시도에서 의류 후보 9만 건 추출(커밋 안 함). 의류 칸 체크로만 거른 거라 무관한 곳·플랫폼이 섞여 있고, 확인된 252곳 중 20곳만 들어 있다.
## 남은 일

- 판매 채널 관계(`sells_through`) 10건뿐 → 확장 (§11-3).
- 공정위 후보에서 실제 여성의류 쇼핑몰을 골라 추가 (§11-1).
