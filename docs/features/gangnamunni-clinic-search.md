# 강남언니 병원 조회 가이드

`gangnamunni-clinic-search`는 강남언니 공개 병원 목록 페이지에서 병원 후보를 조회하는 read-only 스킬입니다.

## 공개 접근 경로

- 기본 검색 URL: `https://www.gangnamunni.com/hospitals?q=<keyword>`
- 데이터 위치: HTML 안의 `__NEXT_DATA__` JSON (`props.pageProps.dehydratedState.queries[*].state.data.pages[*].data`)
- query 선택: `queryKey[0] === "infinite-search-hospitals"`
- 같은 payload의 이전 필드 fallback: 이전 `/search?q=<keyword>` HTML에서 쓰던 `props.pageProps.hospitals`도 파싱한다. `/search`를 추가 요청하지 않는다.
- 인증/시크릿: 불필요
- 프록시: 사용하지 않음

## 예시

```bash
npx gangnamunni-clinic-search "강남 성형외과" --limit 5
```

```js
const { searchClinics } = require("gangnamunni-clinic-search")
const result = await searchClinics({ query: "코성형", limit: 3 })
```

## 출력

각 후보는 공개 검색 페이지에 포함된 병원명, 평점, 리뷰 수, 지역/역/거리, 지원 언어, 이미지 URL, 공개 병원 링크를 포함합니다. 좌표처럼 upstream이 현재 응답에 주지 않는 값은 생략될 수 있습니다.

## 제한사항

- 조회 시점 공개 검색 결과 기준입니다.
- 로그인, 상담, 예약, 결제, 찜, 리뷰 작성은 자동화하지 않습니다.
- CAPTCHA/차단/로그인벽/빈 shell 페이지는 실패 모드로 처리합니다.
- `pageProps.totalLength` 또는 dehydrated `recordsTotal`은 있는데 파싱 가능한 병원이 없으면 `failureMode: "empty-shell"`로 구조 변경을 명시합니다.
- 의료 판단이나 병원 선택 보증을 대신하지 않습니다.
