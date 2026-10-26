# 설치한 에이전트 스킬 목록

작성일: 2026-10-27 · 설치 위치: 작업한 PC의 사용자 폴더 (`~/.claude/skills`, 저장소 밖)

스킬 본문은 저장소에 넣지 않는다. 다른 PC에서는 아래 명령으로 같은 출처에서 다시 설치한다.

## 설치 목록

| 스킬 | 출처 | 용도 (이 프로젝트 기준) | 보안 검사 (skills.sh) |
| --- | --- | --- | --- |
| find-skills | vercel-labs/skills (SKILL.md를 직접 내려받아 배치) | 스킬 검색·설치 안내 | 확인하지 못함 |
| frontend-design | anthropics/skills | 화면 전반의 디자인 완성도 | 확인하지 못함 |
| design-taste-frontend | leonxlnx/taste-skill | 미적 감각, 기존 페이지 개선 | 확인하지 못함 |
| kpi-dashboard-design | wshobson/agents | 지표 선정과 대시보드 구조 | 확인하지 못함 |
| interface-design | dammyjay93/interface-design | 데이터 중심 화면 설계 (랜딩 페이지 제외) | 전부 통과 |
| data-visualization | anthropics/knowledge-work-plugins | 차트 선택과 접근성 | 전부 통과 |
| graphify | graphify-labs/graphify | 브랜드·기업·채널 관계 그래프 점검 | Socket 경고 |
| data-storytelling | wshobson/agents | 보고서와 사업주 자료의 이야기 구조 | 전부 통과 |

보안 검사 결과는 skills.sh 페이지 표시값을 옮긴 것이다. 직접 검증하지는 않았다.

## 다른 PC에서 설치

```bash
npx skills add vercel-labs/skills@find-skills -g -y
npx skills add anthropics/skills@frontend-design -g -y
npx skills add leonxlnx/taste-skill@design-taste-frontend -g -y
npx skills add wshobson/agents@kpi-dashboard-design -g -y
npx skills add dammyjay93/interface-design@interface-design -g -y
npx skills add anthropics/knowledge-work-plugins@data-visualization -g -y
npx skills add graphify-labs/graphify@graphify -g -y
npx skills add wshobson/agents@data-storytelling -g -y
```

`npx`를 쓰려면 Node.js가 필요하다. Windows에서 `-g` 설치 시 "PromptScript does not support global skill installation" 오류가 나도 Claude Code 쪽 설치는 되어 있을 수 있다. `npx skills list -g`로 확인한다.

## 내용을 읽고 판단한 후보

별 수보다 본문을 기준으로 판단했다. 별이 적어도 내용이 쓸 만하면 참고용으로 채택할 수 있다.

| 스킬 | 별 수 | 본문에서 본 것 | 판단 |
| --- | --- | --- | --- |
| promotional-planning (kishorkukreja) | 84 | 프로모션 기준선 대비 증분 매출, ROI, 행사 달력, 자기잠식, 행사 후 매출 하락 | 참고 가치 높음. 식품·소비재 중심이라 패션에 맞게 바꿔 써야 함 |
| knowledge-graph-construction (lyndonkl) | 186 | 엔터티-관계, 사건 표현, 계층 구조 등 스키마 패턴 | 브랜드·기업·채널 DB 구조를 점검할 때 참고 가치 있음 |
| master-data-management (erphq) | 4 | 기준정보(마스터 데이터) 개념, 중복 해소, 체크리스트 | 중복 판정 기준에 참고 가능. 기업 규모 전제 |
| demand-forecasting (finsilabs) | 60 | 재주문점·안전재고·계절성 등 재고 개념 | 개념은 쓸 만하나 Shopify·Amazon 도구 전제 |
| pricing-strategy (phuryn) | 2.7만 | 가격 전략, 지불 의향 | SaaS 중심. 가격 설정 때 부분 참고 |
| kosis-stats, bok-ecos-stats (nomadamas) | 공식 API 조회 | 실제 지침은 실행 시 외부 npm 패키지에서 받는 구조 | 패키지 내용을 확인한 뒤 결정 |
| company-identity-reconciliation (crawlora) | 14 | 기업·브랜드 동일성 판정 절차 | 유료 API와 외부 플랫폼 조회 전제. 보류 |

