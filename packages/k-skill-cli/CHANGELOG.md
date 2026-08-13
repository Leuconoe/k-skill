# @nomadamas/k-skill

## 0.2.5

### Patch Changes

- ed21f93: Rewrite the setup workflow around skill installation, Claude Code plugin support, the unified CLI runtime, credential resolution, verification, and strictly approved update checks.
- e145763: Remove the deprecated `used-car-price-search` skill from bundled CLI assets.
- 79e57d5: store-longevity-radar가 공공데이터포털 직접 다운로드 실패 시 SHA-256 검증된 R2 미러를 fallback으로 사용하도록 한다.

## 0.2.4

### Patch Changes

- cd546c5: Use the official Kakao Local API for nearby bar candidates and return Kakao Map detail-page handoffs for menu, opening-hour, and seating enrichment.
- 1644058: Remove the unofficial `tossctl` fallback and expose only the official Toss Securities Open API client. Calls now require official OAuth credentials and do not fall back to CLI sessions, scraping, or undocumented HTTP routes.
- efaeee8: Remove the discontinued Catchtable and Hi-Pass skills from the bundled CLI.
- ddcae69: seoul-weather-risk 스킬과 ASK 서울 기상 위험 조회 helper를 CLI 번들에 추가한다. 장소별 폭염·한파·호우·대설·강풍 후보 예보 시간대와 판정 근거를 인증된 읽기 전용 HTTPS API로 조회한다.

## 0.2.3

### Patch Changes

- 0aa0a2d: Remove a discontinued clinic-search skill from the bundled CLI assets.
- 7daf89a: store-longevity-radar 스킬과 상가업소 시계열 장수 점포 추출 helper를 CLI 번들에 추가한다.

## 0.2.2

### Patch Changes

- 38a3121: hankookilbo-news 스킬을 CLI 번들에 추가한다. 한국일보 공식 원격 MCP 서버를 인증 없이 직접 호출해 기사 메타데이터를 조회한다.
- 9a206b2: naver-blog-research: 검색 결과 제목·스니펫에서 숨김 접근성 라벨 "새 창 열림" 제거

## 0.2.1

### Patch Changes

- Bundle and migrate the remaining fine-dust, KTX, and setup root helpers found
  by the registry E2E suite.

## 0.2.0

### Minor Changes

- c556b5e: k-skill 통합 CLI를 추가하고 122개 스킬 전체를 runtime-aware adapter로 전환한다.
  generic/Dolshoi instruction 조립(`instruct`), 82개 helper script 실행(`exec`),
  8개 reference 조회(`read`), 안전한 asset 경로 확인(`path`), 전체 목록(`list`)을
  제공하며 모든 bundled asset을 npm 패키지에 포함한다.
