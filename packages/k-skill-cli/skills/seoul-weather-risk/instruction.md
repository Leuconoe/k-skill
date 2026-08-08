# Seoul Weather Risk

## What this skill does

ASK 서울의 장소별 기상 위험 예상 시간대 단일 제품(`weather_place_risk_window`)을 읽기 전용 스킬로 탐색한다. helper는 hosted `k-skill-proxy`만 호출하며, 사용자 API Key를 발급받거나 저장하지 않는다. 실패 또는 미준비 상태를 fixture나 추정값으로 대체하지 않는다.

## Product

- `weather_place_risk_window` — 장소별 기상 위험 예상 시간대. 폭염·한파·호우·대설·강풍 후보를 임계값으로 선별한 예보 기반 참고 정보다(기상청 공식 특보가 아님).
- 질문 예: 특정 장소에서 방문·이동 주의가 필요할 수 있는 예보 시간과 근거는 무엇인가?
- grain: `place_id`와 `forecast_at`마다 한 행.

이 스킬은 단일 제품만 다룬다. bundle에 다른 제품이 섞여 있거나 이 제품이 빠지면 계약 오류로 중단한다.

## Workflow

1. 환경 설정만 먼저 확인한다. 이 명령은 네트워크를 호출하지 않는다.

```bash
npx -y @nomadamas/k-skill@0 exec seoul-weather-risk scripts/seoul_weather_risk.py -- preflight
```

2. bundle에서 이 제품의 준비 상태를 확인한다.

```bash
npx -y @nomadamas/k-skill@0 exec seoul-weather-risk scripts/seoul_weather_risk.py -- catalog
```

3. 제품의 grain, 기본키, 시간축, 공개 column 및 증거 metadata를 확인한다.

```bash
npx -y @nomadamas/k-skill@0 exec seoul-weather-risk scripts/seoul_weather_risk.py -- describe --product-id weather_place_risk_window
```

4. 공개 projection의 등호 필터와 `1..500` 범위의 limit으로 data page를 조회한다.

```bash
npx -y @nomadamas/k-skill@0 exec seoul-weather-risk scripts/seoul_weather_risk.py -- query \
  --product-id weather_place_risk_window \
  --filter place_id=example-place \
  --from 2026-08-01 \
  --to 2026-08-07 \
  --limit 100
```

응답의 `registration_ready`, `publication_id`, `blockers`를 먼저 확인한다. data 응답의 `next_cursor`는 같은 제품의 다음 page에만 그대로 재사용한다. publication이 바뀌면 cursor는 `409`로 만료된다.

## Boundaries

- table name, SQL, join, sort, aggregate를 입력받지 않는다.
- 알 수 없는 제품이나 필터를 추측해 보정하지 않는다.
- 기본 proxy origin은 `https://k-skill-proxy.nomadamas.org`이다. 별도 self-host proxy를 쓸 때만 `KSKILL_PROXY_BASE_URL`을 HTTPS origin으로 설정한다. 값은 명령행 인수, 문서, 로그에 넣지 않는다.
- 사용자 API Key와 `Authorization` 헤더를 사용하지 않는다. ASK Seoul 전용 서비스 키는 proxy 운영 환경에만 두며, Marketplace의 `k-skill-proxy:seoul-weather-risk` principal에 `skill:seoul-weather-risk:read` scope로 등록한다. 이 scope는 bundle·product·data 읽기만 허용하고 다른 Marketplace API를 거부한다. 사용자 환경·응답·로그에는 키가 존재하지 않는다.
- proxy는 bundle, 단일 product, 그 data 조회만 노출한다. `table name`, SQL, join, sort, aggregate 및 비허용 query field는 upstream으로 전달하지 않는다.
- `/skill/v1/bundles/seoul-weather-risk`의 제품 집합이 `weather_place_risk_window` 단일 제품과 다르면 응답 계약 오류로 중단한다.
- live 실패를 fixture나 synthetic 결과로 대체하지 않는다.
- 이 제품은 예보값 임계치 기반 참고 정보이며 기상청 공식 특보를 대체하지 않는다는 점을 응답에서 명확히 한다.

## Done when

- 실제 응답의 `publication_id`, `time_axis`(`forecast_at`), `usage` 및 행 수를 함께 설명했다.
- 준비되지 않은 제품(`503`)과 인증·권한·할당량 오류를 성공으로 표현하지 않았다.

## Failure modes

- `invalid_limit`: `1..500` 밖의 limit
- `proxy_disabled`, `invalid_proxy_base_url`: proxy 환경 설정 오류
- `unauthorized`/`api_key_missing`(401), `forbidden`/`api_key_forbidden`(403), `unknown_product`(404)
- `cursor_expired`(409), `rate_limited`(429), `product_not_ready`(503)
- `upstream_not_configured`(503): proxy 운영 환경에 ASK Seoul 전용 서비스 키 또는 origin이 설정되지 않음
- `response_contract_invalid`, `malformed_response`: 단일 제품 계약 또는 API 응답 계약 drift
