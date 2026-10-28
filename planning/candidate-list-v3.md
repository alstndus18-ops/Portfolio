# 후보 목록 v3

**웹 접근 차단 오류(원문):** `Browser Use rejected this action due to browser security policy. Reason: The user declined permission for this action. Browser use could not acquire authority to trigger network egress. The origin approval gate did not grant access for https://nothing-written.com. The user declined approval. The agent must not attempt to achieve the same outcome via workaround, indirect execution, raw CDP or browser commands, alternate browser surfaces, or policy circumvention. Proceed only with a materially safer alternative that does not require this blocked browser action; if none exists, stop and request user input.`

**확인 시각:** 2026-10-29 01:08 KST  
**차단 사항:** 신규 웹 페이지(공식몰·검색·외부 기사)를 열 수 없었다. 아래는 이미 저장된 DB의 공개 채널 근거만 사용했다. 따라서 공식 URL, 가격, 공식 소개문은 새로 확인하지 않았으며 `확인 불가`로 기록한다.

## 범위와 방법

- 기준: `research/fashion-commerce-map/data/curated/korea_entities.csv`, `korea_relationships.csv`, `korea_evidence.csv`.
- 선택: DB에서 여성복/디자이너 여성복으로 분류되고 29CM 및/또는 W컨셉 판매 관계가 확인된, 기존 4개 보류 후보와 다른 20개 브랜드.
- `bose` 판정은 자사 생산 비중 근거가 필요하다. 해당 근거를 DB에서 확인하지 못했으므로 정규 브랜드/보세몰을 추정하지 않았다.
- 가격·무드 칸의 빈 값은 부정이 아니라 **이번 확인 범위에서 확인 불가**를 뜻한다.

| Brand | Type (regular/bose) | Official URL | Channel | Estimated price range (confirmed values only) | Mood keywords (official intro text only) | Evidence URL | Check date | Notes |
|---|---|---|---|---|---|---|---|---|
| 하나드 (HANAD) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/117158 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 54개를 기록. |
| 윤세 (YUNSÉ) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/107655 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 57개를 기록. |
| 와이씨에이치 (YCH) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/103201 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 62개를 기록. |
| 듀이듀이 (DEW E DEW E) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/102186 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 62개를 기록. |
| 분더캄머 (WNDERKAMMER) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/100007 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 62개를 기록. |
| 론론 (RONRON) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM | 확인 불가 | 확인 불가 | https://search.29cm.co.kr/?keyword= | 2026-10-26 | DB는 29CM 검색에서 브랜드 표기 상품 52개를 기록. |
| 잉크 (EENK) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/102781 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 62개를 기록. |
| 르셉템버 (LE17SEPTEMBRE) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/111079 | 2026-10-27 | DB의 W컨셉 여성 브랜드 랜딩 URL. |
| 앤유 (ANDYOU) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/102985 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 26개를 기록. |
| 로우클래식 (LOW CLASSIC) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM | 확인 불가 | 확인 불가 | https://search.29cm.co.kr/?keyword= | 2026-10-26 | DB는 29CM 검색에서 브랜드 표기 상품 52개를 기록. |
| 아모멘토 (AMOMENTO) | 미확인 (regular/bose) | 확인 불가 | 무신사, 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://display.wconcept.co.kr/rn/brand/103954 | 2026-10-26 | DB는 W컨셉 브랜드 표기 상품 62개를 기록. |
| 르닐 (LENIL) | 미확인 (regular/bose) | 확인 불가 | 29CM | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/17924 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 닐바이피 (NILBY P) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/112088 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 르하스 (LHAS) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/35202 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 드팜므 (DEFEMME) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/19309 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 아에르 (AEER) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/2273 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 베뉴엣 (BENUET) | 미확인 (regular/bose) | 확인 불가 | 29CM | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/20794 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 마레디마리 (MARE DI MARI) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/10210 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 킨더살몬 (KINDERSALMON) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/672 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |
| 메종마레 (MAISONMARAIS) | 미확인 (regular/bose) | 확인 불가 | 29CM, W컨셉 | 확인 불가 | 확인 불가 | https://www.29cm.co.kr/store/brand/2687 | 2026-10-27 | DB는 29CM 브랜드 페이지에서 현 의류 판매를 확인. |

## Stage 1 결과

20개 신규 후보의 공개 판매 채널은 DB 근거로 확인했다. 그러나 신규 웹 열람이 차단되어, 요청한 가격대·공식 소개문·공식몰 URL을 채우는 Stage 2의 검증은 완료할 수 없다. 위 후보는 **후보 풀**이며 강한 후보 선정 결과가 아니다.
