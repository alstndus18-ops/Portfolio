# 매일 추적하기 (며칠치 변화 보기)

> **2026-10-30부터 실제로 매일 도는 것은 `monitor\run_daily.cmd`다**(기획서 §14 방식, 그레이스유·쿠메·낫띵리튼·제이제이지고트·오르, `collect.py` → `materials.py` → `build.py`). 작업 스케줄러 "GraceU monitor daily"에 매일 20:00으로 등록했고 로그는 `monitor\logs\<날짜>.log`(커밋 안 함). 이 PC가 켜져 있어야 한다. 아래는 쉬즈미스 포함 옛 4곳의 상의 상세 트랙(`tools\run_daily.cmd`) 안내로, 예약하지 않았다.

그레이스유와 확정 4곳(쿠메·낫띵리튼·쉬즈미스·제이제이지고트)을 **같은 시각에 매일 한 번** 읽어 날짜별 스냅샷으로 쌓고, 날짜 사이 변화를 비교한다. 5일 정도 쌓으면 신상 주기·할인 시작/종료·진열 순서·가격 변경이 보인다. 기준선은 2026-10-29에 이미 저장했다.

## 한 번에 돌리기

```bash
tools\run_daily.cmd
```

(Windows. 필요한 것: Python 3.12, `agent-browser` CLI. Python 경로는 `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`로 가정한다. 다르면 파일 맨 위 `PY=` 줄만 고친다.) 전체 약 40~50분.

| 단계 | 대상 | 결과 파일 |
|---|---|---|
| 1 공식몰 전체 상품 | 4곳 전체 카테고리의 이름·정가·판매가·목록 순서 | `snapshots/official/<브랜드>/<날짜>.json` |
| 2 29CM 브랜드 페이지 | 4곳 | `snapshots/29cm/<ID>/<날짜>.json` |
| 3 W컨셉 브랜드관 | 그레이스유 + 4곳 | `snapshots/wconcept/<ID>/<날짜>.json` |
| 4 **상의 상세** | 그레이스유 + 4곳의 '상의' 상품마다 옵션(색상·사이즈)·품절 표시 (약 590개 상세 화면) | `snapshots/tops/<브랜드>/<날짜>.json` |
| 5 한 장 표 갱신 | 4번 결과로 `onepager/상의-비교표.md` 와 날짜별 복사본·지표 이력을 다시 만든다 | `onepager/history/` |

단계 4는 1단계의 그날 공식몰 스냅샷(낫띵리튼·제이제이지고트 ID, 쉬즈미스 가격)을 쓰므로 1단계가 먼저 끝나야 한다. 같은 날 다시 돌리면 그날 파일을 덮어쓴다. 로그인·장바구니·주문은 건드리지 않고 요청 사이 0.4~1초 쉰다.

## 변화 보기

```bash
python tools/diff_snapshots.py tops kume                      # 상의 상세 스냅샷: 가장 최근 두 날짜 비교 (신상·삭제·가격·완전 품절 표시 변동)
python tools/diff_snapshots.py tops --all --series            # 5곳 상의 지표 추이 표
python tools/diff_snapshots.py official kume 2026-10-29 2026-11-02   # 공식몰 전체 상품 비교
python tools/diff_snapshots.py 29cm 1939 --series
python tools/diff_snapshots.py wconcept 108809 --series
```

`onepager/history/상의-지표-이력.csv` 에는 날짜마다 5곳의 상의 지표(상품 수·판매가 중앙/사분위·정가 중앙·표시 할인·완전 품절 상품·옵션 조합 품절)가 한 줄씩 쌓인다.

## 읽을 때 알아야 할 것

- **품절 표시는 화면 상태일 뿐** 재고 수량이나 판매량이 아니다. 수량은 저장하지 않으며, 품절 비율로 인기나 소진 속도를 읽지 않는다.
- 공식몰 전체 스냅샷(1단계)은 목록에서 읽어 품절이 거의 안 읽힌다(쿠메·쉬즈미스 0건). 품절은 4단계(상세 옵션)에서만 믿을 수 있다.
- 29CM·W컨셉 스냅샷은 브랜드 페이지 **첫 화면 상품 카드**(약 50~190개)다. 전체 상품 수가 아니고 날마다 달라질 수 있다.
- 낫띵리튼 공식몰은 현재 시즌(293~304)·세일·재입고·아웃렛과 상의·니트 지난 시즌 목록을 읽는다.
- 바바더닷컴(제이제이지고트)은 그룹몰이다. 사이트가 표시하는 `total`과 읽은 수를 비교해 둔다.
- 스냅샷은 시각이 아니라 **날짜** 단위다. 하루에 두 번 돌릴 필요는 없다.

## 매일 자동으로 돌리고 싶을 때

`monitor\run_daily.cmd`는 이미 등록돼 있다(맨 위 참고). 확인·삭제:

```bash
schtasks /Query /TN "GraceU monitor daily" /FO LIST /V
schtasks /Delete /TN "GraceU monitor daily" /F
```

옛 트랙 `tools\run_daily.cmd`는 등록하지 않았다.
