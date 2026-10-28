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

## 검토한 후보 (미설치, 2026-10-27)

설치 여부와 관계없이 "쓸 수 있는지"를 판단한 기록이다. 목적은 상품 태그(상품명·사진에서 만드는 속성)와 사진 비교·색 추출 기능을 우리 방식으로 갖추는 것이다.

| 후보 | 출처 | 하는 일 | 판단 | 우리 방식으로 쓸 수 있나 |
| --- | --- | --- | --- | --- |
| linkfox-product-title-analyze | linkfox-ai/linkfox-skills (MIT, 112★, 2026-10-16) | 상품명을 단어로 나눠 속성(색·소재·용도) 추출, 빈도 집계 | 그대로 사용 불가 | 부분 가능. 아래 참고 |
| linkfox-multimodal-extract-attributes | 같은 저장소 | 사진에서 색·형태·재질 등 속성을 AI로 뽑아 목록으로 반환 | 그대로 사용 불가 | 부분 가능. 아래 참고 |
| linkfox-multimodal-product-similarity | 같은 저장소 | 사진들을 외관 기준으로 묶음(군집), 유사도 기준값 0~100 | 그대로 사용 불가 | 로직만 참고. 점수 계산은 우리 방식으로 새로 구현 |
| curiositech clip-aware-embeddings | curiositech/some_claude_skills (MIT, 254★, 2026-10-26) | CLIP 임베딩으로 이미지 유사도 계산 방법 안내 | 방법 참고용 | 가능. 모델 설치가 필요 |
| pascalorg image-analysis | pascalorg/skills (95 설치) | 이미지 색 추출 등 범용 분석 | 범용, 패션 전용 아님 | 가능하지만 대부분 직접 짜는 편이 단순 |
| fashn | fashn-AI/fashn-skill (Apache-2.0, 3★) | 가상 피팅 | 목적이 다름 | 사용하지 않음 |

**linkfox 3종을 그대로 쓸 수 없는 이유**
- 아마존 셀러용이고 상품 데이터 형식이 아마존 기준이다. 본문이 중국어 위주다.
- 실행하려면 외부 서비스 키(`LINKFOX_AGENT_API_KEY`)가 필요하고, 상품 제목·이미지 주소를 그 서버로 보낸다. 우리 DB 상품을 외부로 보내는 것은 `AGENTS.md`의 데이터 원칙과 맞지 않는다.
- 결과가 나쁘면 사용자 피드백을 자동으로 외부 API에 보내는 규칙이 있다(`references/api.md`). 이것도 허용할 수 없다.

**수정해서 우리 방식으로 쓸 수 있는지 (판단)**
- **속성 추출(사진·상품명):** 외부 API 호출 부분을 빼면 로직은 쓸 수 있다. 다만 속성 목록(반팔·긴팔·셔츠 등)과 동의어는 우리가 정해야 한다. 가장 단순한 방법은 Claude가 저장된 사진을 직접 보고, 정해 둔 속성 목록 안에서만 값을 적는 것이다. 이 방식은 외부 서비스 없이 가능하고, 대신 사진 수만큼 토큰이 든다.
- **사진 비교 점수:** 우리가 로컬에서 임베딩 모델(CLIP 계열)을 돌려 두 사진의 벡터 유사도를 계산하고 점수로 기록하는 방식이 맞다. linkfox의 묶음 로직은 참고만 한다.
- **이미지 색 추출:** 외부 도구 없이 사진의 주요 색을 계산하는 짧은 스크립트로 충분하다. 범용 스킬은 참고용이다.

**결론:** 아마존용 linkfox 3종은 **설치하지 않는다. 참고 대상으로만 두고, 우리 방식으로 새로 작성한다.** 쓸 만한 것은 로직과 구조(속성 추출 방식, 제목 토큰화 흐름, 묶음 기준값 개념)이고, 외부 서비스·API·아마존 데이터 형식은 버린다.

### 우리 방식으로 바꾸는 순서