### 본문 검토 메모

- **promotional-planning**: 1) 기준선 판단과 증분 매출 계산(기준선 = 행사 없는 주의 평균 또는 시계열 분해), 2) 가격 탄력성 모델 예시(파이썬), 3) 행사별 ROI, 4) 행사 달력 최적화, 5) 행사 물량 계획, 6) 자기잠식과 행사 후 매출 하락(pantry loading) 같은 함정. 식품 용어가 많아서 패션의 시즌 오프, 쿠폰, 무료배송 행사로 바꿔 읽어야 한다.
- **knowledge-graph-construction**: 용도별 아키텍처 선택(LPG·RDF 등), 엔터티-관계 패턴, 사건 표현 패턴, 계층 패턴. 브랜드·기업·채널 스키마를 점검할 때 "엔터티와 관계를 어떻게 나눌지" 참고용으로 쓴다. 그래프 DB를 바로 도입하라는 내용은 아니다.
- **master-data-management**: 기준정보 개념, 중복 판정, 골든 레코드, 안티패턴과 체크리스트. 기업 규모 전제가 있어 중복 판정 기준 정도만 가져온다.
- **demand-forecasting**: 재주문점, 안전재고, 계절성 단계. 도구 설명이 Shopify·Amazon 중심이라 개념만 참고한다.
- **pricing-strategy**: 가격 모델, 경쟁 가격 분석, 지불 의향, 가격 탄력성. SaaS 예시가 많다.
- **kosis-stats** (원본 `NomaDamas/k-skill/kosis-stats/instruction.md`, 약 1.6만 바이트 확인): 국가통계포털 KOSIS 표 검색, 메타 확인, 소량 조회 후 출처 인용까지의 절차가 정리되어 있다. 기본 조회는 **호스팅 프록시(`k-skill-proxy.nomadamas.org`)를 거치므로 검색어가 제3자 서버를 지난다**. 공개 통계 검색어라 위험은 낮지만 기록해 둔다. 인증키(`KSKILL_KOSIS_API_KEY`)는 `bigdata`·`--direct` 모드에서만 쓰며 무료 발급이다. 실행은 `npx @nomadamas/k-skill@0 exec` 명령으로 외부 패키지 스크립트를 돌리는 방식이다.
- **bok-ecos-stats** (원본 instruction.md, 약 4천 바이트 확인): 기준금리, 환율, 소비자물가 같은 한국은행 ECOS 시계열을 조회한다. 키 없이 공개 데모 키 `sample`로 동작하지만 호출당 10행 제한이 있다. 실사용은 무료 발급 키를 권장한다. 실행 방식은 kosis와 같다.
- **market-sizing-analysis** (wshobson, 별 1.2만, 본문 확인): TAM·SAM·SOM 3단계 틀, 하향식·상향식·가치 기반 계산 방법, 적용 사례가 들어 있다. 시장 개요 페이지에 "전체 시장 규모" 같은 숫자를 넣을 때 참고할 만하다. 다만 원 단위 추정은 근거 자료가 필요하고, 이 DB는 표본이라 상향식 계산의 전제가 약하다는 점을 감안한다.
- **pricewin-price-comparison**: 호텔 OTA 요금 비교용이고 외부 MCP 서버가 필요하다. 업무와 무관.

## 설치하지 않은 것

| 스킬 | 판단 이유 |
| --- | --- |
| camofox-browser, camofox-cli | 봇 탐지 회피 도구라 접근 제한 우회 금지 원칙과 충돌 |
| claude-ads | 광고 계정 운영용. `ads-competitor`는 나중에 검토 가능 |
| market-sizing-analysis | 신규 사업 투자용. 금액 추정이 필요해지면 다시 본다 |
| pricewin-price-comparison | 호텔 요금 비교용이라 업무와 무관 |
| competitive-intelligence (Anthropic) | CRM 커넥터 전제 |
| brightdata price-comparison | 보안 검사 실패 |
| 트렌딩 상위의 영상·트위터 자동화 계열 | 업무와 무관 |
| 네이버·쿠팡 대량 수집, 우회 기능 스킬 | 프로젝트 원칙과 충돌 |
