# seoul-weather-risk

`seoul-weather-risk`는 ASK 서울의 장소별 기상 위험 예상 시간대 단일 제품(`weather_place_risk_window`)을 인증된 읽기 전용 K-Skill API로 탐색하는 클라이언트다.

## API 계약

- Base URL: `KSKILL_SEOUL_WEATHER_RISK_API_BASE_URL` (HTTPS origin, 끝 슬래시는 정규화)
- API Key: `KSKILL_SEOUL_WEATHER_RISK_API_KEY` (`Authorization: Bearer` 헤더)
- Bundle: `GET /skill/v1/bundles/seoul-weather-risk`
- Detail: `GET /skill/v1/products/{product_id}`
- Data: `GET /skill/v1/products/{product_id}/data?limit=1..500&from=&to=&cursor=` 및 공개 projection의 등호 필터

환경변수의 실제 값과 API Key는 문서, shell 인수, 로그, 응답에 포함하지 않는다. base URL이 없거나 HTTPS origin이 아니면 호출 전에 실패한다. 단위 테스트의 loopback mock HTTP만 예외다.

## 제품

| 항목 | 값 |
|---|---|
| product_id | `weather_place_risk_window` |
| 제목 | 장소별 기상 위험 예상 시간대 |
| grain | `place_id`와 `forecast_at`마다 한 행 |
| time_axis | `forecast_at` |
| 설명 | 폭염·한파·호우·대설·강풍 후보를 임계값으로 선별한 예보 기반 참고 정보(기상청 공식 특보 아님) |

## 동작 경계

- bundle의 `products`가 `weather_place_risk_window` 단일 제품과 다르거나 중복되면 `response_contract_invalid`으로 실패한다.
- detail/data 응답은 bundle/product ID, page 수, cursor, JSON 계약을 검증한다. malformed JSON도 실패한다.
- API problem+json의 401, 403, 404, 409, 429, 503은 typed error로 보존한다. `429`의 `Retry-After`와 `request_id`만 안전한 오류 세부 정보로 전달한다.
- 준비되지 않은 제품(`503`)이나 네트워크 오류를 fixture 또는 synthetic 데이터로 대체하지 않는다.