1. **속성 목록 확정 (먼저):** 종류(반팔·긴팔·셔츠·후드 등), 색, 소재, 핏, 기장, 디테일로 나눈다. 동의어 사전을 같이 만든다. 기준 문서는 `research/fashion-commerce-map/docs/03-taxonomy.md`를 확장한다.
2. **입력 교체:** 아마존의 상품 목록 대신 우리 DB의 상품 기록(브랜드, 쇼핑몰, 상품명, 이미지 주소, 가격, 상품 URL, 확인일)을 쓴다.
3. **실행 교체:** 외부 API 호출을 없앤다.
   - 사진 속성: Claude가 저장된 사진을 직접 보고, 확정된 속성 목록 안에서만 값을 적는다(외부 서비스 없음, 사진 수만큼 토큰 사용).
   - 상품명 태그: 한국어 사전과 규칙(정규식·동의어 매칭)으로 처리한다. LLM 없이도 가능하다.
   - 사진 점수: CLIP 계열 임베딩을 로컬에서 계산해 코사인 유사도 0~100으로 기록한다. 기준값은 샘플로 정한다.
   - 색 추출: 주요 색을 계산하는 짧은 스크립트로 처리한다.
4. **출력 교체:** 아마존의 `attributeName`/`attributeValue` 형식 대신 우리 CSV로 쓴다: 상품 ID, 속성, 값, 근거 URL, 확인일, 방법(사람/규칙/AI/점수).
5. **버리는 것:** API 키, 외부 서버 호출, 피드백 자동 전송, 중국어 설명, 아마존 전용 필드.
6. **검증(구현 뒤):** 샘플 30개로 맞는지 사람이 확인하고, 정확도를 이 기록에 남긴다.

> 지금 단계는 1번(속성 목록)까지만 한다. 나머지는 목록이 정해진 뒤에 한다.

## 추가 후보 (미설치, 2026-10-27)

목적: 상품 태그, 사진 비교, 색 추출, 가격 비교, 한국어 처리, 데이터 정리에 간접적으로 쓰거나 아이디어를 얻을 것. 별점은 기준이 아니다. 설치 전에는 SKILL.md와 외부 서비스 요구 사항을 확인한다.

### 모델·라이브러리 (스킬보다 직접 쓰기 좋은 것)

| 이름 | 출처 | 쓸모 | 메모 |
| --- | --- | --- | --- |
| FashionCLIP | patrickjohncyh/fashion-clip (MIT, 544★, 2025-01) | 패션 사진 전용 임베딩. 사진 유사도 점수와 속성(색·종류) 판정의 기반 후보 | 패션으로 미세 조정된 CLIP. 가장 먼저 검토할 모델 |
| OpenCLIP | mlfoundations/open_clip (14,225★, 2026-10) | 범용 CLIP 구현. FashionCLIP이 안 맞을 때 대안 | 라이선스 표기가 NOASSERTION이라 확인 필요 |
| Kiwi | bab2min/Kiwi (Apache-2.0, 802★, 2026-10) | 한국어 형태소 분석. 상품명을 단어로 나눠 태그 후보를 뽑는 데 쓴다 | 상품명 태그의 한국어 처리에 가장 직접 맞음 |

### 스킬 (우리 방식으로 참고할 만한 것)

> 2026-10-27 결정: 유료 서비스나 외부 API 키가 필요한 항목은 **사용하지 않는다**. 아래에서 "사용 안 함"으로 표시한 것은 기록만 남긴다. 나머지는 참고용으로 계속 기록하고, 나중에 한 번에 종합 정리한다.

| 이름 | 출처 | 쓸모 | 메모 |
| --- | --- | --- | --- |
| color-palette-extractor | onewave-ai/claude-skills (MIT, 384★, 2026-10) | 이미지에서 주요 색을 뽑는 방식 참고 | 색 추출을 우리 스크립트로 짤 때 참고 |
| muapi-color-analysis-board | samuraigpt/generative-media-skills (MIT, 25★) | 색 분석 결과를 보드로 보여주는 방식 참고 | **사용 안 함(생성 서비스 의존)**. 로직만 참고 |
| stytrix | stytrix-ai/stytrix-skills (MIT, 2★) | 패션 디자인 보조 (외부 MCP 필요) | 목적이 달라 참고만 |
| brightdata price-comparison | brightdata/skills (MIT, 268★, 2026-10) | 가격 비교 방식 참고 | **사용 안 함(유료 데이터 서비스 의존)** |
| competitor-price-tracker | nexscope-ai/eCommerce-Skills (MIT, 1,265★, 2026-08) | 경쟁사 가격 추적 아이디어 | **사용 안 함(아마존 중심, 유료 가능성)**. 아이디어만 참고 |

### 참고만 (직접 쓰지 않음)
- 상품 사진 촬영·생성·가상 피팅 계열(product-photography, virtual try-on, fashn 등): 우리 목적(비교·태그·가격)과 맞지 않음
- 광고 전환 추적, 채용·기업 데이터 도구: 현재 목적과 무관

