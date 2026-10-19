# 01. 데이터 모델

## 핵심 개체

| 개체 | 뜻 | 예시 질문 |
| --- | --- | --- |
| Company | 법인 또는 운영 회사 | 이 쇼핑몰을 운영하는 회사는 어디인가? |
| BusinessUnit | 한 법인 안의 사업부문 | 법인 전체가 아닌 패션 사업부문의 브랜드·채널은 무엇인가? |
| Seller | 판매·통신판매 신고 주체 | 실제 판매 책임 주체는 누구인가? |
| Brand | 소비자에게 보이는 브랜드 | 어느 회사가 이 브랜드를 소유·운영하는가? |
| Storefront | 독립 쇼핑몰 또는 서비스 | 어떤 URL·앱에서 고객을 만나는가? |
| Platform | 여러 판매자 또는 브랜드가 입점하는 장 | 누가 플랫폼을 운영하는가? |
| SalesChannel | 브랜드가 판매하는 경로 | 자사몰, 플랫폼 입점, 오프라인, 해외 마켓 중 어디인가? |
| Category | 상품 분류 | 여성 의류, 가방, 스포츠웨어 등 어느 영역인가? |
| Evidence | 관계·속성을 뒷받침하는 근거 | 어떤 페이지·공시·등록부에서 언제 확인했는가? |

## 왜 분리하는가

브랜드명과 회사명, 자사몰과 입점몰, 쇼핑몰과 플랫폼은 자주 다르다. 이를 하나의 "쇼핑몰" 표로 합치면 소유 관계와 판매 경로가 무너진다. 개체를 분리하고 관계를 연결해야 나중에 국가와 채널이 늘어도 추적할 수 있다.

## 모든 주요 레코드에 필요한 공통 필드

| 필드 | 설명 |
| --- | --- |
| `id` | 변경되지 않는 내부 식별자 |
| `name` | 표기명 |
| `country_or_region` | 본사·법인 또는 대상 시장의 국가/지역 |
| `status` | active / inactive / unknown |
| `verification_status` | verified / partially_verified / candidate |
| `source_id` | 출처 등록부의 식별자 |
| `observed_at` | 사실을 마지막으로 확인한 시각 |
| `notes` | 불확실성, 조건, 해석 메모 |

## 관계 예시

```text
Company ──operates──> Storefront
BusinessUnit ──operates──> Storefront
BusinessUnit ──owns_or_operates──> Brand
Company ──owns_or_operates──> Brand
Seller ──sells_through──> Storefront 또는 Platform
Brand ──has_sales_channel──> SalesChannel
Brand / Storefront ──belongs_to──> Category
각 관계 ──supported_by──> Evidence
```

`operates`, `owns_or_operates`처럼 관계의 의미를 명확히 기록하고, 추정은 `candidate`로만 보관한다.
