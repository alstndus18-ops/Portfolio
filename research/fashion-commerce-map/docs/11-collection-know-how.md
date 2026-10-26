# 수집 노하우 (에이전트 공유)

브랜드·쇼핑몰을 모으면서 알게 된 빠른 방법과 시행착오를 모은다. Claude·Codex·Cursor 누구든 수집 전에 "지금 가장 빠른 방법"을 읽고, 수집 후 새로 알게 된 것을 "시행착오 기록"에 추가한다.

**쓰는 법**

- 시행착오 기록은 맨 아래에 추가만 한다. 형식: `날짜 · 에이전트 · 사이트 — 겪은 일 → 원인 → 다음엔`. 한 줄로.
- 같은 요령이 두 번 이상 통하면 "지금 가장 빠른 방법"이나 "사이트별 메모"를 고친다 (이 두 절은 제자리 수정).
- 수집 기준·판단 원칙은 기획서 §10·§13과 `AGENTS.md` 데이터 원칙이 우선한다. 여기는 "어떻게 빨리"만 다룬다.

## 지금 가장 빠른 방법 (무신사, 2026-10-26)

후보를 머리로 떠올리지 말고 무신사 여성 카테고리에서 대량으로 뽑은 뒤 숫자로 거른다. 2026-10-26 기준 후보 1,914개 → 591개 추가에 약 9분 (조회 자체는 2~3분, 나머지는 시행착오 해결·기록).

| 단계 | 하는 일 | 주소 (`A` = `https://api.musinsa.com/api2/dp`) |
|---|---|---|
| 0 | `agent-browser open "https://www.musinsa.com/category/100?gf=F"`, `get url`로 열린 것 확인 | — |
| 1 후보 | 세부 카테고리 45개 × 정렬 7개, 1쪽 `size=100`. 브랜드 `brand`(영문 주소)·`brandName` 모으기 | `A/v2/plp/goods?gf=F&sortCode=<정렬>&category=<코드>&page=1&size=100&caller=CATEGORY` |
| 2 중복 | `korea_entities.csv` brand의 `name_ko`·`name_en`과 공백·기호 빼고 소문자 비교 | — |
| 3 성별 | `{all, men, women}`. 남녀 공용은 양쪽에 잡힘. 여성 위주 = `men ≤ all×5%` 그리고 `all ≥ 20` | `A/v1/plp/goods/count/gender?gf=A&brand=<주소>&caller=FLAGSHIP` |
| 4 의류 비중 | 카테고리 `001`·`002`·`003`·`100` 상품 수 합 ÷ 전체. **50% 미만은 제외** (수영복·속옷·잡화 위주) | `A/v1/plp/goods/count?gf=A&brand=<주소>[&category=<코드>]&caller=FLAGSHIP` |
| 5 판매 | `isSoldOut=false` 상품 1개 이상, 첫 상품명을 근거 메모에 | `A/v2/plp/goods?gf=F&sortCode=POPULAR&brand=<주소>&page=1&size=10&caller=FLAGSHIP` |
| 6 브랜드 정보 | 페이지 HTML의 `meta: {...}, shared:` JSON → `brandName`·`brandNameEng`·`brandNation`(국가)·`since` | `/brand/<주소>/products?gf=A` |
| 7 기록 | CSV 3개에 한 줄씩. 판매 채널 무신사 `KR-SF-0001`, 국가는 `brandNation` 기준, 근거 ID는 작업자 접두어 | — |

- 정렬 7개: `POPULAR` `NEW` `REVIEW` `LOW_PRICE` `HIGH_PRICE` `DISCOUNT_RATE` `SALE_ONE_WEEK_COUNT`.
- 세부 카테고리 코드는 `A/v1/plp/filter/categories?gf=F&category=<001|002|003|100>&caller=CATEGORY`로 받는다.
- 남녀 혼합 후보(`men > 5%`, `women ≥ 40%`)는 대부분 스트리트·스포츠라 기획서 §10-12대로 여성 라인이 뚜렷한 것만 따로 고른다.

**실행 요령 (PowerShell + agent-browser)**

- 스크립트는 base64로 넘긴다. 따옴표가 안 깨진다. `--stdin`은 이 환경에서 스크립트가 전달되지 않았다.
- 명령줄 한도(약 32,000자) 때문에 base64가 3만 자를 넘지 않게 후보를 나눈다 (브랜드 주소 약 1,700개까지 한 번에 됨).
- 10초 넘게 걸리는 조회는 `eval`이 기다리지 않고 `null`을 돌려준다. 페이지 안에서 백그라운드로 돌리고 `window.__r`에 결과를 넣은 뒤, 짧은 `eval`로 끝났는지 확인해 가져온다.
- 6~8개씩 `Promise.all`로 묶는다. 1,758개 성별 조회가 약 40초.