### 아이디어 제안 (스킬이 없어도 할 수 있는 것)
- **태그 사전 자동 확장:** 상품명에서 자주 나오는 단어를 세어 동의어 후보를 뽑는다. 사람이 승인한 것만 사전에 넣는다.
- **근거 있는 태그만 인정:** 상품명에 있는 단어는 "상품명 근거", 사진에서 읽은 값은 "사진 근거"로 구분해 기록한다. 둘이 다르면 "확인 필요"로 둔다.
- **가격 비교 표 자동 생성:** 같은 태그 상품 묶음에서 정가·판매가·할인율을 쇼핑몰별로 정렬한 표를 만든다. 스킬 없이 CSV로 충분하다.
- **사진 중복 제거:** 같은 상품이 여러 쇼핑몰에 올라온 경우를 사진 점수 0.95 이상으로 묶는다. 기준값은 샘플로 정한다.

## 폭넓은 검색 결과 (미설치, 2026-10-27)

목적: 자료 만들기, 마케팅, 문서·발표, 데이터, 영상·이미지 등 여러 분야의 참고 스킬을 기록해 두고, 나중에 한 번에 정리한다. 유료 서비스나 외부 API 키가 필요한 것은 사용하지 않는다(2026-10-27 결정). 설치 여부와 관계없이 기록만 남긴다.

**검색 범위:** 검색어 99개(마케팅, SEO, 문서, 발표, 데이터, 영상, 법무, 인사, 개발, 국내 생산성 등)로 찾은 고유 스킬 **1,546개**. 상세 목록은 작업 임시 폴더(`skill_unique.tsv`, `skill_cat.tsv`)에 있고 저장소에는 넣지 않았다. 필요하면 나중에 정리해 올린다.

**주의:** 키워드로 자동 분류해서 분야가 조금씩 어긋난다. 개발용 스킬이 많이 섞여 있다. 설치 수가 많다고 우리 목적에 맞는 것은 아니다. 아래는 설치 수 기준 대표 예시이고, 실제로 쓸 것은 SKILL.md를 읽고 고른다.

### 마케팅·판매·콘텐츠 (쓸 만한 후보)
- coreyhaines31/marketingskills: seo-audit(SEO 점검), copywriting(문구), content-strategy(콘텐츠 전략), ai-seo(AI 검색 노출), marketing-psychology(고객 심리), cro(전환율 개선), signup(가입 흐름), events(행사 기획)
- 101-skills 등 여러 모음: landing-page-design(랜딩 페이지), youtube-thumbnail-design(썸네일), product-photography(상품 사진, 촬영 조건이 맞을 때만)

### 문서·발표·자료 만들기
- anthropics/skills: docx(워드), xlsx(엑셀), pdf, pptx(발표 자료) — 우리 보고서·엑셀 작업의 기본. 설치 수가 많고 출처가 공식에 가깝다.
- anthropics/knowledge-work-plugins: documentation(문서 작성)
- 4ier/notion-cli: Notion 연동 (외부 계정 필요)

### 데이터·기획·분석
- mattpocock/skills: research(조사), to-questionnaire(설문지), to-prd(요구 정리) — 조사와 기획 흐름에 맞음
- 데이터 분석·시각화 스킬은 검색 결과에 많지만 대부분 특정 DB나 클라우드 전용이라 우선순위가 낮다

### 한국어·국내
- uplika/uplika-plugin: naver-ai-cite(네이버 AI 인용 관련, 설치 13) — 설치 수는 적지만 국내 검색 노출 쪽 참고
- 한국어 형태소 분석: Kiwi(모델 항목에 기록) — 스킬보다 라이브러리 쪽이 실용적

### 참고만 (직접 쓰지 않음)
- Lark(Feishu), Azure, HeyGen, 유료 이미지·영상 생성, 트위터 자동화: 외부 계정이나 유료 서비스 의존
- 쿠폰·특정 쇼핑몰 전용(예: 맥도날드 쿠폰, Etsy 광고): 우리 목적과 맞지 않음
- 개발·배포 전용(React, Cloudflare, Convex 등): 이 프로젝트 범위 밖

### 다음에 할 일
- 위 후보를 SKILL.md 기준으로 하나씩 읽고, 무료 여부와 외부 요구 사항을 표시한다.
- 전체 1,546개는 나중에 분야별로 다시 나눠 종합 정리한다.

## 보류 후보 상세 (미설치, 2026-10-27)

