# similar-search 작업 규칙

재질을 새로 수집하거나 보완할 때는 먼저 `material-data/mall-extraction-rules.json`을 읽는다.

- 몰별 `steps` 순서대로 확인한다. 빈값은 마지막 단계까지 실패한 뒤에만 남긴다.
- 재질은 페이지 텍스트 또는 상세 이미지에 인쇄된 공식 `PRODUCT`·`FABRIC`·`소재` 표의 글자만 쓴다. 옷 사진의 모습으로 추정하지 않는다.
- 새 위치·새 템플릿·충돌·실패 원인을 발견하면 같은 JSON의 해당 몰 `learning_log`에 한 줄 추가하고, 반복될 규칙이면 `steps`에 넣는다.
- 기존 규칙이 작동하지 않아도 삭제하지 말고 `deprecated`로 표시한다. 과거 상품과 신규 상품의 템플릿이 공존할 수 있다.

색상별 사진을 새로 찾거나 보완할 때는 먼저 `data/color-photo-rules.json`을 읽는다.

- 몰마다 색 정보가 있는 곳이 다르다. 몰별 `where`(어디에 있는지)·`evidence`(쓰는 근거 순서)를 먼저 보고, 새 상품 구조를 만나면 `where`와 `learning_log`에 날짜와 함께 한 줄 추가한다.
- 그 색 단독 사진이 없으면 `fallback_policy` 순서로 내려간다. 여러 벌이 겹친 사진이라도 쓸 수 있으면 쓰되 어느 단계였는지(evidence)를 남기고, 그 색인지 확인 못 한 대표 사진은 확인 안 됨으로 표시한다.
- 옷 사진의 모습으로 색 이름을 지어내지 않는다. 색 이름은 구매 옵션의 이름만 쓴다.
- 규칙을 고친 뒤에는 `python tools/color_photos.py --sample 5`로 결과를 보고, 전체를 돌린 뒤 표본 30장을 눈으로 확인해 틀린 수를 `learning_log`에 적는다.
- 옵션 색마다 근거 단계(`ev`: label → lineup → representative)가 `data.js`에 적히고 카드·상세에 표시된다. 단계별 개수와 규칙 불일치는 `node tools/evidence_report.mjs`로 본다(Python 불필요).
- 순서: Python 환경에서 `python tools/color_photos.py --sample 5`(몰마다 5개, 파일 안 바뀜) → 결과가 맞으면 `python tools/color_photos.py`(OCR 모델 필요, 처음엔 오래 걸림) → `node tools/evidence_report.mjs`로 `문제 없음` 확인 → 화면에서 표본 확인. `ev` 기록 코드는 2026-10-28에 추가했고 Python으로는 아직 돌려 보지 않았다.