```powershell
function ABEval($js) { $b = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js)); (agent-browser eval -b $b 2>$null) -join "`n" }
# 백그라운드 시작: $slugs = "'kirsh','urago',..."
ABEval "window.__r=null;(async()=>{const s=[$slugs];const out={};for(let i=0;i<s.length;i+=8){await Promise.all(s.slice(i,i+8).map(async b=>{const r=await fetch('https://api.musinsa.com/api2/dp/v1/plp/goods/count/gender?gf=A&brand='+b+'&caller=FLAGSHIP',{credentials:'include'});if(r.ok)out[b]=(await r.json()).data}))}window.__r=JSON.stringify(out)})();'started'"
# 끝날 때까지 한 명령 안에서 기다린 뒤 가져오기
for ($k=0; $k -lt 40; $k++) { Start-Sleep 3; if ((ABEval "window.__r?'done':'run'") -match 'done') { break } }
$res = ((ABEval "window.__r") | ConvertFrom-Json) | ConvertFrom-Json
```

브랜드 정보 추출 (공백·줄바꿈이 섞여 있으므로 정규식에 `\s*`):

```js
const meta=async b=>{const h=await (await fetch('/brand/'+encodeURIComponent(b)+'/products?gf=A')).text();const m=/meta:\s*(\{[\s\S]*?\})\s*,\s*shared:/.exec(h);if(!m)return null;const d=JSON.parse(m[1]);return {ko:d.brandName,en:d.brandNameEng,nation:d.brandNation,nationName:d.brandNationName,since:d.since}};
```

## 사이트별 메모

| 사이트 | 메모 |
|---|---|
| 무신사 | 브라우저 밖 직접 요청(PowerShell 등)은 403. 상품 목록 2쪽부터는 인증값(`hmacId`)이 필요해 403, `size`는 100까지(200은 400) → 1쪽 100개를 정렬·세부 카테고리로 바꿔 넓힌다. 우회하지 않는다. 전체 브랜드 목록 페이지(`/brands` 등)는 없음. 브랜드 영문 주소를 추측하면 자주 틀린다(예: 유라고 `urago`). |
| 29CM | 아직 같은 방식 미확인. |
| W컨셉 | 아직 같은 방식 미확인. |

## 시행착오 기록

- 10-26 · Cursor · 무신사 — 후보 19개를 이름으로 떠올려 영문 주소를 추측 → 7개가 주소 불일치로 0건 → 카테고리 목록에서 브랜드를 뽑는 방식으로 바꿈.
- 10-26 · Cursor · 무신사 — PowerShell `Invoke-WebRequest`로 브랜드 페이지 요청 → 403 → 브라우저 탭 안에서 `fetch`로 부른다.
- 10-26 · Cursor · 무신사 — `agent-browser open` 직후 `eval`이 "Failed to fetch" → 페이지가 `about:blank`였음 → `get url`로 열린 것을 확인하고 진행.
- 10-26 · Cursor · 무신사 — 카테고리 상품 목록 `page=2` → 403(인증값 필요) → 1쪽 `size=100`, 정렬·카테고리를 바꿔 후보를 늘린다.
- 10-26 · Cursor · 무신사 — 여성 비중 필터만으로 고른 후보 중 페이지플린은 첫 상품이 목걸이 → 잡화 위주 → 카테고리별 상품 수로 의류 비중을 자동 계산해 50% 미만 제외.
- 10-26 · Cursor · 공통 — 1,758개 조회를 `eval` 한 번에 돌림 → `null` 반환(오래 걸리는 조회를 기다리지 않음) → 페이지 안 백그라운드 실행 + 짧은 확인으로 가져온다.
- 10-26 · Cursor · 공통 — `eval --stdin`에 PowerShell 파이프로 스크립트를 넘김 → 실행 안 됨 → base64(`-b`)만 쓴다.
- 10-26 · Cursor · 무신사 — 브랜드 HTML에서 `meta: {` 문자열로 찾기 → 실패(실제 HTML은 공백·줄바꿈이 다름, 확인할 때 공백을 줄여서 봐서 착각) → 정규식 `\s*`.
- 10-26 · Cursor · 공통 — PowerShell에서 `$d`(목록)와 `$D`(표)를 같이 씀 → 대소문자 구분이 없어 목록이 덮어써져 이미 넣은 줄이 모두 지워질 뻔함(커밋 전이라 되돌림) → 변수 이름을 완전히 다르게, CSV 수정 뒤 `git diff --numstat`로 추가·삭제 줄 수 확인.
- 10-26 · Cursor · 무신사 — 국가를 모두 KR로 적었음(확인 안 한 값) → 브랜드 HTML의 `brandNation`이 있어 그 값으로 기록(27개가 해외).
