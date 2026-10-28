# similar-search 작업 규칙

재질을 새로 수집하거나 보완할 때는 먼저 `material-data/mall-extraction-rules.json`을 읽는다.

- 몰별 `steps` 순서대로 확인한다. 빈값은 마지막 단계까지 실패한 뒤에만 남긴다.
- 재질은 페이지 텍스트 또는 상세 이미지에 인쇄된 공식 `PRODUCT`·`FABRIC`·`소재` 표의 글자만 쓴다. 옷 사진의 모습으로 추정하지 않는다.
- 새 위치·새 템플릿·충돌·실패 원인을 발견하면 같은 JSON의 해당 몰 `learning_log`에 한 줄 추가하고, 반복될 규칙이면 `steps`에 넣는다.
- 기존 규칙이 작동하지 않아도 삭제하지 말고 `deprecated`로 표시한다. 과거 상품과 신규 상품의 템플릿이 공존할 수 있다.

색상별 사진을 새로 찾거나 보완할 때는 먼저 `data/color-photo-rules.json`을 읽는다.

- 목표: 옷을 골라 색을 바꿀 때마다 그 색 옷이 보이는 사진이 나온다. 사람이 입은 사진인지 옷만 놓인 사진인지는 가리지 않고, 여러 벌이 함께 있어도 된다. 어느 것도 못 찾았을 때만 대표 사진을 쓴다.
- 전제: 상품 사진에 보이는 옷 색은 모두 그 옷의 옵션 색 안에 있다. 옵션 색 이름은 구매 옵션의 이름만 쓰고, 사진 모습으로 색 이름을 지어내지 않는다.
- 몰마다 색 정보가 있는 곳이 다르다. 몰별 `where`·`evidence`를 먼저 보고, 새 상품 구조를 만나면 `where`와 `learning_log`에 날짜와 함께 한 줄 추가한다.
- 순서는 `fallback_policy`: label(글자로 찾은 색 사진) → match(사진 속 옷 색이 그 색) → lineup(여러 색이 함께 보임) → representative. 옵션 색마다 `ev`가 `data.js`에 적히고 화면은 lineup·representative만 작게 표시한다.
- 실행(Python 3.12 + easyocr + transformers가 있는 PC): `python tools/color_photos.py --match --mall <몰> `로 한 몰씩(몰당 5~15분, CPU 기준) → `node tools/evidence_report.mjs`로 `문제 없음` 확인 → 화면에서 색을 바꿔 가며 표본 30장을 눈으로 확인해 틀린 수를 `learning_log`에 적는다. 글자(OCR)로 label을 새로 찾을 때는 `python tools/color_photos.py --sample 5` 후 `python tools/color_photos.py`.
- 스스로 학습: `--match`는 컷별 분할 결과를 `cache/seg_colors.json`(저장소에 안 올림)에 쌓아 같은 사진을 다시 분할하지 않고, 몰별로 색 사진이 나온 위치를 `data/color-photo-learned.json`에 쌓아 다음 실행에서 그 위치의 사진부터 보고 옵션 색을 다 찾으면 멈춘다. 학습 파일은 지우지 말고 같이 커밋한다.
