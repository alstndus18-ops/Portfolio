# 수집 노하우 (에이전트 공유)

브랜드·쇼핑몰을 모으면서 알게 된 빠른 방법과 시행착오를 모은다. Claude·Codex·Cursor 누구든 수집 전에 "지금 가장 빠른 방법"을 읽고, 수집 후 새로 알게 된 것을 "시행착오 기록"에 추가한다.

**쓰는 법**

- 시행착오 기록은 맨 아래에 추가만 한다. 형식: `날짜 · 에이전트 · 사이트 — 겪은 일 → 원인 → 다음엔`. 한 줄로.
- 같은 요령이 두 번 이상 통하면 "지금 가장 빠른 방법"이나 "사이트별 메모"를 고친다 (이 두 절은 제자리 수정).
- 수집 기준·판단 원칙은 기획서 §10·§13과 `AGENTS.md` 데이터 원칙이 우선한다. 여기는 "어떻게 빨리"만 다룬다.

## 지금 가장 빠른 방법 (무신사, 2026-10-27)

포함 기준은 기획서 §10-13: **무신사 여성 의류 카테고리에 브랜드가 올라와 있으면 포함.** 비율 계산은 하지 않는다. 카테고리 필터의 "브랜드" 목록이 그 카테고리의 브랜드 전체를 쪽 단위로 주므로, 후보 찾기와 판단이 한 번에 끝난다. 2026-10-27 기준 4,337개 → DB에 없는 3,646개 추가에 조회 약 2분 30초.

| 단계 | 하는 일 | 주소 (`A` = `https://api.musinsa.com/api2/dp`) |
|---|---|---|
| 0 | `agent-browser open "https://www.musinsa.com/category/100?gf=F"`, `get url`로 열린 것 확인 | — |
| 1 목록 | 카테고리 `001` 상의·`002` 아우터·`003` 바지·`100` 원피스/스커트 각각 `page=1..totalPages`, `size=100`(1000은 빈 결과). `brand`·`brandName`·`brandNameEnglish` | `A/v1/plp/filter/brands?gf=F&category=<코드>&caller=CATEGORY&page=<n>&size=100` |
| 2 중복 | DB brand의 `name_ko`·`name_en`(공백·기호 빼고 소문자)과 evidence URL의 무신사 브랜드 주소로 비교 | — |
| 3 분류 | 남성 상품 0개면 `womenswear`, 있으면 `womenswear_mixed`. `all=0`(보이는 상품 없음)은 운영 확인이 안 돼 뺀다 | `A/v1/plp/goods/count/gender?gf=A&brand=<주소>&caller=FLAGSHIP` |
| 4 브랜드 정보 | HTML `meta: {...}, shared:` → `brandNation`(국가)·`since`. 국가가 없으면 비움 | `/brand/<주소>/products?gf=A` |
| 5 기록 | CSV 3개에 한 줄씩. 판매 채널 무신사 `KR-SF-0001`, 근거 URL은 브랜드숍, 근거 ID는 작업자 접두어 | — |

- 3·4단계는 브랜드당 2번 요청. 8개씩 묶어 3,662개에 약 1분 50초.
- 이 방법으로 무신사 여성 의류 브랜드는 사실상 다 모았다(2026-10-27 기준). 다음 확장은 다른 플랫폼(29CM·W컨셉 등)에서 같은 구조의 브랜드 필터를 찾는 것.
- 예전 방법(상품 목록 1쪽을 세부 카테고리 45개 × 정렬 7개로 훑기, 2026-10-26)은 후보가 1,914개에 그쳤다. 브랜드 필터가 막히면 대안으로 쓴다: `A/v2/plp/goods?gf=F&sortCode=<POPULAR|NEW|REVIEW|LOW_PRICE|HIGH_PRICE|DISCOUNT_RATE|SALE_ONE_WEEK_COUNT>&category=<세부 코드>&page=1&size=100&caller=CATEGORY`. 세부 코드는 `A/v1/plp/filter/categories?gf=F&category=<001|002|003|100>&caller=CATEGORY`.

**실행 요령 (PowerShell + agent-browser)**

- 스크립트는 base64로 넘긴다. 따옴표가 안 깨진다. `--stdin`은 이 환경에서 스크립트가 전달되지 않았다.
- 명령줄 한도(약 32,000자) 때문에 base64가 3만 자를 넘지 않게 후보를 나눈다. 수천 개면 `window.__s=window.__s.concat([...])`로 1,000개씩 페이지에 먼저 넣고, 백그라운드 스크립트가 `window.__s`를 읽게 한다.
- PowerShell 5.1의 `Get-Content … | ConvertFrom-Json | Where-Object`는 배열을 한 덩어리로 넘겨 필터가 안 먹는다. 변수에 먼저 담고(`$x = … | ConvertFrom-Json`) `foreach`로 돈다. `@(…)`로 감싸도 안 된다.
- CSV를 쓰기 전에 넣을·지울 줄 수를 계산하고, 다르면 `throw`로 멈추게 한다. 쓴 뒤 `git diff --numstat`로 다시 확인.
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
| 무신사 | 브라우저 밖 직접 요청(PowerShell 등)은 403. 상품 목록 2쪽부터는 인증값(`hmacId`)이 필요해 403, `size`는 100까지(200은 400) → 1쪽 100개를 정렬·세부 카테고리로 바꿔 넓힌다. 우회하지 않는다. 전체 브랜드 목록 페이지(`/brands` 등)는 없지만, 카테고리 필터의 브랜드 목록(`plp/filter/brands`)은 쪽 넘김이 된다. 브랜드 영문 주소를 추측하면 자주 틀린다(예: 유라고 `urago`). 같은 이름의 브랜드숍이 둘인 경우가 있다(예: `boundary`·`boundary1`). |
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
- 10-27 · Cursor · 무신사 — 상품 목록을 정렬·세부 카테고리로 훑어 후보를 늘림(1,914개에서 막힘) → 카테고리 필터 응답의 `brand` 항목에 별도 주소(`plp/filter/brands`)가 있고 쪽 넘김이 됨 → 브랜드 전체(여성 4개 카테고리 합 4,337개)를 바로 받는다. 필터·facet 응답부터 볼 것.
- 10-27 · Cursor · 공통 — 사용자 지시로 비율 기준(여성 95%·의류 50%·판매 상품 수)을 없앰 → 비율 계산·상품 확인 단계가 빠져 요청 수가 브랜드당 6번에서 2번으로 줄었다. 기준이 복잡하면 먼저 사용자에게 단순화를 제안할 것.
- 10-27 · Cursor · 공통 — `ConvertFrom-Json` 결과를 바로 `Where-Object`로 걸러 상품 0개 16개가 같이 들어감 → PowerShell 5.1이 배열을 한 덩어리로 넘김 → 변수에 담고 `foreach`, 쓰기 전 줄 수 검사 `throw`로 막음(이번엔 이 검사로 두 번째 실수를 쓰기 전에 잡았다).
