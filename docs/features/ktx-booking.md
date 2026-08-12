# KTX 운행시간표 조회 가이드

## 조회 전용 기능

`ktx-booking`은 한국철도공사가 공개한 최신 KTX 운행시간표 XLSX를 읽어 계획 출발·도착 시각을 조회한다.

- 회원가입·로그인 불필요
- credential 불필요
- 실시간 잔여석·좌석번호 조회 없음
- 예약·예약대기·결제·취소 없음
- 자동 재조회·매진 감시 없음

## 필요한 것

- Node.js 18+
- `npx`

helper는 PEP 723 메타데이터에 선언된 `openpyxl`을 `uv`로 실행한다.

## 입력값

- 출발역
- 도착역
- 날짜: `YYYYMMDD`
- 시작·종료 시각: `HHMM`
- 최대 결과 수

## 조회 예시

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- \
  search \
  --dep 서울 \
  --arr 부산 \
  --date 20260820 \
  --time 0600 \
  --time-limit 1200 \
  --limit 5
```

현재 사용 중인 한국철도공사 원본만 확인:

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- source
```

## 결과 해석

`trains`에는 열차번호와 계획 출발·도착 시각이 포함된다. `source`에는 공식 파일 제목, 게시일, 다운로드 URL이 포함된다.

이 결과는 **공개 운행계획**이며 다음 정보는 제공하지 않는다.

- 실제 운휴·지연·편성 변경
- 실시간 좌석 판매 상태
- 호차·좌석번호
- 운임·할인 적용 결과

구매가 필요하면 결과의 `booking_url`을 사용자가 직접 열어 공식 코레일 표면에서 확인한다.

## 안전 경계

- 계정 ID·비밀번호를 요구하거나 저장하지 않는다.
- Korail 앱 내부 API, `korail2`, Dynapath token 또는 anti-bot 복구 로직을 사용하지 않는다.
- 한 사용자 요청에 대해 한 번 조회하고 polling을 시작하지 않는다.
- CAPTCHA·차단·접근 제한을 우회하지 않는다.
- 자세한 배경은 [`AUTOMATION-LEGAL-STATEMENT.md`](../../ktx-booking/references/AUTOMATION-LEGAL-STATEMENT.md)를 참고한다.
