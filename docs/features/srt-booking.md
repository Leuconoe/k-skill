# SRT 운행시간표 조회 가이드

## 조회 전용 기능

`srt-booking`은 주식회사 에스알이 공개한 최신 SRT 운행시각표 HWP를 임시로 내려받아 계획 출발·도착 시각을 조회한다.

- 회원가입·로그인 불필요
- credential 불필요
- 실시간 잔여석·좌석번호 조회 없음
- 예약·예약대기·결제·취소 없음
- 자동 재조회·매진 감시 없음

## 필요한 것

- Node.js 18+
- `npx`
- Python 3

helper는 공식 HWP를 임시 디렉터리에 저장하고 `npx -y kordoc`으로 Markdown 변환한 뒤 원문과 변환물을 즉시 삭제한다.

## 입력값

- 출발역
- 도착역
- 날짜: `YYYYMMDD`
- 시작·종료 시각: `HHMM`
- 최대 결과 수

## 조회 예시

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- \
  search \
  --dep 수서 \
  --arr 부산 \
  --date 20260820 \
  --time 0600 \
  --time-limit 1200 \
  --limit 5
```

현재 사용 중인 에스알 공식 원본만 확인:

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- source
```

## 결과 해석

`trains`에는 열차번호와 계획 출발·도착 시각이 포함된다. `source`에는 공식 시간표 기준일, 첨부 번호와 다운로드 URL이 포함된다.

이 결과는 **공개 운행계획**이며 다음 정보는 제공하지 않는다.

- 실제 운휴·지연·편성 변경
- 실시간 좌석 판매 상태
- 호차·좌석번호
- 운임·할인 적용 결과

구매가 필요하면 결과의 `booking_url`을 사용자가 직접 열어 공식 SRT 표면에서 확인한다.

## 안전 경계

- 계정 ID·비밀번호를 요구하거나 저장하지 않는다.
- `SRTrain`, SRT 앱 내부 API 또는 좌석선택 내부 endpoint를 사용하지 않는다.
- 한 사용자 요청에 대해 한 번 조회하고 polling을 시작하지 않는다.
- CAPTCHA·차단·접근 제한을 우회하지 않는다.
- 자세한 배경은 [`AUTOMATION-LEGAL-STATEMENT.md`](../../srt-booking/references/AUTOMATION-LEGAL-STATEMENT.md)를 참고한다.
