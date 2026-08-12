# ktx-booking — assembled instructions

Runtime mode: dolshoi (CloakBrowser available)

## Runtime rules

- Detect capabilities, not product names. Dolshoi credential mode is active only when `DOLSHOI_ACTION_BROKER_URL` is set and `vault-run` is available; CloakBrowser mode is active when the built-in browser tool identifies CloakBrowser or `CLOAKBROWSER_PEEK_TOKEN` is set.
- When the user asks for an action and the official surface supports it lawfully, continue beyond lookup through reversible preparation and execution. Do not declare completion at a result list, deep link, or handoff when the action can still be carried out.
- Immediately before an irreversible external side effect such as payment, message/email delivery, final submission, cancellation, account mutation, or public posting, call `clarify` with the exact target, amount/payload, and effect. Execute only after approval; do not ask again for already-approved reversible steps.
- Preserve hard boundaries for law, required physical presence, CAPTCHA, identity proofing, electronic signatures, and unsupported official surfaces. In those cases, complete the furthest lawful supported step and open or prepare the exact next official step for the user.

## Bundled asset access

- Execute bundled helpers only through `npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/<file> -- <args>`; do not assume a repository-relative or installed-skill-relative path.
- Resolve an asset path with `npx -y @nomadamas/k-skill@0 path ktx-booking <relative-path>` only when another tool explicitly requires a filesystem path.
- Read bundled references through `npx -y @nomadamas/k-skill@0 read ktx-booking references/<file>`.

# KTX Live Timetable Lookup

## What this skill does

`korail2`의 시간표 검색 경로를 이용해 현재 KTX 운행 후보와 일반실·특실 예약 가능 여부를 조회한다.

이 스킬은 **라이브 조회 전용**이다.

- 회원 로그인과 credential을 사용하지 않는다.
- `ScheduleView` 검색 요청만 실행한다.
- 예약, 예약대기, 좌석 선점, 결제, 취소, 자동 재조회는 실행하지 않는다.
- 정확한 호차·좌석번호를 조회하지 않는다.
- 구매는 공식 코레일 페이지에서 사용자가 직접 진행한다.

KTX 조회에는 코레일의 현재 Dynapath 검사에 대응하는 `korail2` 호환 revision을 사용한다. 이는 조회 성공을 위한 검색 transport일 뿐 코레일의 공식 승인이나 약관상 허가를 의미하지 않는다.

## Commands

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- \
  search \
  --dep 서울 \
  --arr 부산 \
  --date 20260819 \
  --time 0600 \
  --time-limit 1200 \
  --limit 5
```

현재 라이브 조회 endpoint와 안전 경계:

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- source
```

출력:

- 열차번호·열차종류
- 요청한 출발역·도착역
- 현재 출발·도착 시각
- 일반실·특실 예약 가능 여부
- 사용한 라이브 search endpoint
- 공식 코레일 페이지

## Workflow

1. 출발역, 도착역, 날짜, 시간대를 확인한다.
2. `search`를 한 번 실행한다.
3. 요청 역과 정확히 일치하는 후보만 제시한다.
4. 좌석 구매가 필요하면 `booking_url`을 제공하고 종료한다.
5. 사용자가 다시 요청하지 않는 한 polling·매진 감시를 시작하지 않는다.

## Hard boundaries

- `KSKILL_KTX_ID`, `KSKILL_KTX_PASSWORD` 또는 회원 로그인을 요구하지 않는다.
- helper에 `reserve`, `reservations`, `cancel`, `payment`, waiting-list 명령을 추가하지 않는다.
- 예약 endpoint, 결제 endpoint 또는 계정 endpoint를 호출하지 않는다.
- CAPTCHA·접근 거부·계정 제한이 발생하면 즉시 중단한다.
- Dynapath 호환 header를 예약·로그인·결제 자동화에 확장하지 않는다.
- 사용자 요청 한 번을 반복 수집이나 장기 실행으로 확장하지 않는다.

## Failure modes

- `MACRO ERROR` 또는 코레일의 접근 제한
- upstream `korail2` 호환 revision 설치 실패
- 날짜·시간 또는 역명 오류
- 조건에 맞는 열차 없음

이 경우 차단을 우회하지 않고 [코레일 공식 조회 페이지](https://www.korail.com/ticket/train/schedule)를 안내한다.

## Legal notice

```bash
npx -y @nomadamas/k-skill@0 read ktx-booking references/AUTOMATION-LEGAL-STATEMENT.md
```