결정: 지금은 설치하지 않는다. 기획 단계가 커지면 그때 설치한다. 아래는 나중에 바로 판단할 수 있도록 내용과 출처만 기록한다. 모두 무료(MIT) 오픈소스이고 외부 계정이나 유료 API가 필요하다는 표시는 없다(설치 전 SKILL.md에서 다시 확인).

| 스킬 | 출처 (라이선스, 별점, 최근 갱신) | 하는 일 | 우리에게 쓸 자리 |
| --- | --- | --- | --- |
| seo-audit | coreyhaines31/marketingskills (MIT, 56,700★, 2026-10-26) | 웹 페이지의 검색 노출 상태 점검 | 쇼핑몰·랜딩 페이지 점검, 경쟁사 검색 노출 비교 |
| copywriting | 같은 저장소 | 상품·광고 문구 작성 | 상품 설명, 프로모션 문구 초안 |
| content-strategy | 같은 저장소 | 콘텐츠 계획과 주제 정리 | 브랜드별 콘텐츠 방향 정리 |
| customer-research | 같은 저장소 | 고객 조사 설계 | 소비자 조사 계획 |
| ai-seo | 같은 저장소 | AI 검색에 노출되는 방법 | 브랜드 정보가 AI 답변에 나오는지 점검 |
| marketing-psychology | 같은 저장소 | 소비자 심리 원리 정리 | 프로모션 기획의 근거 |
| cro | 같은 저장소 | 구매·가입 전환율 개선 | 쇼핑몰 구매 흐름 점검 |
| signup | 같은 저장소 | 가입 흐름 점검 | 회원 가입 단계 분석 |
| events | 같은 저장소 | 행사·이벤트 기획 | 프로모션·이벤트 기획안 |
| research | mattpocock/skills (MIT, 304,086★, 2026-10-22) | 주제 조사와 자료 정리 (경로: engineering/research) | 시장·경쟁사 조사 정리 |
| to-questionnaire | 같은 저장소 (경로: productivity/to-questionnaire) | 설문 문항 작성 | 고객·사용자 설문 설계 |

**나중에 설치할 때 명령 (지금은 실행하지 않음):**
- `npx skills add coreyhaines31/marketingskills --skill seo-audit --agent claude-code -g -y` (다른 묶음 스킬도 같은 형식)
- `npx skills add mattpocock/skills --skill research --agent claude-code -g -y`
- `npx skills add mattpocock/skills --skill to-questionnaire --agent claude-code -g -y`

**설치를 나중에 하는 이유:** 전역 설치는 모든 세션에 스킬 설명이 올라와서 목록이 길어지고 판단이 흐려질 수 있다. 필요할 때 설치하면 된다.
## 설치 예정 조합 (미설치, 2026-10-28)

결정: 지금 쓸 만한 조합으로 기록만 한다. 설치 시점은 사용자가 정하고, 설치 전에 각 스킬의 SKILL.md를 직접 확인한다.

| 순서 | 스킬 | 역할 | 확인할 것 |
| --- | --- | --- | --- |
| 1 | agent-browser (vercel-labs/agent-browser, 1.2M 설치) | 수집 (이미 쓰는 도구) | 설치 확인만 하면 됨 |
| 2 | competitor-profiling (coreyhaines31/marketingskills, 95.9K 설치, 저장소 56.9K★) | 경쟁사 프로필 작성 | 우리 DB 항목(브랜드·채널·근거)과 맞는 출력 형식인지 |
| 3 | firecrawl-competitive-intel (firecrawl/firecrawl-workflows, 31.4K 설치, 209★) | 경쟁사 변화 모니터링 | 무료 사용량 한도, 필요한 API 키, Snyk 경고(WARN) 내용 |

- 3번은 무료 한도를 확인한 뒤에만 설치한다. 외부 API 키가 필요하면 키는 사용자가 직접 넣는다.
- 설치 명령(실행 안 함): `npx skills add coreyhaines31/marketingskills --skill competitor-profiling --agent claude-code -g -y`, `npx skills add firecrawl/firecrawl-workflows --skill firecrawl-competitive-intel --agent claude-code -g -y`

**검토 후 제외한 후보**
- browser-act (108.3K): 인증 절차를 돕는 기능이 있어 차단을 우회하지 않는다는 규칙과 맞지 않음.
- 101-skills web-search (112.4K): 실행하려면 belt 클라우드 로그인이 필요함. 저장소 별 16개, 등록 2026-08-31.
- mbfinotti revops·sales·partnerships 묶음: 저장소 별 1개, 등록 2026-09. 설치 전에 코드를 직접 읽어야 함.
