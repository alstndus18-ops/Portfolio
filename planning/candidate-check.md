# 그레이스유 상의 비교 — 후보 4곳 공개몰 확인

## 결론 (5줄)

1. **낫띵리튼·시엔느·쿠메**는 상의(및 메뉴상 Top/Knit) 목록을 읽었고, 상품 단위 **10개 이상**·대표가 중앙값이 그레이스유(153,000원) **±20% 안**이라 가격대는 **비슷함**으로 본다.
2. **다이애그널**은 TOPS·KNITWEAR 목록 66개 상품 단위까지 읽었으나 중앙값 **94,000원**으로 기준보다 **한 단계 아래**다.
3. 무드(소개·상품명 텍스트만): 그레이스유와 **knit·blouse·cardigan·neck** 등이 겹치는 **낫띵리튼·시엔느**는 가격·무드 모두 맞아 **우선 후보**, **쿠메**는 가격은 비슷하나 소개 키워드 겹침이 약해 **보류**, **다이애그널**은 가격대가 달라 **보류**다.
4. 쿠메 TOP 목록은 공식몰에 **25건 전부**만 노출되어(5페이지 한도 전) 표본 수는 그레이스유(55)보다 적다.
5. 원본 행 데이터는 `planning/candidate-check-raw/*.json`, 확인 시각 **2026-10-29 00:26 KST**(목록 요청 간격 1초).

## 기준선 재확인 (그레이스유 상의)

| 항목 | 값 |
| --- | --- |
| 상품 단위 수 | 55 |
| 대표가 중앙값 | 153,000원 |
| 중간 50% (Q1~Q3) | 101,500~218,000원 |
| 관측일 | 2026-10-28 |
| 가격대 ±20% 밴드 | 122,400~183,600원 (중앙값 기준) |

**통계 계산(한 줄):** 목록·상세에서 읽은 행마다 상품명 끝 `(색상)`을 제거한 기본 이름으로 묶고, 할인가 우선·없으면 정가를 대표값으로 쓰며 색상별 가격이 다르면 그 상품은 최솟값~최댓값 범위의 **산술평균**을 하나의 대표값으로 두고, 상품별 대표값 배열에 대해 **선형 보간**으로 중앙값·Q1·Q3를 계산했다.

**그레이스유 무드 키워드(텍스트만):**

- 소개(회사소개·메타): `Elegant`, `timeless`, `philosophy`, `lifestyle`, `우아한`, `타임리스`, `데일리룩`(keywords)
- 상의 상품명(55개 묶음) 빈도 상위: `top`, `blouse`, `knit`, `cardigan`, `sleeveless`, `cashmere`, `neck`, `drape`, `tie`, `stripe` 등

## 후보별

| 후보 | 목록 URL | 상품 수 | 중앙값 | Q1~Q3 | 가격대 | 무드 키워드 (소개·상품명) | 최종 |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| 낫띵리튼 | [Tops](https://nothing-written.com/product/list.html?cate_no=79), [Knitwear](https://nothing-written.com/product/list.html?cate_no=147) | 80 | 155,000원 | 46,000~179,000원 | 비슷함 | 소개: `daily life`, `workplace`, `design`, `tailoring`, `details` / 상품명: `shirt`, `knit`, `pullover`, `neck`, `button` | **우선** |
| 시엔느 | [Top](https://sienneboutique.com/product/list.html?cate_no=44), [Knit](https://sienneboutique.com/product/list.html?cate_no=78) | 49 | 135,000원 | 86,500~158,000원 | 비슷함 | 소개: `빈티지`, `시크`, `디자이너` / 상품명: `knit`, `wool`, `alpaca`, `cardigan`, `shirt`, `blouse`, `stripe` | **우선** |
| 쿠메 | [TOP](https://kume-studio.co.kr/product/list.html?cate_no=479) | 25 | 159,600원 | 140,600~192,850원 | 비슷함 | 소개: `현대적`, `감각적`, `여성복` / 상품명: `shirt`, `knit`, `blend`, `cotton`, `halter` (목록 다수 `Men's` 접두) | **보류** |
| 다이애그널 | [TOPS](https://www.diagonal.co.kr/product/list.html?cate_no=44), [KNITWEAR](https://www.diagonal.co.kr/product/list.html?cate_no=84) | 66 | 94,000원 | 62,750~127,000원 | 한 단계 아래 | 소개: `간결`, `센슈얼`, `디자인`, `여성복` / 상품명: `tee`, `knit`, `top`, `camisole`, `cardigan`, `stripe` | **보류** |

**가격대 판정:** 상품 수 ≥10일 때만 적용. 중앙값이 122,400~183,600원이고 Q1~Q3 구간이 기준 101,500~218,000원과 **절반 이상 길이** 겹치면「비슷함」, 중앙값만으로는 183,600원 초과·122,400원 미만이면 각각「한 단계 위·아래」.

**우선/보류:** 가격대「비슷함」과 그레이스유 무드 키워드 **교집합이 1개 이상**(상품명·소개에 실제 등장하는 단어)일 때만「우선」, 하나만 맞으면「보류」.

## 확인 한계

| 후보 | 상태 | 한계 |
| --- | --- | --- |
| 낫띵리튼 | 읽음 | 목록 100행 상한(5페이지)·Tops+Knitwear 합산; 메타 description은 짧고 브랜드 문구는 **홈 메인 본문**에서 확인 |
| 시엔느 | 읽음 | Top+Knit 합산 100행 상한; 상품명은 목록의 영문명+`(모델 색)` 형식 |
| 쿠메 | 읽음 | TOP 카테고리 **전량 25건**만 목록에 있음(100·5페이지 한도 미만) |
| 다이애그널 | 읽음 | TOPS+KNITWEAR 합산 100행 상한; RE-BORN 등 저가 티가 중앙값을 낮춤 |

접근 실패·로그인 요구·목록 부재 없음.

## 확인 시각 · 공식몰

- **확인 시각:** 2026-10-29 00:26 KST
- **낫띵리튼:** https://nothing-written.com/
- **시엔느:** https://sienneboutique.com/
- **쿠메:** https://kume-studio.co.kr/
- **다이애그널:** https://www.diagonal.co.kr/
