# seoul-weather-risk

`seoul-weather-risk`는 서울 행정동 이름을 정규 `place_id`로 해석한 뒤 ASK 서울의 장소별 기상 위험 예상 시간대 단일 제품(`weather_place_risk_window`)을 hosted `k-skill-proxy`로 탐색하는 읽기 전용 클라이언트다. 사용자는 내부 ID를 알거나 ASK Seoul API Key를 발급·저장할 필요가 없다.

## 행정동 입력 계약

- 기본 입력은 `--admin-dong <서울 행정동명>`이며 Unicode NFC·공백 정규화 후 정확히 일치시킨다.
- `kma_admin_dong_grid_20260325` 버전의 427행 bundled reference가 `admin_dong`, `gu`, `place_id`를 연결한다.
- 동명이명인 `신사동`은 `ambiguous_admin_dong`으로 중단하고 강남구/관악구 중 하나를 `--gu`로 요구한다.
- 오타·유사 문자열·좌표를 추측하지 않는다. 기존 자동화용 `--filter place_id=...`는 유지하되 `--admin-dong`과 동시 사용은 거부한다.
- proxy query에는 변환된 `place_id`만 포함하며 `admin_dong`과 `gu`는 전송하지 않는다.

## API 계약

- Base URL: 기본 `https://k-skill-proxy.nomadamas.org`, self-host 환경에서만 `KSKILL_PROXY_BASE_URL`로 대체한다(HTTPS origin, 끝 슬래시는 정규화).
- 사용자 인증: 없음. helper는 user-side `Authorization` 헤더를 보내지 않는다.
- Proxy bundle: `GET /v1/ask-seoul/weather-risk/bundle`
- Proxy detail: `GET /v1/ask-seoul/weather-risk/product`
- Proxy data: `GET /v1/ask-seoul/weather-risk/data?limit=1..500&from=&to=&cursor=` 및 `product_row_id`, `place_id`, `forecast_at`, `risk_labels` 등호 필터만 허용한다.

ASK Seoul 전용 서비스 키와 origin은 proxy 운영 환경의 `ASK_SEOUL_KSKILL_API_KEY`, `ASK_SEOUL_SKILL_API_BASE_URL`에만 둔다. Marketplace에서 이 키는 `k-skill-proxy:seoul-weather-risk` / `skill:seoul-weather-risk:read`로 고정 등록되어 bundle·product·data 읽기 외에는 사용할 수 없다. 키는 사용자 환경·문서·shell 인수·로그·응답에 포함하지 않는다. proxy origin이 HTTPS가 아니면 호출 전에 실패한다. 단위 테스트의 loopback mock HTTP만 예외다.

## 제품

| 항목 | 값 |
|---|---|
| product_id | `weather_place_risk_window` |
| 제목 | 장소별 기상 위험 예상 시간대 |
| grain | `place_id`와 `forecast_at`마다 한 행 |
| time_axis | `forecast_at` |
| 설명 | 폭염·한파·호우·대설·강풍 후보를 임계값으로 선별한 예보 기반 참고 정보(기상청 공식 특보 아님) |

## 동작 경계

- proxy는 이 스킬의 bundle, 단일 product, data 세 route만 allowlist하고, 비허용 query field·중복 field·`limit` 범위 밖 입력을 upstream으로 전달하지 않는다.
- helper는 bundled reference의 버전, 427행, 필수 필드, 고유 `place_id`, 고유 행정동·자치구 조합을 검증하고 drift 시 `location_mapping_invalid`으로 실패한다.
- bundle의 `products`가 `weather_place_risk_window` 단일 제품과 다르거나 중복되면 `response_contract_invalid`으로 실패한다.
- detail/data 응답은 bundle/product ID, page 수, cursor, JSON 계약을 검증한다. malformed JSON도 실패한다.
- API problem+json의 401, 403, 404, 409, 429, 503은 typed error로 보존한다. `429`의 `Retry-After`와 `request_id`만 안전한 오류 세부 정보로 전달한다.
- 준비되지 않은 제품(`503`)이나 네트워크 오류를 fixture 또는 synthetic 데이터로 대체하지 않는다.
