# 설치한 에이전트 스킬 목록

작성일: 2026-10-27 · 설치 위치: 작업한 PC의 사용자 폴더 (`~/.claude/skills`, 저장소 밖)

이 목록은 어떤 스킬을 어디서 가져왔는지 기록하려고 남긴다. 스킬 본문은 저장소에 넣지 않는다. 다른 PC에서 쓰려면 아래 명령으로 같은 출처에서 다시 설치한다.

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

보안 검사 결과는 skills.sh 페이지에 표시된 값을 옮긴 것이다. 설치 전에 직접 검증한 것은 아니다.

## 설치 명령 (참고)

```bash
npx skills add <owner/repo@skill> -g -y
```

예: `npx skills add graphify-labs/graphify@graphify -g -y`

## 검토했지만 설치하지 않은 것

- camofox-browser, camofox-cli: 봇 탐지 회피 도구라 프로젝트 원칙(접근 제한 우회 금지)과 충돌한다.
- claude-ads: 광고 계정 운영용이라 지금 목적과 다르다. `ads-competitor`는 나중에 검토할 수 있다.
- market-sizing-analysis: 신규 사업 투자용이라 지금은 쓸 데가 없다. 금액 추정이 필요해지면 다시 본다.
- company-identity-reconciliation: 유료 API 키와 외부 플랫폼 조회가 필요해서 보류한다.
- 그 밖의 네이버·쿠팡 대량 수집, 우회 기능이 있는 스킬은 프로젝트 원칙과 맞지 않아 제외했다.
